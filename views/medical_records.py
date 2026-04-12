import streamlit as st
import pandas as pd
from i18n.translate import t
from config.locations import get_current_scenario_id
from data_utils.clinic import (
    generate_hospital_records, render_hospital_record,
    generate_clinic_records, render_clinic_record
)
from data_utils.case_definition import get_symptomatic_column, get_day1_assets
from state.resources import spend_time, spend_budget, check_resources, format_resource_cost, TIME_COSTS
from npc.engine import get_npc_response, stream_npc_response, get_npc_avatar
from npc.emotions import get_npc_trust, update_npc_emotion, analyze_user_tone
from npc.unlock import check_npc_unlock_triggers
import outbreak_logic as jl


def view_hospital_triage():
    from npc.unlock import get_hospital_records_contact_name

    st.markdown("## District Hospital Triage")

    # Intro Text
    contact_name = get_hospital_records_contact_name()
    st.info(
        f"{contact_name}: 'Here are the patients admitted in the last 48 hours. Please review them. "
        "Mark the ones that fit your Case Definition to add them to your Line List.'"
    )

    # Initialize State
    if 'line_list' not in st.session_state:
        st.session_state.line_list = []
    if 'parents_interviewed' not in st.session_state:
        st.session_state.parents_interviewed = []

    triage_data = jl.get_hospital_triage_list()

    # --- SECTION 1: THE CHECKLIST ---
    with st.container(border=True):
        st.markdown("### Patient Admission Log")

        # Grid Header
        c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
        c1.write("**Add?**")
        c2.write("**ID/Age**")
        c3.write("**Village**")
        c4.write("**Clinical Notes**")

        # Grid Rows
        for patient in triage_data:
            c1, c2, c3, c4 = st.columns([1, 1, 1, 3])

            # Checkbox
            is_selected = patient['id'] in st.session_state.line_list
            if c1.checkbox("Select", key=f"chk_{patient['id']}", value=is_selected, label_visibility="collapsed"):
                if patient['id'] not in st.session_state.line_list:
                    st.session_state.line_list.append(patient['id'])
            else:
                if patient['id'] in st.session_state.line_list:
                    st.session_state.line_list.remove(patient['id'])

            c2.write(f"**{patient['id']}** ({patient['age']}/{patient['sex']})")
            c3.write(patient['village'])
            # Highlight Fever to rule out toxin
            if "Fever" in patient['symptom']:
                c4.markdown(f"**{patient['symptom']}** - *{patient['notes']}*")
            else:
                c4.write(f"{patient['symptom']} - *{patient['notes']}*")
            st.divider()

    # --- SECTION 2: PARENT INTERVIEWS ---
    if len(st.session_state.line_list) > 0:
        st.markdown("### Investigation")
        st.write(f"**Budget:** You can interview parents for **{2 - len(st.session_state.parents_interviewed)}** more cases.")

        cols = st.columns(3)
        for i, patient_id in enumerate(st.session_state.line_list):
            patient = next(p for p in triage_data if p['id'] == patient_id)

            with cols[i % 3]:
                with st.container(border=True):
                    st.write(f"**{patient_id}** ({patient['village']})")

                    if patient_id in st.session_state.parents_interviewed:
                        st.success("✅ Interviewed")
                    elif len(st.session_state.parents_interviewed) >= 2:
                        st.caption("⛔ No Budget")
                    else:
                        if st.button(f"Interview Parents", key=f"btn_{patient_id}"):
                            st.session_state.parents_interviewed.append(patient_id)

                            # Log the parent interview event
                            jl.log_event(
                                event_type='interview',
                                location_id=patient['parent_type'],
                                cost_time=0,
                                cost_budget=0,
                                payload={
                                    'patient_id': patient_id,
                                    'parent_type': patient['parent_type'],
                                    'village': patient['village']
                                }
                            )

                            # TRIGGER THE INTERVIEW
                            st.session_state.current_npc = patient['parent_type']
                            st.rerun()

    # --- SECTION 3: THE DIALOGUE (Pop-up) ---
    if 'current_npc' in st.session_state and st.session_state.current_npc in ['parent_tamu', 'parent_general', 'parent_ward']:
        npc_key = st.session_state.current_npc
        # Load the text from truth data
        truth = st.session_state.get("truth", {}) or {}
        npc_data = (truth.get("npc_truth", {}) or {}).get(npc_key)
        if npc_data is None:
            data_dir = st.session_state.get("data_dir")
            if data_dir:
                npc_data = (jl.load_truth_data(data_dir=data_dir).get("npc_truth", {}) or {}).get(npc_key)

        if npc_data is None:
            st.error("Unable to load interview data for this NPC.")
            if st.button("End Interview"):
                del st.session_state.current_npc
                st.rerun()
            return

        st.markdown("---")
        st.warning(f"🎙️ Interviewing: {npc_data['name']}")
        st.write(f"**{npc_data['name']}:** \"{npc_data['always_reveal'][0]}\"")
        st.write(f"**{npc_data['name']}:** \"{npc_data['always_reveal'][2]}\"")

        # Special logic for Tamu (JE/AES scenario only)
        if npc_key == 'parent_tamu' and st.session_state.get("current_scenario_type", "je") == "je":
            st.error("❗ **KEY FINDING:** Family traveled to Nalu 2 weeks ago!")

        if st.button("End Interview"):
            del st.session_state.current_npc
            st.rerun()


