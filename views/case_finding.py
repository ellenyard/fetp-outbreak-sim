import streamlit as st
import pandas as pd
from i18n.translate import t
from config.locations import get_current_scenario_id
from data_utils.clinic import (
    generate_clinic_records, create_found_case_records,
    add_found_cases_to_truth, render_clinic_record
)
from data_utils.case_definition import get_day1_assets, get_symptomatic_column, scenario_config_label
from state.resources import spend_time, TIME_COSTS
import outbreak_logic as jl
import day1_utils


def view_case_finding():
    """View for reviewing clinic records and finding additional cases."""
    from data_utils.case_definition import scenario_config_label, record_case_definition_version
    from data_utils.clinic import generate_hospital_records, render_hospital_record
    from datetime import date
    from data_utils.clinic import create_structured_case_records

    # Back button at the top for easy navigation
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔙 Return to Clinic", key="return_to_clinic_from_cf"):
            scenario_type = st.session_state.get("current_scenario_type", "je")
            if scenario_type == "lepto":
                st.session_state.current_location = "rhu_clinic"
                st.session_state.current_area = "Ward Northbend"
            else:
                st.session_state.current_location = "nalu_health_center"
                st.session_state.current_area = "Nalu Village"
            st.session_state.current_view = "location"
            st.rerun()

    st.header("Case Finding")
    scenario_type = st.session_state.get("current_scenario_type", "je")
    case_label = scenario_config_label(scenario_type)

    # Tabs for different record sources
    tab1, tab2, tab3 = st.tabs(["Clinic Records", "Hospital Records", "Multi-source Sweep"])

    with tab1:
        clinic_name = "Northbend Rural Health Unit" if scenario_type == "lepto" else "Nalu Health Center"
        st.subheader(f"{clinic_name} - Patient Register Review")

        if not st.session_state.clinic_abstraction_submitted:
            st.info("Start with the Clinic Log Abstraction step to build your clean line list.")
            if st.button("Go to Clinic Log Abstraction", key="go_to_clinic_abstraction"):
                st.session_state.current_view = "clinic_log_abstraction"
                st.rerun()

        # Resource display and cost warning
        time_cost = TIME_COSTS["clinic_records_review"]

        col1, col2, col3 = st.columns(3)
        with col1:
            time_display = f":red[{st.session_state.time_remaining}h]" if st.session_state.time_remaining < 0 else f"{st.session_state.time_remaining}h"
            st.markdown(f"**⏱️ Time Remaining**  \n{time_display}")
        with col2:
            st.metric("📋 Activity Cost", f"{time_cost}h")
        with col3:
            if st.session_state.clinic_records_reviewed:
                st.success("✅ Completed")
            else:
                st.info("Not yet completed")

        # Check if already done or if enough time
        if not st.session_state.clinic_records_reviewed:
            if st.session_state.time_remaining < time_cost:
                st.error(f"⚠️ Not enough time to review clinic records. Need {time_cost}h, have {st.session_state.time_remaining}h.")
                st.info("Advance to the next day to get more time, or prioritize other activities.")
            else:
                st.markdown(f"""
                You've obtained permission to review records from the **{clinic_name}**.
                Look through these handwritten clinic notes to identify potential cases
                that may not have been reported to the district hospital.

                **Your task:** Review each record and select any that might be related to the outbreak.
                Consider: fever, syndrome-specific symptoms, and geographic/temporal clustering.
                """)

                st.info(f"💡 Tip: Not every fever is {case_label}. Look for the combination of fever AND key syndrome features.")

                # Generate clinic records
                if 'clinic_records' not in st.session_state:
                    st.session_state.clinic_records = generate_clinic_records()

                records = st.session_state.clinic_records

                # Show records in columns
                st.markdown("---")
                st.markdown("### Patient Register (June 2025)")

                col1, col2 = st.columns(2)

                selected = []
                for i, record in enumerate(records):
                    with col1 if i % 2 == 0 else col2:
                        render_clinic_record(record, show_checkbox=False)
                        is_selected = st.checkbox(
                            f"Potential {case_label} case",
                            key=f"clinic_select_{record['record_id']}",
                            value=record['record_id'] in st.session_state.selected_clinic_cases
                        )
                        if is_selected:
                            selected.append(record['record_id'])

                st.markdown("---")

                # Summary and submission
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"**Selected records:** {len(selected)}")
                    if selected:
                        st.caption(", ".join(selected))

                with col2:
                    if st.button(f"Submit Case Finding (costs {time_cost}h)", type="primary"):
                        # Deduct time
                        spend_time(time_cost, "Clinic records review")

                        st.session_state.selected_clinic_cases = selected
                        st.session_state.clinic_records_reviewed = True

                        # Calculate score
                        true_positives = sum(1 for rid in selected
                                           for r in records if r['record_id'] == rid and r.get('is_aes'))
                        false_positives = len(selected) - true_positives

                        # Count total true cases
                        total_aes = sum(1 for r in records if r.get('is_aes'))
                        false_negatives = total_aes - true_positives

                        st.session_state.case_finding_score = {
                            'true_positives': true_positives,
                            'false_positives': false_positives,
                            'false_negatives': false_negatives,
                            'total_aes': total_aes,
                            'selected': len(selected)
                        }

                        # Add found cases to the line list and study data
                        if true_positives > 0:
                            cases_added = add_found_cases_to_truth(
                                st.session_state.truth,
                                records,
                                selected,
                                session_state=st.session_state
                            )
                            st.session_state.found_cases_added = True
                            st.session_state.case_finding_score['cases_added'] = cases_added

                        # Log the case finding event
                        jl.log_event(
                            event_type='case_finding',
                            location_id=None,
                            cost_time=0,
                            cost_budget=0,
                            payload={
                                'true_positives': true_positives,
                                'false_positives': false_positives,
                                'false_negatives': false_negatives,
                                'total_aes': total_aes,
                                'selected_count': len(selected),
                                'cases_added': true_positives
                            }
                        )

                        st.success(f"✅ Case finding complete! You identified {true_positives} of {total_aes} potential {case_label} cases.")

                        if false_positives > 0:
                            st.warning(f"⚠️ {false_positives} record(s) you selected may not be {case_label} cases.")
                        if false_negatives > 0:
                            st.info(f"📝 {false_negatives} potential {case_label} case(s) were missed. Review records with fever + key syndrome symptoms.")

                        st.rerun()
        else:
            # Show results if already completed
            if st.session_state.case_finding_score:
                score = st.session_state.case_finding_score
                st.markdown("### Your Case Finding Results")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("True Positives", score['true_positives'])
                with col2:
                    st.metric("False Positives", score['false_positives'])
                with col3:
                    sensitivity = (score['true_positives'] / score['total_aes'] * 100) if score['total_aes'] > 0 else 0
                    st.metric("Sensitivity", f"{sensitivity:.0f}%")

                if score['true_positives'] > 0:
                    cases_added = score.get('cases_added', score['true_positives'])
                    st.success(f"✅ {cases_added} additional cases have been added to the line list and are available for analysis in Descriptive Epidemiology and Study Design.")

    with tab2:
        st.subheader("District Hospital - Detailed Medical Records")
        scenario_type = st.session_state.get("current_scenario_type", "je")
        if scenario_type == "lepto":
            st.markdown("""
            The District Hospital has provided detailed medical records for 2 of the admitted cases.
            These records contain more clinical information that may help characterize the outbreak.
            """)
        else:
            st.markdown("""
            The District Hospital has provided detailed medical records for 2 of the admitted AES cases.
            These records contain more clinical information that may help characterize the outbreak.
            """)

        hospital_records = generate_hospital_records()

        record_choice = st.selectbox(
            "Select patient record to review:",
            options=list(hospital_records.keys()),
            format_func=lambda x: f"{hospital_records[x]['name']} ({hospital_records[x]['age']}, {hospital_records[x]['village']})"
        )

        if record_choice:
            render_hospital_record(hospital_records[record_choice])

            st.markdown("---")
            st.markdown("### Chart Abstraction")
            st.caption("Capture structured clinical details and consider differential diagnoses.")

            review = st.session_state.medical_chart_reviews.get(record_choice, {})
            col1, col2 = st.columns(2)
            with col1:
                onset_date = st.date_input(
                    "Symptom onset date",
                    value=review.get("onset_date", date.today()),
                    key=f"chart_onset_{record_choice}",
                )
                fever_duration = st.number_input(
                    "Fever duration (days)",
                    min_value=0,
                    max_value=30,
                    value=review.get("fever_duration", 0),
                    key=f"chart_fever_{record_choice}",
                )
                rash_features = st.text_input(
                    "Rash characteristics or syndrome features",
                    value=review.get("rash_features", ""),
                    key=f"chart_rash_{record_choice}",
                )
            with col2:
                hydration_resp = st.selectbox(
                    "Dehydration / respiratory status",
                    ["Normal", "Mild dehydration", "Severe dehydration", "Respiratory distress"],
                    index=["Normal", "Mild dehydration", "Severe dehydration", "Respiratory distress"].index(
                        review.get("hydration_resp", "Normal")
                    ),
                    key=f"chart_hydration_{record_choice}",
                )
                vitals = st.text_input(
                    "Key vitals (Temp/HR/BP)",
                    value=review.get("vitals", ""),
                    key=f"chart_vitals_{record_choice}",
                )
                clinical_course = st.selectbox(
                    "Clinical course",
                    ["Improving", "Stable", "Worsening", "Hospitalized", "Died"],
                    index=["Improving", "Stable", "Worsening", "Hospitalized", "Died"].index(
                        review.get("clinical_course", "Stable")
                    ),
                    key=f"chart_course_{record_choice}",
                )

            st.markdown("### Differential Diagnosis Prompts")
            differential_prompts = day1_utils.get_differential_prompts(scenario_type)
            for item in differential_prompts:
                st.markdown(f"- **{item['dx']}** — *Support:* {item['supporting']} | *Against:* {item['against']}")

            dx_options = [item["dx"] for item in differential_prompts]
            leading_dx = st.multiselect(
                "Select 1–2 leading differentials",
                options=dx_options,
                default=review.get("leading_differentials", []),
                max_selections=2,
                key=f"chart_dx_{record_choice}",
            )
            justification = st.text_area(
                "Justify your leading differentials using chart fields",
                value=review.get("justification", ""),
                key=f"chart_justify_{record_choice}",
            )

            if st.button("Save Chart Abstraction", type="primary", key=f"save_chart_{record_choice}"):
                if not leading_dx or not justification.strip():
                    st.error("Select 1–2 differentials and provide justification.")
                else:
                    st.session_state.medical_chart_reviews[record_choice] = {
                        "onset_date": str(onset_date) if onset_date else "Unknown",
                        "fever_duration": fever_duration,
                        "rash_features": rash_features,
                        "hydration_resp": hydration_resp,
                        "vitals": vitals,
                        "clinical_course": clinical_course,
                        "leading_differentials": leading_dx,
                        "justification": justification.strip(),
                    }
                st.success("✅ Chart abstraction saved.")

    with tab3:
        st.subheader("Definition-driven case finding")
        assets = get_day1_assets()
        sources = day1_utils.get_case_finding_sources(assets)
        case_def = st.session_state.decisions.get("case_definition_structured")
        scenario_config = st.session_state.get("scenario_config", {}) or {}

        if not case_def:
            st.info("Save a working case definition to run the sweep.")
            return

        st.caption("Run case finding across multiple sources. You can re-run after refining the case definition.")
        if st.button("Run case finding sweep", type="primary"):
            st.session_state.case_finding_results = day1_utils.run_case_finding(
                sources,
                case_def,
                scenario_config,
                current_day=int(st.session_state.get("current_day", 1)),
            )

        results = st.session_state.get("case_finding_results")
        if results:
            for source in results.get("sources", []):
                with st.expander(f"{source.get('label', 'Source')}"):
                    if source.get("pending"):
                        st.info("Reports pending due to reporting delay.")
                        continue
                    matches = source.get("matches", [])
                    st.metric("Matches", len(matches))
                    if matches:
                        st.dataframe(pd.DataFrame(matches), use_container_width=True, hide_index=True)
                        if st.button(f"Add {len(matches)} matches to line list", key=f"add_{source.get('source_id')}"):
                            new_inds, new_hhs = create_structured_case_records(
                                matches,
                                st.session_state.truth["individuals"],
                                st.session_state.truth["households"],
                                scenario_config,
                            )
                            if not new_inds.empty:
                                st.session_state.truth["individuals"] = pd.concat(
                                    [st.session_state.truth["individuals"], new_inds], ignore_index=True
                                )
                                st.session_state.truth["households"] = pd.concat(
                                    [st.session_state.truth["households"], new_hhs], ignore_index=True
                                )
                                st.session_state['found_case_individuals'] = new_inds
                                st.session_state['found_case_households'] = new_hhs
                                st.session_state.found_cases_added = True
                                st.success("Added cases to line list.")

    if st.session_state.clinic_records_reviewed:
        st.markdown("---")
        st.markdown("Ready to debrief your case finding?")
        if st.button("Go to Case-finding Debrief", type="primary"):
            st.session_state.current_view = "case_finding_debrief"
            st.rerun()


