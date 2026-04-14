import streamlit as st
import pandas as pd
from i18n.translate import t
from config.scenarios import load_scenario_content, load_scenario_config
from config.locations import get_current_scenario_id
from data_utils.case_definition import (
    build_case_definition_summary, record_case_definition_version,
    case_definition_feedback, get_symptomatic_column, get_day1_assets,
    scenario_config_label
)
from state.resources import format_resource_cost
import outbreak_logic as jl
import day1_utils


def view_overview():
    truth = st.session_state.truth

    # Use scenario-specific title
    scenario_name = st.session_state.get("current_scenario_name", "Outbreak Investigation")
    st.title(f"{scenario_name}")
    st.subheader(f"Day {st.session_state.current_day} briefing")

    from views.sitrep import day_briefing_text, day_task_list
    from views.journal import view_evidence_board
    from data_utils.charts import get_initial_cases, make_epi_curve, make_village_map
    from datetime import date

    st.markdown(day_briefing_text(st.session_state.current_day))

    day_task_list(st.session_state.current_day)

    # Evidence Board
    st.markdown("---")
    view_evidence_board()

    # Session save/load guidance
    with st.expander("ℹ️ Saving Your Progress"):
        st.markdown("""
        **Working on this investigation over multiple sessions?**

        - Use **💾 Save** in the sidebar to download your progress as a file
        - Save files include all your decisions, interviews, lab results, and investigation notes
        - To continue later, use **📂 Load** to upload your save file
        - Save regularly to avoid losing work!
        - You can share save files with team members or facilitators

        *Tip: Save files are named with the current day and timestamp for easy identification.*
        """)

    # If the user tried to advance but prerequisites are missing, show them here.
    if st.session_state.get("advance_missing_tasks"):
        st.warning(t("missing_tasks_title", default="Missing tasks before you can advance:"))
        for item in st.session_state.advance_missing_tasks:
            # Support both legacy plain-English strings and new i18n keys
            if isinstance(item, str) and (" " not in item) and ("." in item):
                st.markdown(f"- {t(item, default=item)}")
            else:
                st.markdown(f"- {item}")
        st.session_state.advance_missing_tasks = []

    st.markdown("---")
    st.markdown("### Situation overview")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Line list (initial reported cases)")
        line_list = get_initial_cases(truth)
        st.dataframe(line_list)
        st.session_state.line_list_viewed = True
        estimated_cases = st.session_state.decisions.get("line_list_case_count")
        if estimated_cases is not None:
            st.caption(f"Adjusted line list estimate (after data quality): {estimated_cases} cases.")

    with col2:
        st.markdown("#### Epi curve")
        epi_fig = make_epi_curve(truth)
        st.plotly_chart(epi_fig, use_container_width=True)

    st.markdown("### Geographic Distribution of Cases")
    map_fig = make_village_map(truth)
    st.plotly_chart(map_fig, use_container_width=True)

    # Day 1: Case Definition and Initial Hypotheses
    if st.session_state.current_day == 1:
        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Case Definition")

            # Show scenario-specific case definition template
            scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
            with st.expander("📋 Case Definition Guidelines", expanded=False):
                template_content = load_scenario_content(scenario_id, "case_definition_template")
                st.markdown(template_content)
            template_sections = day1_utils.parse_case_definition_template(template_content)
            if st.button("Load WHO-style template", key="load_who_template"):
                st.session_state.case_def_suspected_clinical = template_sections.get("suspected", "")
                st.session_state.case_def_probable_clinical = template_sections.get("probable", "")
                st.session_state.case_def_confirmed_clinical = template_sections.get("confirmed", "")
                st.success("Template loaded into the builder.")

            scenario_config = st.session_state.get("scenario_config", {}) or {}
            symptom_map = {s.get("label"): s.get("key") for s in scenario_config.get("symptoms", [])}
            symptom_labels = list(symptom_map.keys())
            symptom_descriptions = {s.get("label"): s.get("description", "") for s in scenario_config.get("symptoms", [])}
            exclusion_options = scenario_config.get("exclusion_conditions", [])
            village_options = truth["villages"]["village_id"].tolist()

            # Show symptom glossary to help players understand medical terms
            with st.expander("📖 Symptom Glossary (click to expand)", expanded=False):
                st.markdown("**Understanding the clinical criteria:**")
                for label, desc in symptom_descriptions.items():
                    if desc:
                        st.markdown(f"- **{label}**: {desc}")
                epi_fields = scenario_config.get("epi_link_fields", [])
                if epi_fields:
                    st.markdown("\n**Epidemiological link (exposure criteria):**")
                    for field in epi_fields:
                        if field.get("description"):
                            st.markdown(f"- **{field.get('label')}**: {field.get('description')}")

            # Show case cards to help players think through borderline cases
            assets = get_day1_assets()
            case_cards = assets.get("case_cards", [])
            if case_cards:
                with st.expander("🃏 Case Cards - Practice Classification", expanded=False):
                    st.markdown("""
**What are case cards?** These are example patient scenarios to help you think through
how your case definition would classify different presentations. Review them to test
whether your definition captures the right cases.
                    """)
                    for card in case_cards:
                        with st.container():
                            st.markdown(f"**{card.get('case_id')}: {card.get('title')}**")
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"- *Clinical:* {card.get('clinical', 'N/A')}")
                                st.markdown(f"- *Exposure:* {card.get('exposure', 'N/A')}")
                            with col_b:
                                st.markdown(f"- *Lab:* {card.get('lab', 'N/A')}")
                                st.markdown(f"- *Missing data:* {card.get('missing_data', 'N/A')}")
                            st.markdown("---")

            # What makes a good case definition?
            with st.expander("What makes a good case definition?", expanded=False):
                st.markdown("""
A strong case definition has:
- **Person**: Who is affected (age, occupation, exposure history)
- **Place**: Geographic boundary (which villages/wards)
- **Time**: Onset date window
- **Clinical criteria**: Symptoms that distinguish cases from non-cases
- **Tiered classification**: Suspected -> Probable -> Confirmed, with increasing specificity
- **Exclusions**: Conditions that rule out the disease

Each tier builds on the previous one. Suspected cases have clinical criteria only,
probable cases add an epidemiological link, and confirmed cases require laboratory evidence.
                """)

            # Worked example from a different disease
            with st.expander("See an Example: Cholera Case Definition", expanded=False):
                st.markdown("""
**Context:** A cholera outbreak in a coastal district after flooding.

| Tier | Clinical | Epi Link | Lab |
|------|----------|----------|-----|
| **Suspected** | Acute watery diarrhea + dehydration | Not required | Not required |
| **Probable** | Same as suspected | Contact with confirmed case OR exposure to contaminated water source | Not required |
| **Confirmed** | Same as suspected | Not required | *Vibrio cholerae* O1 or O139 isolated from stool |

**Time:** Onset between March 1-31, 2025
**Place:** Coastal wards A, B, C
**Exclusions:** Known chronic diarrheal disease, recent antibiotic use causing GI symptoms
                """)

            st.markdown("#### Time/Place Boundaries")
            defaults = scenario_config.get("case_definition_defaults", {})
            c1, c2 = st.columns(2)
            with c1:
                st.date_input(
                    "Onset start",
                    key="case_def_onset_start",
                    value=pd.to_datetime(defaults.get("onset_start", date.today())).date(),
                )
            with c2:
                st.date_input(
                    "Onset end",
                    key="case_def_onset_end",
                    value=pd.to_datetime(defaults.get("onset_end", date.today())).date(),
                )
            st.multiselect(
                "Affected villages/wards",
                options=village_options,
                default=defaults.get("villages", village_options),
                key="case_def_villages",
            )
            st.multiselect(
                "Explicit exclusions (rule-outs)",
                options=exclusion_options,
                default=exclusion_options,
                key="case_def_exclusions",
            )

            def _tier_builder(tier_key: str, title: str) -> dict:
                # Completeness indicator
                has_clinical = bool(st.session_state.get(f"{tier_key}_required_any"))
                has_epi = st.session_state.get(f"{tier_key}_epi_required", False)
                has_lab = st.session_state.get(f"{tier_key}_lab_required", False)
                if has_clinical and (has_epi or has_lab or tier_key == "case_def_suspected"):
                    badge = "🟢"
                elif has_clinical:
                    badge = "🟡"
                else:
                    badge = "⚪"
                st.markdown(f"#### {badge} {title} Case")

                required_any = st.multiselect(
                    "At least one required symptom",
                    options=symptom_labels,
                    key=f"{tier_key}_required_any",
                )
                # Inline validation
                if not required_any:
                    if tier_key == "case_def_suspected":
                        st.caption("*Tip: Suspected cases typically need at least one clinical criterion (e.g., fever).*")
                    elif tier_key == "case_def_confirmed":
                        st.caption("*Tip: Confirmed cases should include clinical criteria plus lab evidence.*")

                optional_symptoms = st.multiselect(
                    "Additional symptoms (optional)",
                    options=[s for s in symptom_labels if s not in required_any],
                    key=f"{tier_key}_optional",
                )
                min_optional = st.number_input(
                    "Minimum optional symptoms",
                    min_value=0,
                    max_value=len(optional_symptoms),
                    value=0,
                    step=1,
                    key=f"{tier_key}_min_optional",
                )
                epi_required = st.checkbox(
                    "Require epidemiological link",
                    value=(tier_key == "probable"),
                    key=f"{tier_key}_epi_required",
                    help="Epidemiological link = documented exposure (e.g., floodwater contact, cleanup work) within the incubation period. See Symptom Glossary above for exposure types.",
                )
                # Inline validation for probable
                if tier_key == "case_def_probable" and not epi_required:
                    st.caption("*Tip: Probable cases often require an epidemiological link to strengthen classification.*")

                lab_required = st.checkbox(
                    "Require lab evidence",
                    value=(tier_key == "confirmed"),
                    key=f"{tier_key}_lab_required",
                )
                # Inline validation for confirmed
                if tier_key == "case_def_confirmed" and not lab_required:
                    st.caption("*Tip: Confirmed cases typically require laboratory evidence.*")

                lab_tests = st.multiselect(
                    "Accepted lab tests",
                    options=[lt.get("code") for lt in scenario_config.get("lab_tests", [])],
                    key=f"{tier_key}_lab_tests",
                    disabled=not lab_required,
                )
                return {
                    "required_any": [symptom_map[label] for label in required_any],
                    "optional_symptoms": [symptom_map[label] for label in optional_symptoms],
                    "min_optional": int(min_optional),
                    "epi_link_required": epi_required,
                    "lab_required": lab_required,
                    "lab_tests": lab_tests,
                }

            suspected = _tier_builder("case_def_suspected", "Suspected")
            probable = _tier_builder("case_def_probable", "Probable")
            confirmed = _tier_builder("case_def_confirmed", "Confirmed")

            current_case_def = {
                "time_window": {
                    "start": str(st.session_state.get("case_def_onset_start")),
                    "end": str(st.session_state.get("case_def_onset_end")),
                },
                "villages": st.session_state.get("case_def_villages", []),
                "exclusions": st.session_state.get("case_def_exclusions", []),
                "tiers": {
                    "suspected": suspected,
                    "probable": probable,
                    "confirmed": confirmed,
                },
            }

            st.info(case_definition_feedback(current_case_def))

            rationale = st.text_area("Revision rationale (optional)", key="case_def_rationale", height=60)

            if st.button("Save Case Definition", type="primary"):
                if not any(
                    value.strip()
                    for tier in current_case_def.values()
                    for value in tier.values()
                ):
                    st.error("Please enter at least one case definition element before saving.")
                else:
                    st.session_state.case_definition_builder = current_case_def
                    st.session_state.decisions["case_definition_structured"] = current_case_def
                    st.session_state.decisions["case_definition_text"] = build_case_definition_summary(current_case_def)
                    st.session_state.decisions["case_definition"] = current_case_def
                    st.session_state.decisions["scenario_id"] = scenario_id
                    st.session_state.decisions["scenario_config"] = scenario_config
                    st.session_state.case_definition_written = True
                    record_case_definition_version(current_case_def, rationale=rationale.strip())
                    st.success("✅ Case definition saved!")

            if st.session_state.case_definition_written:
                st.info("✓ Case definition recorded")
                st.markdown("**Saved case definition:**")
                st.text_area(
                    "Case definition (saved)",
                    value=st.session_state.decisions.get("case_definition_text", ""),
                    height=160,
                    key="case_definition_saved_display",
                    disabled=True,
                    label_visibility="collapsed",
                )

        with col2:
            st.markdown("### Initial Hypotheses")
            st.caption("Based on what you know so far, what might be causing this outbreak? (At least 1 required)")

            # Show scenario-specific hypothesis examples
            with st.expander("💡 Hypothesis Development Guide", expanded=False):
                hypothesis_content = load_scenario_content(scenario_id, "hypothesis_examples")
                st.markdown(hypothesis_content)

            with st.form("hypotheses_form"):
                h1 = st.text_input("Hypothesis 1 (required):")
                h2 = st.text_input("Hypothesis 2 (optional):")
                h3 = st.text_input("Hypothesis 3 (optional):")
                h4 = st.text_input("Hypothesis 4 (optional):")

                if st.form_submit_button("Save Hypotheses"):
                    hypotheses = [h for h in [h1, h2, h3, h4] if h.strip()]
                    if len(hypotheses) >= 1:
                        st.session_state.initial_hypotheses = hypotheses
                        st.session_state.hypotheses_documented = True
                        st.success(f"✅ {len(hypotheses)} hypothesis(es) saved!")
                    else:
                        st.error("Please enter at least one hypothesis.")

            if st.session_state.hypotheses_documented:
                st.info(f"✓ {len(st.session_state.initial_hypotheses)} hypothesis(es) recorded")
                st.markdown("**Saved hypotheses:**")
                for hypothesis in st.session_state.initial_hypotheses:
                    st.markdown(f"- {hypothesis}")