def view_interviews():
    from config.locations import get_locations
    from views.interviews import render_interview_modal

    truth = st.session_state.truth
    npc_truth = truth["npc_truth"]

    # Back button at the top for easy navigation
    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        # If coming from a location, show "Return to Location" button
        current_loc = st.session_state.get("current_location")
        if current_loc:
            loc_data = get_locations().get(current_loc, {})
            loc_name = loc_data.get("name", "Location")
            if st.button(f"🔙 Return to {loc_name}", key="return_to_loc_from_interviews"):
                st.session_state.current_view = "location"
                st.rerun()
        else:
            if st.button("🔙 Return to Map", key="return_to_map_from_interviews"):
                st.session_state.current_view = "map"
                st.rerun()

    st.header("👥 Interviews")

    # Check if we're accessing from a specific location with NPCs
    context_loc = st.session_state.get("interview_context_location")
    context_npcs = []
    if context_loc:
        loc_data = get_locations().get(context_loc, {})
        for npc_key in loc_data.get("npcs", []):
            if npc_key in st.session_state.npcs_unlocked and npc_key in npc_truth:
                context_npcs.append((npc_key, npc_truth[npc_key]))

    # If there's exactly one NPC at the context location and no active modal,
    # start the conversation immediately
    if len(context_npcs) == 1 and not st.session_state.get("action_modal"):
        npc_key, npc = context_npcs[0]
        interviewed = npc_key in st.session_state.interview_history
        time_cost = TIME_COSTS["interview_followup"] if interviewed else TIME_COSTS["interview_initial"]
        budget_cost = 0 if interviewed else npc.get("cost", 0)

        can_proceed, msg = check_resources(time_cost, budget_cost)
        if can_proceed:
            spend_time(time_cost, f"Interview: {npc['name']}")
            if budget_cost > 0:
                spend_budget(budget_cost, f"Interview: {npc['name']}")
            st.session_state.current_npc = npc_key
            st.session_state.interview_history.setdefault(npc_key, [])
            st.session_state.action_modal = "interview"
            # Clear context after auto-selecting
            st.session_state.interview_context_location = None
            st.rerun()

    # Resource display
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Budget", f"${st.session_state.budget}")
    with col2:
        time_color = "normal" if st.session_state.time_remaining >= 0 else "inverse"
        st.metric("⏱️ Time Remaining", f"{st.session_state.time_remaining}h", delta_color=time_color)
    with col3:
        st.metric("Interviews Completed", len(st.session_state.interview_history))

    st.caption("Each new interview costs time. Follow-up questions with the same person are quicker.")

    # Group NPCs by availability
    available_npcs = []
    locked_npcs = []

    for npc_key, npc in npc_truth.items():
        if npc_key in st.session_state.npcs_unlocked:
            available_npcs.append((npc_key, npc))
        else:
            locked_npcs.append((npc_key, npc))

    # Show available NPCs
    st.markdown("### Available Contacts")
    cols = st.columns(3)
    for i, (npc_key, npc) in enumerate(available_npcs):
        with cols[i % 3]:
            interviewed = npc_key in st.session_state.interview_history
            status = "✓ Interviewed" if interviewed else ""

            # Calculate costs
            time_cost = TIME_COSTS["interview_followup"] if interviewed else TIME_COSTS["interview_initial"]
            budget_cost = 0 if interviewed else npc.get("cost", 0)

            st.markdown(f"**{npc.get('avatar', '🧑')} {npc['name']}** {status}")
            st.caption(f"{npc['role']}")
            st.caption(f"Cost: {format_resource_cost(time_cost, budget_cost)}")

            btn_label = "Continue" if interviewed else "Talk"
            if st.button(f"{btn_label}", key=f"btn_{npc_key}"):
                can_proceed, msg = check_resources(time_cost, budget_cost)
                if can_proceed:
                    spend_time(time_cost, f"Interview: {npc['name']}")
                    if budget_cost > 0:
                        spend_budget(budget_cost, f"Interview: {npc['name']}")

                    # Log the interview event
                    jl.log_event(
                        event_type='interview',
                        location_id=npc_key,
                        cost_time=time_cost,
                        cost_budget=budget_cost,
                        payload={
                            'npc_name': npc['name'],
                            'npc_role': npc['role'],
                            'is_followup': interviewed
                        }
                    )

                    st.session_state.current_npc = npc_key
                    st.session_state.interview_history.setdefault(npc_key, [])
                    st.session_state.action_modal = "interview"
                    st.rerun()
                else:
                    st.error(msg)

    # Show locked NPCs (without hints about how to unlock)
    if locked_npcs:
        st.markdown("### Other Contacts")
        st.caption("Some contacts may become available as your investigation progresses.")
        cols = st.columns(3)
        for i, (npc_key, npc) in enumerate(locked_npcs):
            with cols[i % 3]:
                st.markdown(f"**🔒 {npc['name']}**")
                st.caption(f"{npc['role']}")
                st.caption("*Not yet available*")

    # Handle interview modal
    action_modal = st.session_state.get("action_modal")
    if action_modal == "interview":
        st.markdown("---")
        render_interview_modal()