def view_case_finding_debrief():
    import time
    from data_utils.case_definition import record_case_definition_version

    st.title("Case-finding Debrief")

    # Explain the purpose of this step
    st.info("""
**What is this?** This debrief helps you evaluate your case definition's performance by comparing
it against actual cases in the clinic records.

**Why does it matter?** Case definitions are iterative - you refine them based on how well they
identify true cases while excluding non-cases. This is a key skill in outbreak investigation.
    """)

    with st.expander("📖 Understanding False Positives & Negatives", expanded=False):
        st.markdown("""
**False Positive:** Your definition matched this patient, but they don't actually have the disease.
- *Too many false positives* → Your definition is too broad (low specificity)
- *Action:* Add more specific criteria or require more symptoms

**False Negative:** Your definition missed this patient, but they actually have the disease.
- *Too many false negatives* → Your definition is too restrictive (low sensitivity)
- *Action:* Relax criteria or accept fewer required symptoms

**The tradeoff:** Early in an outbreak, you may want higher sensitivity (catch all cases).
As you learn more, you can increase specificity (reduce false alarms).
        """)

    assets = get_day1_assets()
    entries = assets.get("clinic_log_entries", [])
    if not st.session_state.clinic_line_list:
        st.warning("Complete the clinic log abstraction first.")
        return

    case_def = st.session_state.decisions.get("case_definition_structured") or st.session_state.case_definition_builder
    if not case_def:
        st.warning("Save a working case definition first.")
        return
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    if not case_def.get("tiers"):
        st.warning("Your case definition is missing tiered symptom criteria.")

    answer_key = {entry["entry_id"]: entry for entry in entries}
    matches = []
    for row in st.session_state.clinic_line_list:
        patient_id = row.get("patient_id", "")
        classification = day1_utils.match_case_definition_structured(row, case_def, scenario_config)
        is_match = classification in {"suspected", "probable", "confirmed"}
        truth_case = answer_key.get(patient_id, {}).get("truth_case")
        matches.append({
            "patient_id": patient_id,
            "is_match": is_match,
            "truth_case": truth_case,
            "raw_text": answer_key.get(patient_id, {}).get("raw_text", "Unknown entry"),
        })

    match_count = sum(1 for m in matches if m["is_match"])
    non_match_count = len(matches) - match_count
    st.metric("Matches working case definition", match_count)
    st.metric("Does not match", non_match_count)

    accuracy = st.session_state.clinic_abstraction_feedback.get("accuracy_percent", 100) if st.session_state.get("clinic_abstraction_feedback") else 100
    estimated_cases = int(round(match_count * (accuracy / 100))) if match_count else 0
    st.metric("Estimated cases after data quality adjustment", estimated_cases)

    false_positives = [m for m in matches if m["is_match"] and m["truth_case"] is False][:3]
    false_negatives = [m for m in matches if not m["is_match"] and m["truth_case"] is True][:3]

    st.markdown("### Likely false positives")
    st.caption("These patients matched your definition but may not have the disease. Review them to see if your definition is too broad.")
    fp_options = [f"{m['patient_id']}: {m['raw_text']}" for m in false_positives]
    if fp_options:
        fp_selected = st.multiselect("Select cases you believe are false positives", options=fp_options)
    else:
        st.success("No obvious false positives found - your definition may have good specificity.")
        fp_selected = []

    st.markdown("### Likely false negatives")
    st.caption("These patients didn't match your definition but may actually have the disease. Review them to see if your definition is too restrictive.")
    fn_options = [f"{m['patient_id']}: {m['raw_text']}" for m in false_negatives]
    if fn_options:
        fn_selected = st.multiselect("Select cases you believe are false negatives", options=fn_options)
    else:
        st.success("No obvious false negatives found - your definition may have good sensitivity.")
        fn_selected = []

    st.markdown("---")
    st.markdown("### Decision")
    st.caption("Based on the above review, should you revise your case definition? If yes, return to the Overview page to make changes.")
    revise_decision = st.radio("Revise case definition?", options=["No", "Yes"], horizontal=True)
    rationale = st.text_area("Rationale", height=80)

    if st.button("Save Debrief", type="primary"):
        st.session_state.case_finding_debrief = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M"),
            "false_positive_examples": fp_selected,
            "false_negative_examples": fn_selected,
            "revise_decision": revise_decision,
            "rationale": rationale.strip(),
            "data_quality_accuracy": accuracy,
            "estimated_case_count": estimated_cases,
        }
        st.session_state.decisions["line_list_case_count"] = estimated_cases
        if accuracy < 80:
            st.session_state.decisions["data_quality_flag"] = True
        if revise_decision == "Yes" and case_def:
            record_case_definition_version(case_def, rationale=rationale.strip())
        st.success("✅ Debrief saved.")


