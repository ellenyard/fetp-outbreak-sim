"""Case-definition utilities and related helpers.

Functions for building, recording, summarising, and providing feedback
on structured case definitions, plus small scenario-config accessors
used by the overview and case-finding tabs.
"""

import time

import streamlit as st
import day1_utils

# ---------------------------------------------------------------------------
# Scenario / column helpers
# ---------------------------------------------------------------------------


def get_symptomatic_column(truth: dict) -> str:
    """Return the symptomatic column based on the scenario."""
    scenario_type = truth.get("scenario_type")
    if scenario_type == "lepto":
        return "symptomatic_lepto"
    return "symptomatic_AES"


def scenario_config_label(scenario_type: str) -> str:
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    available_sample_types = sorted(
        {stype for test in scenario_config.get("lab_tests", []) for stype in test.get("sample_types", [])}
    ) or ["human_CSF", "human_serum", "pig_serum", "mosquito_pool"]
    return scenario_config.get("disease_name", "Case")


def get_day1_assets() -> dict:
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    return day1_utils.load_day1_assets(scenario_id)


# ---------------------------------------------------------------------------
# Domain unlocking (based on NPC interviews / lab orders / env findings)
# ---------------------------------------------------------------------------


def derive_unlocked_domains() -> set[str]:
    domains = {"demographics", "clinical"}
    npc_truth = st.session_state.truth.get("npc_truth", {})
    interview_history = st.session_state.get("interview_history", {})

    data_access_domains = {
        "vet_surveillance": {"animals"},
        "environmental_data": {"environment", "vector"},
        "mining_environmental_compliance_records": {"environment"},
    }

    for npc_key in interview_history.keys():
        npc = npc_truth.get(npc_key, {})
        access = npc.get("data_access")
        if access in data_access_domains:
            domains.update(data_access_domains[access])
        if "nurse" in npc.get("role", "").lower() or "doctor" in npc.get("role", "").lower():
            domains.add("vaccination")

    if st.session_state.get("nurse_pig_clue_shown"):
        domains.add("animals")

    lab_orders = st.session_state.get("lab_orders", []) or []
    if any(order.get("sample_type") == "mosquito_pool" for order in lab_orders):
        domains.add("vector")

    env_findings = st.session_state.get("environment_findings", []) or []
    if env_findings:
        domains.add("environment")

    return domains


# ---------------------------------------------------------------------------
# Case definition summary / versioning / feedback
# ---------------------------------------------------------------------------


def build_case_definition_summary(case_def: dict) -> str:
    lines = []
    tiers = case_def.get("tiers", {}) if isinstance(case_def, dict) else {}
    if "time_window" in case_def:
        tw = case_def.get("time_window", {})
        lines.append(f"Time: {tw.get('start', '')} to {tw.get('end', '')}")
    if case_def.get("villages"):
        lines.append(f"Place: {', '.join(case_def.get('villages', []))}")
    if case_def.get("exclusions"):
        lines.append(f"Exclusions: {', '.join(case_def.get('exclusions', []))}")
    for tier in ["suspected", "probable", "confirmed"]:
        tier_data = tiers.get(tier, {})
        if not tier_data:
            continue
        lines.append(f"{tier.title()} Case:")
        required_any = tier_data.get("required_any", [])
        optional = tier_data.get("optional_symptoms", [])
        min_opt = tier_data.get("min_optional", 0)
        if required_any:
            lines.append(f"- Clinical: at least one of {', '.join(required_any)}")
        if optional:
            lines.append(f"- Additional: \u2265{min_opt} of {', '.join(optional)}")
        if tier_data.get("epi_link_required"):
            lines.append("- Epi link required")
        if tier_data.get("lab_required"):
            labs = tier_data.get("lab_tests", [])
            lab_text = ", ".join(labs) if labs else "lab confirmation"
            lines.append(f"- Lab: {lab_text}")
    return "\n".join(lines)


def record_case_definition_version(case_def: dict, rationale: str = "") -> None:
    versions = st.session_state.get("case_definition_versions", [])
    next_version = len(versions) + 1
    entry = {
        "version": f"v{next_version}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "case_definition": case_def,
        "rationale": rationale,
    }
    versions.append(entry)
    st.session_state.case_definition_versions = versions
    st.session_state.decisions["case_definition_history"] = versions


def case_definition_feedback(case_def: dict) -> str:
    """Provide scenario-aware feedback on the case definition quality."""
    if not case_def:
        return "\u26a0\ufe0f Add clinical, time/place, and exclusion criteria to tighten the definition."

    scenario_config = st.session_state.get("scenario_config", {}) or {}
    scenario_type = scenario_config.get("scenario_type", "")
    disease_name = scenario_config.get("disease_name", "the disease")

    time_window = case_def.get("time_window", {})
    villages = case_def.get("villages", [])
    exclusions = case_def.get("exclusions", [])
    tiers = case_def.get("tiers", {})

    feedback_parts = []

    # Check for missing basic elements
    missing = []
    if not time_window.get("start") or not time_window.get("end"):
        missing.append("time window")
    if not villages:
        missing.append("geographic boundary")
    if not exclusions:
        missing.append("exclusions (rule-outs for differential diagnoses)")
    if missing:
        feedback_parts.append(f"\u26a0\ufe0f **Missing elements:** {', '.join(missing)}.")

    # Check tier structure
    suspected = tiers.get("suspected", {})
    probable = tiers.get("probable", {})
    confirmed = tiers.get("confirmed", {})

    if not suspected.get("required_any"):
        feedback_parts.append("\u26a0\ufe0f **Suspected tier** has no required symptoms - consider adding at least one clinical criterion (e.g., fever).")

    # Scenario-specific feedback for leptospirosis
    if scenario_type == "lepto":
        # Check if exposure criteria are included for probable cases
        if not probable.get("epi_link_required"):
            feedback_parts.append("\U0001f4a1 **Tip for leptospirosis:** Probable cases typically require exposure history (floodwater contact, cleanup work). Consider enabling 'Require epidemiological link' for the Probable tier.")

        # Check if myalgia is included (hallmark symptom)
        all_symptoms = set()
        for tier in tiers.values():
            all_symptoms.update(tier.get("required_any", []))
            all_symptoms.update(tier.get("optional_symptoms", []))
        if "myalgia" not in all_symptoms:
            feedback_parts.append("\U0001f4a1 **Tip:** Calf myalgia is a hallmark symptom of leptospirosis that helps distinguish it from other post-flood febrile illnesses.")

        # Check if lab confirmation is set for confirmed tier
        if not confirmed.get("lab_required"):
            feedback_parts.append("\U0001f4a1 **Tip:** Confirmed cases typically require lab evidence (PCR, MAT, or IgM ELISA).")

    # General sensitivity/specificity feedback
    filled = sum(len(tier.get("required_any", [])) + len(tier.get("optional_symptoms", [])) for tier in tiers.values())
    if filled <= 2 and not feedback_parts:
        feedback_parts.append(f"\u26a0\ufe0f The definition is broad and may capture many non-{disease_name} cases (low specificity).")
    elif filled >= 8:
        feedback_parts.append(f"\u26a0\ufe0f The definition is very restrictive and may miss true {disease_name} cases (low sensitivity).")

    if not feedback_parts:
        return f"\u2705 Your case definition includes key elements for {disease_name}. Monitor sensitivity/specificity as you collect data."

    return "\n\n".join(feedback_parts)
