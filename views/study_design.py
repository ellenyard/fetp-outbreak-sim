import streamlit as st
import pandas as pd
import numpy as np
import io
from i18n.translate import t
from config.locations import get_current_scenario_id
from state.resources import spend_time, spend_budget, format_resource_cost, TIME_COSTS, BUDGET_COSTS
import outbreak_logic as jl

apply_case_definition = jl.apply_case_definition
ensure_reported_to_hospital = jl.ensure_reported_to_hospital
generate_study_dataset = jl.generate_study_dataset
validate_study_design_requirements = getattr(jl, "validate_study_design_requirements", None)

parse_xlsform = getattr(jl, "parse_xlsform", None)
llm_map_xlsform_questions = getattr(jl, "llm_map_xlsform_questions", None)
llm_build_select_one_choice_maps = getattr(jl, "llm_build_select_one_choice_maps", None)
llm_build_unmapped_answer_generators = getattr(jl, "llm_build_unmapped_answer_generators", None)
prepare_question_render_plan = getattr(jl, "prepare_question_render_plan", None)
XLSFORM_AVAILABLE = all([callable(f) for f in [parse_xlsform, llm_map_xlsform_questions, llm_build_select_one_choice_maps, llm_build_unmapped_answer_generators, prepare_question_render_plan]])


def _derive_unlocked_domains() -> set:
    """Derive unlocked exposure domains based on NPC interviews and data access."""
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
            domains.add("clinical")

    # Check if derive_unlocked_domains exists in outbreak_logic for full implementation
    if hasattr(jl, "derive_unlocked_domains"):
        domains = jl.derive_unlocked_domains()

    return domains