def view_day1_lab_brief():
    st.title("Day 1 Lab Mini-Brief")
    st.caption("Review preliminary lab findings and note limitations.")

    st.session_state.day1_lab_brief_viewed = True

    assets = get_day1_assets()
    lab_brief = assets.get("lab_brief", {})
    st.markdown(lab_brief.get("summary", ""))

    results = lab_brief.get("results", [])
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True)

    st.markdown("**Limitations**")
    for item in lab_brief.get("limitations", []):
        st.markdown(f"- {item}")

    st.markdown("**Next steps**")
    for item in lab_brief.get("next_steps", []):
        st.markdown(f"- {item}")

    interpretation = st.text_area("Your interpretation", height=80, key="day1_lab_interpretation")
    if st.button("Save Lab Brief Notes", type="primary"):
        st.session_state.day1_lab_brief_viewed = True
        st.session_state.day1_lab_brief_notes = interpretation.strip()
        st.success("✅ Lab brief notes saved.")


def view_triangulation_checkpoint():
    st.title("Triangulation Checkpoint")
    st.caption("Summarize epi, clinical, and lab evidence to define working hypotheses for Day 2.")

    with st.form("triangulation_form"):
        epi_summary = st.text_area("Epi evidence summary", height=80)
        clinical_summary = st.text_area("Clinical evidence summary", height=80)
        lab_summary = st.text_area("Lab evidence summary", height=80)
        hypothesis_1 = st.text_input("Working hypothesis 1")
        hypothesis_2 = st.text_input("Working hypothesis 2 (optional)")
        evidence_support = st.text_area("Evidence supporting hypotheses", height=80)
        next_actions = st.text_area("High-priority data needs / Day 2 actions (2 items)", height=80)

        if st.form_submit_button("Save Triangulation Checkpoint"):
            st.session_state.triangulation_checkpoint = {
                "epi_summary": epi_summary.strip(),
                "clinical_summary": clinical_summary.strip(),
                "lab_summary": lab_summary.strip(),
                "hypothesis_1": hypothesis_1.strip(),
                "hypothesis_2": hypothesis_2.strip(),
                "evidence_support": evidence_support.strip(),
                "next_actions": next_actions.strip(),
            }
            st.session_state.triangulation_completed = True
            st.success("✅ Triangulation checkpoint saved.")