def view_medical_records():
    """Day 1: Medical Records view - The Hub for building case definition and line list variables."""
    from data_utils.case_definition import scenario_config_label
    import day1_utils

    st.title("Medical Records")
    st.caption("Day 1: Review initial cases and build your field log structure")
    scenario_type = st.session_state.get("current_scenario_type", "je")

    # Back button
    if st.button("Return to Map", key="return_from_medical_records"):
        st.session_state.current_view = "map"
        st.rerun()

    st.markdown("---")

    # STEP 1: Case card set
    st.markdown("### Step 1: Case Card Review")
    st.caption("Review these case cards and label each based on your current case definition tier.")

    assets = get_day1_assets()
    case_cards = assets.get("case_cards", [])
    labels = ["Select...", "Likely case", "Possible", "Unlikely"]

    if not case_cards:
        st.info("No case cards available for this scenario.")
    else:
        cols = st.columns(3)
        for idx, card in enumerate(case_cards):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"**{card['case_id']}: {card['title']}**")
                    st.caption(card.get("clinical", ""))
                    st.markdown(f"- **Exposure:** {card.get('exposure', 'Not documented')}")
                    st.markdown(f"- **Lab:** {card.get('lab', 'Not available')}")
                    st.markdown(f"- **Missing data:** {card.get('missing_data', 'None')}")

                    current_label = st.session_state.case_card_labels.get(card["case_id"], "Select...")
                    selection = st.selectbox(
                        "Classification",
                        options=labels,
                        index=labels.index(current_label),
                        key=f"case_card_label_{card['case_id']}",
                    )
                    st.session_state.case_card_labels[card["case_id"]] = selection

        if len(st.session_state.case_card_labels) == len(case_cards) and all(
            label != "Select..." for label in st.session_state.case_card_labels.values()
        ):
            st.session_state.case_cards_reviewed = True
            summary_counts = pd.Series(st.session_state.case_card_labels.values()).value_counts()
            st.success("✅ Case cards reviewed.")
            st.markdown("**Pattern-recognition summary:**")
            st.markdown(f"- Likely: {summary_counts.get('Likely case', 0)}")
            st.markdown(f"- Possible: {summary_counts.get('Possible', 0)}")
            st.markdown(f"- Unlikely: {summary_counts.get('Unlikely', 0)}")

            likely_tags = []
            for card in case_cards:
                if st.session_state.case_card_labels.get(card["case_id"]) == "Likely case":
                    likely_tags.extend(card.get("tags", []))
            if likely_tags:
                top_tags = pd.Series(likely_tags).value_counts().head(3).index.tolist()
                st.caption(f"Common cues among likely cases: {', '.join(top_tags)}")

    st.markdown("---")

    # STEP 2: Build Line List Variables
    st.markdown("### Step 2: Build Line List Variables")
    st.caption("Select which columns you want to include in your field investigation log.")

    if scenario_type == "lepto":
        all_options = [
            "Age",
            "Sex",
            "Village",
            "Fever",
            "Calf myalgia",
            "Conjunctival suffusion",
            "Jaundice",
            "Acute kidney injury",
            "Onset date",
        ]
    else:
        # Available options - including traps
        all_options = [
            "Age",
            "Sex",
            "Village",
            "Fever",
            "Seizure",
            "Rash",
            "Vomiting",
            "Pig Contact",  # Trap!
            "Rice Field",   # Trap!
        ]

    selected_cols = st.multiselect(
        "Select columns for your field log:",
        options=all_options,
        default=st.session_state.line_list_cols if st.session_state.line_list_cols else [],
        key="line_list_cols_select"
    )

    if scenario_type != "lepto":
        # Check for traps
        traps = []
        if "Pig Contact" in selected_cols:
            traps.append("Pig Contact")
        if "Rice Field" in selected_cols:
            traps.append("Rice Field")

        if traps:
            st.warning(f"⚠️ **Medical records do not typically contain exposure information like {', '.join(traps)}. Consider sticking to clinical signs and demographic information that would be documented in hospital records.**")

    if st.button("Save Line List Structure", type="primary"):
        if not selected_cols:
            st.error("Select at least one column before saving your line list structure.")
        else:
            st.session_state.line_list_cols = selected_cols
            st.success(f"✅ Line list structure saved with {len(selected_cols)} columns!")
            st.rerun()

    if st.session_state.line_list_cols:
        st.info(f"Current line list columns: {', '.join(st.session_state.line_list_cols)}")

    st.markdown("---")

    # Navigation hint
    st.markdown("### Next Steps")
    st.caption("Once you've defined your line list structure, proceed to Case Finding to review additional cases.")
    if st.button("Go to Case Finding"):
        st.session_state.current_view = "casefinding"
        st.rerun()


