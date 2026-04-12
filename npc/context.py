"""NPC context-building utilities for outbreak simulation prompts.

Provides functions to build epidemiologic and NPC-specific data context,
manage investigation stage tracking, redact spoilers, and generate
style hints for NPC dialogue.
"""

import re
import json

import streamlit as st
import pandas as pd

from outbreak_logic import apply_case_definition


def _scenario_config_label(scenario_type: str) -> str:
    """Return the disease display name from the active scenario config."""
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    return scenario_config.get("disease_name", "Case")


def build_epidemiologic_context(truth: dict) -> str:
    """Short summary of the outbreak from truth tables."""
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"][["village_id", "village_name"]]

    hh_vil = households.merge(villages, on="village_id", how="left")
    hh_columns = ["hh_id", "village_name"]
    hh_columns.extend(
        col
        for col in ["cleanup_participation", "flood_depth_category"]
        if col in hh_vil.columns
    )
    merged = individuals.merge(hh_vil[hh_columns], on="hh_id", how="left")
    for optional_col in ["cleanup_participation", "flood_depth_category"]:
        if optional_col not in merged.columns:
            merged[optional_col] = pd.NA

    scenario_type = truth.get("scenario_type")
    case_criteria = {
        "scenario_id": st.session_state.get("current_scenario"),
        "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
        "lab_results": st.session_state.lab_results,
    }
    cases = apply_case_definition(merged, case_criteria)
    total_cases = len(cases)

    if total_cases == 0:
        return f"No symptomatic {_scenario_config_label(scenario_type).lower()} cases have been assigned in the truth model."

    if scenario_type == "lepto":
        adult_male_cases = cases[
            (cases["sex"] == "M") & (cases["age"] >= 18) & (cases["age"] <= 60)
        ]
        if "cleanup_participation" in cases.columns:
            cleanup_cases = cases[
                cases["cleanup_participation"].isin(["heavy", "moderate", "light"])
            ]
        else:
            cleanup_cases = cases.iloc[0:0]
        if "flood_depth_category" in cases.columns:
            flood_exposed_cases = cases[
                cases["flood_depth_category"].isin(["deep", "moderate"])
            ]
        else:
            flood_exposed_cases = cases.iloc[0:0]
        context = (
            f"There are currently about {total_cases} symptomatic {_scenario_config_label(scenario_type).lower()} cases in the district. "
            f"Adult men account for {len(adult_male_cases)} cases. "
            f"{len(cleanup_cases)} cases report flood cleanup work, and {len(flood_exposed_cases)} "
            "come from households with moderate or deep flooding exposure."
        )
        return context

    village_counts = cases["village_name"].value_counts().to_dict()

    bins = [0, 4, 14, 49, 120]
    labels = ["0–4", "5–14", "15–49", "50+"]
    age_groups = pd.cut(cases["age"], bins=bins, labels=labels, right=True)
    age_counts = age_groups.value_counts().to_dict()

    context = (
        f"There are currently about {total_cases} symptomatic {_scenario_config_label(scenario_type).lower()} cases in the district. "
        f"Cases by village: {village_counts}. "
        f"Cases by age group: {age_counts}. "
        "Most cases are children and cluster around key exposure areas."
    )
    return context