def view_clinic_register_scan():
    """Day 1: Clinic Register Scan - Review logbook and select suspect cases."""

    st.title("Clinic Register Scan")
    st.caption("Day 1: Review the clinic logbook and identify potential cases")
    scenario_type = st.session_state.get("current_scenario_type", "je")

    # Back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Return to Map", key="return_from_clinic_register"):
            st.session_state.current_view = "map"
            st.rerun()

    st.markdown("---")

    if scenario_type == "lepto":
        st.markdown("### Raw Logbook from Northbend Rural Health Unit")
    else:
        st.markdown("### Raw Logbook from Nalu Health Center")
    if scenario_type == "lepto":
        st.caption("Review these handwritten records and check any that you suspect might be outbreak-related cases.")
    else:
        st.caption("Review these handwritten records and check any that you suspect might be AES cases.")

    # Generate clinic records if not already done
    if 'clinic_records' not in st.session_state:
        st.session_state.clinic_records = generate_clinic_records()

    records = st.session_state.clinic_records

    # Create a dataframe for display
    display_df = pd.DataFrame(records)

    # Add a suspect case checkbox column
    st.markdown("#### Patient Register (June 2025)")

    # Initialize manual_cases if needed
    if not isinstance(st.session_state.manual_cases, list):
        st.session_state.manual_cases = []

    # Display records with checkboxes
    header_cols = st.columns([1, 2, 1, 1, 5])
    header_cols[0].markdown("**Suspect?**")
    header_cols[1].markdown("**Record ID**")
    header_cols[2].markdown("**Date**")
    header_cols[3].markdown("**Age**")
    header_cols[4].markdown("**Patient / Village**")

    selected_records = []
    for i, record in enumerate(records):
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 5])

            # Checkbox
            is_checked = record['record_id'] in st.session_state.manual_cases
            check = col1.checkbox(
                "Suspect?",
                key=f"suspect_{record['record_id']}",
                value=is_checked,
                label_visibility="collapsed"
            )

            if check:
                selected_records.append(record['record_id'])

            # Record details
            col2.write(f"**{record['record_id']}**")
            col3.write(record['date'])
            col4.write(record['age'])
            col5.write(f"{record['patient']} - {record['village']}")

            # Complaint and notes in full width
            st.caption(f"**Complaint:** {record['complaint']}")
            st.caption(f"**Notes:** {record['notes']}")
            st.divider()

    st.session_state.manual_cases = selected_records

    st.markdown("---")

    # Summary and action button
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f"**Checked records:** {len(st.session_state.manual_cases)}")
        if st.session_state.manual_cases:
            st.caption(f"IDs: {', '.join(st.session_state.manual_cases)}")

    with col2:
        if st.button("Add Checked to Line List", type="primary"):
            if st.session_state.manual_cases:
                # Calculate scoring
                true_positives = sum(1 for rid in st.session_state.manual_cases
                                   for r in records if r['record_id'] == rid and r.get('is_aes'))
                false_positives = len(st.session_state.manual_cases) - true_positives
                total_aes = sum(1 for r in records if r.get('is_aes'))
                false_negatives = total_aes - true_positives

                case_label = scenario_config_label(st.session_state.get("current_scenario_type", "je"))
                st.success(f"✅ Added {len(st.session_state.manual_cases)} records to your line list!")
                st.info(f"📊 You identified {true_positives} of {total_aes} true {case_label} cases.")

                if false_positives > 0:
                    st.warning(f"⚠️ {false_positives} selected record(s) may not be {case_label}.")
                if false_negatives > 0:
                    st.caption(f"💡 {false_negatives} potential {case_label} case(s) were not selected.")

                # Mark as reviewed
                st.session_state.clinic_records_reviewed = True
            else:
                st.error("No records selected!")