def view_clinic_log_abstraction():
    import io
    from config.scenarios import load_scenario_content
    import day1_utils

    st.title("Clinic Log Abstraction")
    st.caption("Day 1: Clean raw clinic log entries into a structured line list.")

    scenario_type = st.session_state.get("current_scenario_type", "je")
    assets = get_day1_assets()
    entries = assets.get("clinic_log_entries", [])
    schema = day1_utils.get_clinic_log_schema(scenario_type)

    with st.expander("📋 Working Case Definition Reference", expanded=False):
        scenario_id = get_current_scenario_id()
        template_content = load_scenario_content(scenario_id, "case_definition_template")
        st.markdown(template_content)

    st.markdown("""
    **Instructions**
    - Review each raw clinic entry.
    - Enter structured values for each field.
    - Use **\"Unknown\"** when the entry does not provide information (do not leave blank).
    """)

    if not entries:
        st.info("No clinic log entries available for this scenario.")
        return

    st.markdown("### Raw clinic log entries")
    for entry in entries:
        with st.container(border=True):
            st.markdown(f"**{entry['entry_id']}** — {entry['raw_text']}")

    if not st.session_state.clinic_line_list:
        st.session_state.clinic_line_list = [
            {field: (entry["entry_id"] if field == "patient_id" else "") for field in schema}
            for entry in entries
        ]

    st.markdown("### Clean line list (fill in structured fields)")
    df = pd.DataFrame(st.session_state.clinic_line_list)
    df = df.reindex(columns=schema)
    edited_df = st.data_editor(df, num_rows="fixed", use_container_width=True, key="clinic_line_list_editor")

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("Submit Clean Line List", type="primary"):
            cleaned = edited_df.fillna("").to_dict(orient="records")
            st.session_state.clinic_line_list = cleaned
            st.session_state.clinic_abstraction_submitted = True

            blanks = sum(
                1 for row in cleaned for value in row.values() if str(value).strip() == ""
            )
            unknowns = sum(
                1 for row in cleaned for value in row.values() if str(value).strip().lower() == "unknown"
            )

            answer_key = {entry["entry_id"]: entry["answer_key"] for entry in entries}
            total_fields = 0
            matched_fields = 0
            for row in cleaned:
                key = answer_key.get(row.get("patient_id", ""), {})
                for field in schema:
                    if field == "notes":
                        continue
                    expected = str(key.get(field, "")).strip().lower()
                    actual = str(row.get(field, "")).strip().lower()
                    if expected:
                        total_fields += 1
                        if actual == expected:
                            matched_fields += 1

            score = round((matched_fields / total_fields) * 100, 1) if total_fields else 0
            st.session_state.clinic_abstraction_feedback = {
                "blank_fields": blanks,
                "unknown_fields": unknowns,
                "accuracy_percent": score,
            }
            st.success("✅ Line list saved.")

    with col2:
        csv_buffer = io.StringIO()
        edited_df.to_csv(csv_buffer, index=False)
        st.download_button(
            "Download CSV",
            data=csv_buffer.getvalue(),
            file_name="day1_clinic_line_list.csv",
            mime="text/csv",
        )

    if st.session_state.clinic_abstraction_submitted:
        feedback = st.session_state.clinic_abstraction_feedback
        st.markdown("### Feedback")
        st.markdown(f"- Blank fields: **{feedback.get('blank_fields', 0)}**")
        st.markdown(f"- Marked as Unknown: **{feedback.get('unknown_fields', 0)}**")
        st.markdown(f"- Structured field accuracy (vs key): **{feedback.get('accuracy_percent', 0)}%**")
        st.warning("Common pitfalls: confusing visit date vs onset date, inferring sex from names, or skipping explicit 'Unknown'.")

        with st.expander("Answer Key (available after submission)", expanded=False):
            key_rows = []
            for entry in entries:
                row = {"entry_id": entry["entry_id"]}
                row.update(entry.get("answer_key", {}))
                key_rows.append(row)
            st.dataframe(pd.DataFrame(key_rows), use_container_width=True)