def view_study_design():
    st.header("Data & Study Design")

    truth = st.session_state.truth
    individuals = truth["individuals"]
    households = truth["households"]

    # Gate: don't let Day 2 artifacts be first interaction
    prereq_ok = bool(st.session_state.get("case_definition_written")) and bool(st.session_state.get("hypotheses_documented"))
    if not prereq_ok:
        st.info("Complete **Day 1** on the **Overview / Briefing** screen first (case definition + at least 1 hypothesis). Then return here for sampling and questionnaire upload.")
        return

    # Initialize wizard state
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 1
    if "exposure_domains" not in st.session_state.decisions:
        st.session_state.decisions["exposure_domains"] = {
            "human_demographics": False,
            "animal_exposure": False,
            "environmental_factors": False,
            "behavioral_factors": False
        }

    # Wizard progress indicator
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        status1 = "[●]" if st.session_state.wizard_step == 1 else "[✓]" if st.session_state.wizard_step > 1 else "[ ]"
        st.markdown(f"**{status1} Step 1: Methodology**")
    with col2:
        status2 = "[●]" if st.session_state.wizard_step == 2 else "[✓]" if st.session_state.wizard_step > 2 else "[ ]"
        st.markdown(f"**{status2} Step 2: Exposure Domains**")
    with col3:
        status3 = "[●]" if st.session_state.wizard_step == 3 else "[ ]"
        st.markdown(f"**{status3} Step 3: Review**")
    st.markdown("---")

    # ========================================
    # STEP 1: METHODOLOGY
    # ========================================
    if st.session_state.wizard_step == 1:
        st.markdown("## Step 1: Study Methodology")

        # Case definition (read-only)
        st.markdown("### Case Definition (from Day 1)")
        cd_text = st.session_state.decisions.get("case_definition_text", "").strip()
        if cd_text:
            st.text_area("Working case definition:", value=cd_text, height=100, disabled=True)
        else:
            st.warning("No case definition saved yet.")

        st.markdown("### Study Design")
        scenario_config = st.session_state.get("scenario_config", {}) or {}
        recommended = scenario_config.get("study_design", {}).get("recommended", "case_control")
        sd_type = st.radio(
            "Choose a study design:",
            ["Case-control", "Retrospective cohort"],
            horizontal=True,
            index=0 if st.session_state.decisions.get("study_design", {}).get("type") == "case_control" else 1,
        )

        if sd_type == "Case-control":
            st.session_state.decisions["study_design"] = {"type": "case_control"}
            st.info("**Case-control study**: Compare exposures between cases and controls.")
        else:
            st.session_state.decisions["study_design"] = {"type": "cohort"}
            st.info("**Retrospective cohort study**: Compare attack rates between exposed and unexposed groups.")

        if recommended and st.session_state.decisions["study_design"]["type"] != recommended:
            st.warning(f"Scenario guidance suggests a **{scenario_config.get('study_design', {}).get('label', 'preferred')}** design.")

        st.markdown("### Design Justification")
        st.session_state.decisions["study_design_justification"] = st.text_area(
            "Justify your design choice (2-3 sentences)",
            value=st.session_state.decisions.get("study_design_justification", ""),
            height=80,
        )
        st.session_state.decisions["study_design_sampling_frame"] = st.text_area(
            "Describe the sampling frame",
            value=st.session_state.decisions.get("study_design_sampling_frame", scenario_config.get("study_design", {}).get("sampling_frame_prompt", "")),
            height=60,
        )
        st.session_state.decisions["study_design_bias_notes"] = st.text_area(
            "Bias/matching/feasibility notes",
            value=st.session_state.decisions.get("study_design_bias_notes", ""),
            height=80,
            help="Note potential biases, matching considerations, and feasibility constraints.",
        )

        # Navigation
        if st.button("Next: Exposure Domains", type="primary"):
            if validate_study_design_requirements:
                ok, missing = validate_study_design_requirements(st.session_state.decisions, scenario_config)
            else:
                ok, missing = True, []
            if not ok:
                st.error("Please complete the study design justification, sampling frame, and bias notes before continuing.")
            else:
                st.session_state.wizard_step = 2
                st.rerun()

    # ========================================
    # STEP 2: EXPOSURE DOMAINS (ONE HEALTH)
    # ========================================
    elif st.session_state.wizard_step == 2:
        st.markdown("## Step 2: Exposure Domains (One Health Approach)")

        st.markdown("""
        Select the exposure domains you want to investigate in your study.
        A comprehensive One Health investigation covers human, animal, environmental, and behavioral factors.
        """)

        # Domain checkboxes
        domains = st.session_state.decisions["exposure_domains"]

        col1, col2 = st.columns(2)
        with col1:
            domains["human_demographics"] = st.checkbox(
                "Human Demographics & Health",
                value=domains["human_demographics"],
                help="Age, sex, occupation, clinical symptoms, vaccination history"
            )
            domains["animal_exposure"] = st.checkbox(
                "Animal Exposure",
                value=domains["animal_exposure"],
                help="Contact with pigs, poultry, livestock; proximity to animal populations"
            )
        with col2:
            domains["environmental_factors"] = st.checkbox(
                "Environmental Factors",
                value=domains["environmental_factors"],
                help="Water sources, rice paddies, mosquito exposure, housing conditions"
            )
            domains["behavioral_factors"] = st.checkbox(
                "Behavioral & Social Factors",
                value=domains["behavioral_factors"],
                help="Outdoor activities, protective measures, living conditions, water use"
            )

        # Coverage Meter
        selected_count = sum(domains.values())
        total_count = len(domains)
        coverage_pct = (selected_count / total_count) * 100 if total_count > 0 else 0

        st.markdown("### One Health Coverage Meter")
        st.progress(coverage_pct / 100)
        st.caption(f"Coverage: {selected_count}/{total_count} domains ({coverage_pct:.0f}%)")

        if coverage_pct < 50:
            st.warning("Consider selecting more domains for a comprehensive One Health investigation.")
        elif coverage_pct < 100:
            st.info("Good coverage. Consider adding remaining domains for completeness.")
        else:
            st.success("Excellent! Full One Health coverage across all domains.")

        # Navigation
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous: Methodology"):
                st.session_state.wizard_step = 1
                st.rerun()
        with col2:
            if st.button("Next: Review", type="primary"):
                st.session_state.wizard_step = 3
                st.rerun()

    # ========================================
    # STEP 3: REVIEW & PARTICIPANT SELECTION
    # ========================================
    elif st.session_state.wizard_step == 3:
        st.markdown("## Step 3: Review & Finalize")

        # Review selections
        with st.expander("Review Study Design", expanded=True):
            st.markdown("**Study Type:** " + st.session_state.decisions.get("study_design", {}).get("type", "Not selected").replace("_", "-").title())
            st.markdown("**Exposure Domains Selected:**")
            domains = st.session_state.decisions["exposure_domains"]
            for key, selected in domains.items():
                status = "[✓]" if selected else "[ ]"
                label = key.replace("_", " ").title()
                st.markdown(f"{status} {label}")

            # Coverage meter (compact)
            selected_count = sum(domains.values())
            total_count = len(domains)
            coverage_pct = (selected_count / total_count) * 100
            st.progress(coverage_pct / 100)
            st.caption(f"One Health Coverage: {coverage_pct:.0f}%")

        # Continue with existing participant selection logic
        st.markdown("---")

        # Navigation back button
        if st.button("Previous: Exposure Domains"):
            st.session_state.wizard_step = 2
            st.rerun()

        # -------------------------
        # Participant Selection (only in Step 3)
        # -------------------------
        st.markdown("### Participant Selection")

        # Ensure clinic eligibility proxy exists (used for clinic controls)
        if "reported_to_hospital" not in individuals.columns:
            individuals = ensure_reported_to_hospital(individuals, random_seed=42)
            st.session_state.truth["individuals"] = individuals

        case_criteria = {
            "scenario_id": st.session_state.get("current_scenario"),
            "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
            "lab_results": st.session_state.lab_results,
        }
        cases_pool = apply_case_definition(individuals, case_criteria).copy()
        cases_pool = cases_pool.sort_values(["village_id", "onset_date"], na_position="last")

        existing_cases = st.session_state.decisions.get("selected_cases", []) or []
        existing_controls = st.session_state.decisions.get("selected_controls", []) or []

        # Basic sampling targets
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            n_cases_target = st.number_input("Target # cases", min_value=1, max_value=200, value=int(st.session_state.decisions.get("sample_size", {}).get("cases", 20)), step=1)
        with c2:
            controls_per_case = st.number_input("Controls per case", min_value=1, max_value=5, value=int(st.session_state.decisions.get("study_design", {}).get("controls_per_case", 2) or 2), step=1)
        with c3:
            nonresponse_rate = st.slider("Expected nonresponse", min_value=0, max_value=25, value=int((st.session_state.decisions.get("sampling_plan", {}) or {}).get("nonresponse_rate", 0.0) * 100), step=1)
        with c4:
            allow_replacement = st.checkbox("Allow replacement if nonresponse", value=bool((st.session_state.decisions.get("sampling_plan", {}) or {}).get("allow_replacement", True)))

        st.session_state.decisions["sample_size"] = {"cases": int(n_cases_target), "controls_per_case": int(controls_per_case)}
        st.session_state.decisions.setdefault("study_design", {})
        st.session_state.decisions["study_design"]["controls_per_case"] = int(controls_per_case)

        # Show breakdown of case sources if case finding has been done
        if st.session_state.get('found_cases_added', False) and 'found_via_case_finding' in cases_pool.columns:
            found_count = cases_pool['found_via_case_finding'].sum() if 'found_via_case_finding' in cases_pool.columns else 0
            initial_count = len(cases_pool) - found_count
            st.caption(f"Eligible cases (based on your case definition proxy): **{len(cases_pool)}** ({initial_count} initial + {int(found_count)} from case finding)")
        else:
            st.caption(f"Eligible cases (based on your case definition proxy): **{len(cases_pool)}**")

        # ---- CASE SELECTION (manual)
        with st.form("case_select_form"):
            st.markdown("#### Select cases")
            v_filter = st.multiselect("Filter cases by village", sorted(cases_pool["village_id"].dropna().unique().tolist()), default=sorted(cases_pool["village_id"].dropna().unique().tolist()))
            df_cases = cases_pool[cases_pool["village_id"].isin(v_filter)].copy()

            show_cols = [c for c in ["person_id", "village_id", "hh_id", "age", "sex", "occupation", "onset_date", "severe_neuro", "outcome", "reported_to_hospital"] if c in df_cases.columns]
            df_cases = df_cases[show_cols].copy()
            df_cases.insert(0, "select", df_cases["person_id"].isin(existing_cases))

            edited = st.data_editor(
                df_cases,
                hide_index=True,
                use_container_width=True,
                column_config={"select": st.column_config.CheckboxColumn("Select")},
                disabled=[c for c in df_cases.columns if c != "select"],
            )

            submitted = st.form_submit_button("Save selected cases")
            if submitted:
                selected = edited[edited["select"] == True]["person_id"].astype(str).tolist()
                if len(selected) < 1:
                    st.error("Select at least 1 case.")
                else:
                    st.session_state.decisions["selected_cases"] = selected
                    st.success(f"Saved **{len(selected)}** selected cases.")
                    st.rerun()

        selected_cases = st.session_state.decisions.get("selected_cases", []) or []
        if selected_cases:
            st.info(f"Current case selection: **{len(selected_cases)}** cases selected. Target was {int(n_cases_target)}.")

        # ---- CONTROL SOURCE + ELIGIBILITY
        st.markdown("#### Controls: source & eligibility")
        control_source_label = st.selectbox(
            "Control source",
            ["Community controls", "Neighborhood controls (near cases)", "Clinic controls (healthcare-seeking)"],
            index=0,
        )
        control_source = "community"
        if "Neighborhood" in control_source_label:
            control_source = "neighborhood"
        elif "Clinic" in control_source_label:
            control_source = "clinic"

        eligible_villages_default = sorted(list(set(cases_pool[cases_pool["person_id"].isin(selected_cases)]["village_id"].dropna().astype(str).tolist()))) if selected_cases else sorted(cases_pool["village_id"].dropna().unique().tolist())
        eligible_villages = st.multiselect("Eligible villages for controls", options=sorted(individuals["village_id"].dropna().unique().tolist()), default=eligible_villages_default)

        include_symptomatic_noncase = st.checkbox("Allow symptomatic non-cases as controls (rare)", value=bool((st.session_state.decisions.get("sampling_plan", {}) or {}).get("include_symptomatic_noncase", False)))

        # Optional age eligibility for controls
        age_mode = st.radio("Control age rule", ["No restriction", "Specify range"], horizontal=True, index=0)
        control_age_range = None
        if age_mode == "Specify range":
            a1, a2 = st.columns(2)
            with a1:
                cmin = st.number_input("Control minimum age", min_value=0, max_value=100, value=0, step=1)
            with a2:
                cmax = st.number_input("Control maximum age", min_value=0, max_value=100, value=60, step=1)
            control_age_range = {"min": int(cmin), "max": int(cmax)}

        # Pool for control candidates
        # (We build a manageable candidate set to avoid huge data_editor tables.)
        def _build_control_pool():
            pool = individuals.copy()
            # non-cases only (by default)
            case_ids = set(cases_pool["person_id"].astype(str).tolist())
            pool = pool[~pool["person_id"].astype(str).isin(case_ids)].copy()
            pool = pool[pool["village_id"].isin(eligible_villages)].copy()
            if control_age_range:
                pool = pool[(pool["age"] >= int(control_age_range["min"])) & (pool["age"] <= int(control_age_range["max"]))].copy()
            if control_source == "clinic" and "reported_to_hospital" in pool.columns:
                pool = pool[pool["reported_to_hospital"].fillna(False).astype(bool)].copy()
            # neighborhood handled in outbreak_logic with weights; here we just show same-village candidates
            return pool

        controls_pool = _build_control_pool()
        needed_controls = int(len(selected_cases) * int(controls_per_case)) if selected_cases else int(n_cases_target) * int(controls_per_case)
        st.caption(f"Eligible controls in pool: **{len(controls_pool)}** | Recommended controls to select: **{needed_controls}**")

        # Candidate sampling for UI
        if "controls_candidate_ids" not in st.session_state:
            st.session_state.controls_candidate_ids = []
        if "controls_candidate_seed" not in st.session_state:
            st.session_state.controls_candidate_seed = 0

        cbtn1, cbtn2 = st.columns([1, 3])
        with cbtn1:
            if st.button("Refresh control candidates"):
                st.session_state.controls_candidate_seed += 1
                st.session_state.controls_candidate_ids = []
                st.rerun()

        # Build candidate list (sample to keep UI snappy)
        rng = np.random.default_rng(100 + int(st.session_state.controls_candidate_seed))
        if not st.session_state.controls_candidate_ids:
            cand_n = min(350, len(controls_pool))
            if cand_n > 0:
                cand_ids = controls_pool.sample(n=cand_n, random_state=100 + int(st.session_state.controls_candidate_seed))["person_id"].astype(str).tolist()
                st.session_state.controls_candidate_ids = cand_ids

        cand_controls = controls_pool[controls_pool["person_id"].astype(str).isin(st.session_state.controls_candidate_ids)].copy()
        show_cols_c = [c for c in ["person_id", "village_id", "hh_id", "age", "sex", "occupation", "reported_to_hospital"] if c in cand_controls.columns]
        cand_controls = cand_controls[show_cols_c].copy()
        cand_controls.insert(0, "select", cand_controls["person_id"].astype(str).isin(existing_controls))

        with st.form("controls_select_form"):
            st.markdown("#### Select controls (from a candidate list)")
            edited_c = st.data_editor(
                cand_controls,
                hide_index=True,
                use_container_width=True,
                column_config={"select": st.column_config.CheckboxColumn("Select")},
                disabled=[c for c in cand_controls.columns if c != "select"],
            )
            sub_c = st.form_submit_button("Save selected controls")
            if sub_c:
                selected_c = edited_c[edited_c["select"] == True]["person_id"].astype(str).tolist()
                if len(selected_c) < 1:
                    st.error("Select at least 1 control.")
                else:
                    st.session_state.decisions["selected_controls"] = selected_c
                    st.success(f"Saved **{len(selected_c)}** selected controls.")
                    st.rerun()

        selected_controls = st.session_state.decisions.get("selected_controls", []) or []
        if selected_controls:
            st.info(f"Current control selection: **{len(selected_controls)}** controls selected. Recommended: {needed_controls}.")

        # Persist sampling plan (used by dataset generator)
        st.session_state.decisions["sampling_plan"] = {
            "control_source": control_source,
            "eligible_villages": eligible_villages,
            "include_symptomatic_noncase": bool(include_symptomatic_noncase),
            "control_age_range": control_age_range,
            "nonresponse_rate": float(nonresponse_rate) / 100.0,
            "allow_replacement": bool(allow_replacement),
            "controls_per_case": int(controls_per_case),
            "n_cases": int(n_cases_target),
        }

        # -------------------------
        # Step 3: Questionnaire (XLSForm upload) — gated
        # -------------------------
        st.markdown("### Step 3: Questionnaire (XLSForm upload)")

        if not prereq_ok:
            st.warning("Questionnaire upload is locked until you have a saved case definition and at least 1 hypothesis (Day 1).")
        else:
            st.caption("Build your questionnaire in Kobo (or any XLSForm editor), export as XLSForm (.xlsx), then upload it here.")
            uploaded = st.file_uploader("Upload XLSForm (.xlsx)", type=["xlsx"], key="xlsform_upload")

            if uploaded is not None:
                xls_bytes = uploaded.read()
                st.session_state.decisions["questionnaire_xlsform_bytes"] = xls_bytes

                try:
                    questionnaire = parse_xlsform(xls_bytes)
                    st.session_state.decisions["questionnaire_xlsform_preview"] = questionnaire

                    preview_rows = []
                    for q in questionnaire.get("questions", []):
                        preview_rows.append({
                            "name": q.get("name"),
                            "type": q.get("type"),
                            "label": q.get("label"),
                            "list_name": q.get("list_name"),
                            "n_choices": len(q.get("choices", []) or []),
                        })
                    if preview_rows:
                        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
                    else:
                        st.info("No survey questions detected (notes/groups/calculations are ignored).")
                except Exception as e:
                    st.error(f"Could not parse this XLSForm. Make sure you uploaded the *form definition* (XLSForm), not a data export. Details: {e}")
                    questionnaire = None

                if questionnaire:
                    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
                    if not api_key:
                        st.warning("ANTHROPIC_API_KEY not found in Streamlit secrets. LLM mapping cannot run until it is configured.")

                    if st.button("Run LLM mapping & save questionnaire", key="save_xlsform_questionnaire"):
                        if not api_key:
                            st.error("Missing ANTHROPIC_API_KEY in Streamlit secrets.")
                        else:
                            try:
                                questionnaire = llm_map_xlsform_questions(questionnaire, api_key=api_key)
                                questionnaire = llm_build_select_one_choice_maps(questionnaire, api_key=api_key)
                                questionnaire = llm_build_unmapped_answer_generators(questionnaire, api_key=api_key)
                                questionnaire = prepare_question_render_plan(questionnaire)

                                st.session_state.decisions["questionnaire_xlsform"] = questionnaire
                                st.session_state.questionnaire_submitted = True
                                st.success("Questionnaire uploaded, mapped, and saved.")
                            except Exception as e:
                                st.error(f"Failed to map/save questionnaire: {e}")


        # Facilitator mapping review (optional)
        saved_q = st.session_state.decisions.get("questionnaire_xlsform")
        if isinstance(saved_q, dict) and saved_q.get("questions"):
            if st.session_state.get("facilitator_mode", False):
                with st.expander("Facilitator mapping review (optional)", expanded=False):
                    rows = []
                    for q in saved_q.get("questions", []):
                        r = q.get("render", {}) or {}
                        rows.append({
                            "question_name": q.get("name"),
                            "type": q.get("type"),
                            "label": q.get("label"),
                            "mapped_var": r.get("mapped_var"),
                            "confidence": r.get("confidence"),
                            "domain": r.get("domain"),
                            "rationale": r.get("rationale"),
                            "unmapped": r.get("mapped_var") in (None, "", "unmapped"),
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Step 4: Generate dataset (requires questionnaire + selections)
        # -------------------------
        st.markdown("### Step 4: Generate simulated study dataset")

        can_generate = bool(st.session_state.decisions.get("questionnaire_xlsform")) and bool(st.session_state.decisions.get("selected_cases")) and bool(st.session_state.decisions.get("selected_controls"))
        if not can_generate:
            st.info("To generate the dataset, you need: (1) saved XLSForm questionnaire, (2) selected cases, and (3) selected controls.")
            return

        if st.button("Generate Dataset", type="primary"):
            try:
                decisions = dict(st.session_state.decisions)
                decisions["return_sampling_report"] = True
                decisions["scenario_id"] = st.session_state.get("current_scenario")
                decisions["scenario_config"] = st.session_state.get("scenario_config", {})
                decisions["unlocked_domains"] = sorted(_derive_unlocked_domains())
                st.session_state.decisions["unlocked_domains"] = decisions["unlocked_domains"]
                df, report = generate_study_dataset(individuals, households, decisions)

                st.session_state.generated_dataset = df
                st.session_state.sampling_report = report
                st.session_state.descriptive_analysis_done = True  # proxy
                st.success("Dataset generated. Preview below; export for analysis as needed.")

                locked_domains = (
                    st.session_state.decisions.get("questionnaire_xlsform", {})
                    .get("meta", {})
                    .get("locked_domains", [])
                )
                if locked_domains:
                    st.warning(
                        "Some exposure domains were locked because they were not investigated yet: "
                        + ", ".join(locked_domains)
                    )

                with st.expander("Sampling frame summary", expanded=True):
                    st.json({
                        "case_pool_n": report.get("case_pool_n"),
                        "control_pool_n": report.get("control_pool_n"),
                        "cases_selected_n": report.get("cases_selected_n"),
                        "controls_selected_n": report.get("controls_selected_n"),
                        "cases_after_nonresponse_n": report.get("cases_after_nonresponse_n"),
                        "controls_after_nonresponse_n": report.get("controls_after_nonresponse_n"),
                        "nonresponse_rate": st.session_state.decisions.get("sampling_plan", {}).get("nonresponse_rate"),
                        "allow_replacement": st.session_state.decisions.get("sampling_plan", {}).get("allow_replacement"),
                        "control_source": st.session_state.decisions.get("sampling_plan", {}).get("control_source"),
                    })

                st.dataframe(df.head(30), use_container_width=True)

            except Exception as e:
                st.error(f"Dataset generation failed: {e}")