def view_nalu_child_register():
    """View Nalu Health Center Child Register - 38 entries with new cases.

    NOTE: This view is specific to the JE/AES (Sidero Valley) scenario.
    For the Leptospirosis scenario, this view is not applicable and will
    show a redirect message.
    """
    scenario_type = st.session_state.get("current_scenario_type", "je")
    if scenario_type != "je":
        st.warning("This register is not available for the current scenario.")
        if st.button("Return to Map"):
            st.session_state.current_view = "map"
            st.rerun()
        return

    from outbreak_logic import get_nalu_child_register, get_nalu_medical_record

    st.title("Nalu Health Center - Child Register")
    st.caption("Review the child health register to identify potential cases")

    # Back button
    if st.button("Return to Map", key="return_from_nalu_register"):
        st.session_state.current_view = "map"
        st.rerun()

    st.markdown("---")

    # Get the register
    register = get_nalu_child_register()

    # Convert to DataFrame for display
    df = pd.DataFrame(register)

    # Instructions
    st.markdown("""
    ### Instructions
    - Review the child register entries below
    - Look for patterns in complaints and outcomes
    - Click "View Chart" to see detailed medical records for key patients
    - Identify potential AES cases based on clinical presentation
    """)

    st.markdown("---")

    # Display in table format with highlighting
    st.markdown("### Child Register (38 entries)")

    # Initialize unlocked charts if not exists
    if 'unlocked_nalu_charts' not in st.session_state:
        st.session_state['unlocked_nalu_charts'] = []

    # Show table with color coding
    for idx, entry in enumerate(register):
        # Determine card color based on status
        if 'Referred to Hospital' in entry['status']:
            card_color = "🔴"
        elif 'Died' in entry['status']:
            card_color = "⚫"
        elif 'stiff neck' in entry['complaint'].lower() or 'seizure' in entry['complaint'].lower():
            card_color = "🟡"
        else:
            card_color = "🟢"

        with st.expander(f"{card_color} **{entry['name']}** ({entry['age']} yrs, {entry['sex']}) - {entry['visit_date']}", expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**ID:** {entry['id']}")
                st.markdown(f"**Village:** {entry['village']}")
                st.markdown(f"**Complaint:** {entry['complaint']}")
                st.markdown(f"**Status:** {entry['status']}")

            with col2:
                # Only show view chart button for key patients (those with medical records)
                key_patients = ['NALU-CH-001', 'NALU-CH-002', 'NALU-CH-017', 'NALU-CH-023', 'NALU-CH-015', 'NALU-CH-022']
                if entry['id'] in key_patients:
                    if st.button("View Chart", key=f"chart_{entry['id']}"):
                        st.session_state['current_chart'] = entry['id']
                        st.session_state['unlocked_nalu_charts'].append(entry['id'])
                        st.rerun()

    st.markdown("---")

    # Display medical chart if selected
    if 'current_chart' in st.session_state and st.session_state.get('current_chart'):
        chart_id = st.session_state['current_chart']
        st.markdown(f"### Medical Record: {chart_id}")

        record = get_nalu_medical_record(chart_id)

        if record:
            with st.container():
                st.markdown("#### 📋 Patient Chart")
                for key, value in record.items():
                    st.markdown(f"**{key}:** {value}")

                if st.button("Close Chart", key="close_chart"):
                    st.session_state['current_chart'] = None
                    st.rerun()
        else:
            st.warning("No detailed medical record available for this patient.")

    st.markdown("---")

    # Summary statistics
    st.markdown("### Summary")
    total = len(register)
    referrals = sum(1 for e in register if 'Referred to Hospital' in e['status'])
    deaths = sum(1 for e in register if 'Died' in e['status'])
    suspected = sum(1 for e in register if any(term in e['complaint'].lower() for term in ['fever', 'seizure', 'stiff neck', 'shaking']))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Entries", total)
    col2.metric("Hospital Referrals", referrals)
    col3.metric("Deaths", deaths)
    col4.metric("Suspected Neuro Cases", suspected)