def build_npc_data_context(npc_key: str, truth: dict) -> str:
    """NPC-specific data context based on their data_access scope."""
    from npc.emotions import get_npc_trust

    npc_truth_dict = truth.get("npc_truth", {})
    if npc_key not in npc_truth_dict:
        return "No additional context available for this character."
    npc = npc_truth_dict[npc_key]
    data_access = npc.get("data_access")
    scenario_type = truth.get("scenario_type")
    case_label = _scenario_config_label(scenario_type).lower()

    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"][["village_id", "village_name"]]

    hh_vil = households.merge(villages, on="village_id", how="left")
    merged = individuals.merge(
        hh_vil[["hh_id", "village_name"]], on="hh_id", how="left"
    )
    case_criteria = {
        "scenario_id": st.session_state.get("current_scenario"),
        "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
        "lab_results": st.session_state.lab_results,
    }
    cases = apply_case_definition(merged, case_criteria)

    epi_context = build_epidemiologic_context(truth)
    trust_level = get_npc_trust(npc_key)

    if data_access and trust_level < 1:
        return (
            epi_context
            + " You are cautious about sharing detailed records until the team earns more trust."
        )

    # Override for Dr. Tran - restrict his knowledge to prevent omniscience
    if npc_key == "dr_chen":
        return (
            "You are aware of 2 severe pediatric cases admitted in the last 48 hours. "
            "One has died. You recall seeing maybe 2-3 other similar cases over the "
            "last month, but you do not have the files in front of you. "
            "You DO NOT know the total case count in the district. "
            "You believe the mine is responsible."
        )

    if data_access == "hospital_cases":
        summary = cases.groupby("village_name").size().to_dict()
        return (
            epi_context
            + f" As hospital director, you mainly see hospitalized {case_label} cases. "
              f"You know current hospitalized cases come from these villages: {summary}."
        )

    if data_access == "triage_logs":
        earliest = cases["onset_date"].min()
        latest = cases["onset_date"].max()
        return (
            epi_context
            + " As triage nurse, you mostly notice who walks in first. "
              f"You saw the first {case_label} cases between {earliest} and {latest}."
        )

    if data_access == "private_clinic":
        cases = cases[cases["village_name"] == "Nalu Village"]
        n = len(cases)
        return (
            epi_context
            + f" As a private healer, you have personally seen around {n} early "
              f"{case_label}-like illnesses from households near pig farms and rice paddies in Nalu."
        )

    if data_access == "school_attendance":
        school_age = cases[(cases["age"] >= 5) & (cases["age"] <= 18)]
        cases = school_age
        n = len(cases)
        by_village = cases["village_name"].value_counts().to_dict()
        return (
            epi_context
            + f" As school principal, you mostly know about school-age children. "
              f"You know of {case_label} cases among your students: {n} total, by village: {by_village}."
        )

    if data_access == "vet_surveillance":
        lab = truth["lab_samples"]
        pigs = lab[lab["sample_type"] == "pig_serum"]
        pos = pigs[pigs["true_JEV_positive"] == True]
        by_village = pos["linked_village_id"].value_counts().to_dict()
        return (
            epi_context
            + " As the district veterinary officer, you track pig health. "
              f"Recent pig tests suggest JEV circulation in villages: {by_village}."
        )

    if data_access == "environmental_data":
        env = truth["environment_sites"]
        high = env[env["breeding_index"] == "high"]
        sites = high["site_id"].tolist()
        return (
            epi_context
            + " As environmental health officer, you survey breeding sites. "
              f"You know of high mosquito breeding around these sites: {sites}."
        )

    return epi_context


# =========================
# ANTI-SPOILER / DISCLOSURE HELPERS
# =========================

def investigation_stage() -> str:
    """Return 'confirmed' when the etiology has been earned/revealed, else 'pre_confirmation'."""
    if st.session_state.get("etiology_revealed", False):
        return "confirmed"
    # If a final diagnosis has been explicitly recorded, treat as confirmed.
    if bool((st.session_state.get("decisions", {}) or {}).get("final_diagnosis")):
        return "confirmed"
    return "pre_confirmation"


_SPOILER_PATTERNS = [
    (re.compile(r"\bJapanese\s+Encephalitis\b", re.IGNORECASE), "a mosquito-borne viral encephalitis"),
    (re.compile(r"\bJEV\b", re.IGNORECASE), "the suspected encephalitis virus"),
    # Avoid replacing words like 'project' etc; keep JE replacement conservative.
    (re.compile(r"\bJE\b", re.IGNORECASE), "encephalitis"),
]


def redact_spoilers(text: str, stage: str) -> str:
    if stage == "confirmed" or not text:
        return text
    out = str(text)
    for rgx, repl in _SPOILER_PATTERNS:
        out = rgx.sub(repl, out)
    return out


def sanitize_npc_truth_for_prompt(npc_truth: dict, stage: str) -> dict:
    """Return a copy of npc_truth safe to include in prompts before confirmation."""
    if not isinstance(npc_truth, dict):
        return npc_truth
    safe = dict(npc_truth)

    # Simple string fields
    for k in ["name", "role", "personality"]:
        if k in safe:
            safe[k] = redact_spoilers(safe[k], stage)

    # List fields
    for k in ["always_reveal", "red_herrings", "unknowns"]:
        if k in safe and isinstance(safe[k], list):
            safe[k] = [redact_spoilers(x, stage) for x in safe[k]]

    # Dict fields
    if isinstance(safe.get("conditional_clues"), dict):
        safe["conditional_clues"] = {kk: redact_spoilers(vv, stage) for kk, vv in safe["conditional_clues"].items()}

    return safe


def npc_style_hint(npc_key: str, question_count: int, npc_state: str) -> str:
    """Small deterministic style variation to reduce robotic feel."""
    # Keep hints short so they don't dominate the system prompt.
    if npc_state in ("annoyed", "offended"):
        return "Keep it short. One point per sentence. No extra context unless asked."
    if npc_key in ("nurse_joy", "clinic_nurse"):
        if question_count < 2:
            return "Sound busy and slightly stressed. Ask one clarifying question if needed."
        return "Be helpful but time-pressed. Occasionally mention workload."
    if npc_key in ("dr_chen", "hospital_director"):
        return "Use a calm, clinical tone. Avoid speculation; distinguish observed vs assumed."
    if npc_key in ("chief_musa", "district_officer"):
        return "Be formal and concise. Focus on actions, constraints, and coordination."
    if npc_key in ("vet_amina",):
        return "Use One Health framing. Mention animal/veterinary context only when relevant."
    if npc_key in ("mr_osei",):
        return "Use practical environmental language. Mention mosquitoes/water management if asked."
    return "Speak naturally. If unsure, say so."
