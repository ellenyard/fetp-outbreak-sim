import streamlit as st
import pandas as pd
from datetime import date
from i18n.translate import t
from config.locations import get_current_scenario_id
from npc.engine import lab_test_label, _scenario_lab_catalog
from state.resources import spend_time, spend_budget, format_resource_cost, check_resources, TIME_COSTS, BUDGET_COSTS
import outbreak_logic as jl

apply_case_definition = jl.apply_case_definition
process_lab_order = jl.process_lab_order

LAB_TEST_CATALOG = {
    "JE_IgM_CSF": {"generic": "Arbovirus IgM (CSF)", "confirmed": "Japanese Encephalitis IgM (CSF)"},
    "JE_IgM_serum": {"generic": "Arbovirus IgM (serum)", "confirmed": "Japanese Encephalitis IgM (serum)"},
    "JE_PCR_CSF": {"generic": "Arbovirus PCR (CSF)", "confirmed": "Japanese Encephalitis PCR (CSF)"},
    "JE_PCR_mosquito": {"generic": "Arbovirus PCR (mosquito pool)", "confirmed": "Japanese Encephalitis PCR (mosquito pool)"},
    "JE_Ab_pig": {"generic": "Arbovirus antibodies (pig serum)", "confirmed": "Japanese Encephalitis antibodies (pig serum)"},
    "LEPTO_ELISA_IGM": {"generic": "Leptospira IgM ELISA", "confirmed": "Leptospira IgM ELISA"},
    "LEPTO_PCR_BLOOD": {"generic": "Leptospira PCR (blood)", "confirmed": "Leptospira PCR (blood)"},
    "LEPTO_PCR_URINE": {"generic": "Leptospira PCR (urine)", "confirmed": "Leptospira PCR (urine)"},
    "LEPTO_MAT": {"generic": "Leptospira MAT", "confirmed": "Leptospira MAT"},
    "LEPTO_ENV_WATER_PCR": {"generic": "Leptospira PCR (water)", "confirmed": "Leptospira PCR (water)"},
    "RODENT_PCR": {"generic": "Rodent kidney PCR", "confirmed": "Rodent kidney PCR"},
    "MALARIA_RDT": {"generic": "Malaria RDT", "confirmed": "Malaria RDT"},
    "DENGUE_NS1": {"generic": "Dengue NS1", "confirmed": "Dengue NS1"},
    "BACTERIAL_MENINGITIS_CSF": {"generic": "Bacterial meningitis panel (CSF)", "confirmed": "Bacterial meningitis panel (CSF)"},
}


def _get_available_sample_types():
    """Derive available sample types from scenario config."""
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    return sorted(
        {stype for test in scenario_config.get("lab_tests", []) for stype in test.get("sample_types", [])}
    ) or ["human_CSF", "human_serum", "pig_serum", "mosquito_pool"]


def _refresh_lab_queue_for_day(day: int) -> None:
    """Promote PENDING lab results to final result when day >= ready_day."""
    if "lab_results" not in st.session_state or not st.session_state.lab_results:
        return

    for r in st.session_state.lab_results:
        ready_day = int(r.get("ready_day", 9999))
        if str(r.get("result", "")).upper() == "PENDING" and day >= ready_day:
            r["result"] = r.get("final_result_hidden", r.get("result", "PENDING"))

    # Reveal etiology if confirmatory test returns POSITIVE (only after Day 3+)
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    confirmatory = set(scenario_config.get("confirmatory_tests", []))
    if day >= 3:
        for r in st.session_state.lab_results:
            if str(r.get("result", "")).upper() == "POSITIVE" and r.get("test") in confirmatory:
                st.session_state.etiology_revealed = True
                break


def view_lab_and_environment():
    st.header(t("lab", default="Lab & Environment"))
    if not st.session_state.get("case_definition_written"):
        st.info("Save a working case definition before ordering lab tests.")
        return
    _refresh_lab_queue_for_day(int(st.session_state.get("current_day", 1)))

    # Resource display
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Budget", f"${st.session_state.budget}")
    with col2:
        time_display = f":red[{st.session_state.time_remaining}h]" if st.session_state.time_remaining < 0 else f"{st.session_state.time_remaining}h"
        st.markdown(f"**⏱️ Time Remaining**  \n{time_display}")
    with col3:
        st.metric("🧪 Lab Credits", st.session_state.lab_credits)

    st.markdown("""
    Collect and submit samples for laboratory testing. Each sample type has different
    time and budget costs for collection.
    """)

    scenario_config = st.session_state.get("scenario_config", {}) or {}
    available_sample_types = _get_available_sample_types()
    sample_costs = {
        "human_CSF": {"time": 1.0, "budget": 25, "credits": 3},
        "human_serum": {"time": 0.5, "budget": 25, "credits": 2},
        "pig_serum": {"time": 1.0, "budget": 35, "credits": 2},
        "mosquito_pool": {"time": 1.5, "budget": 40, "credits": 3},
        "blood": {"time": 0.5, "budget": 20, "credits": 2},
        "urine": {"time": 0.5, "budget": 15, "credits": 2},
        "environmental_water": {"time": 1.0, "budget": 20, "credits": 2},
        "environmental_soil": {"time": 1.0, "budget": 20, "credits": 2},
        "rodent_kidney": {"time": 1.5, "budget": 35, "credits": 3},
        "animal_serum": {"time": 1.0, "budget": 25, "credits": 2},
    }

    # Sample costs table
    with st.expander("📋 Sample Collection Costs"):
        sample_costs_table = []
        for sample, costs in sample_costs.items():
            if available_sample_types and sample not in available_sample_types:
                continue
            sample_costs_table.append({
                "Sample Type": sample.replace("_", " ").title(),
                "Time (hours)": costs["time"],
                "Budget ($)": costs["budget"],
                "Lab Credits": costs["credits"],
            })
        st.dataframe(pd.DataFrame(sample_costs_table), hide_index=True)

    truth = st.session_state.truth
    villages = truth["villages"]

    st.markdown("### Submit New Sample")

    col1, col2, col3 = st.columns(3)
    with col1:
        sample_type = st.selectbox(
            "Sample type",
            available_sample_types,
        )
    with col2:
        village_id = st.selectbox(
            "Village",
            villages["village_id"],
            format_func=lambda vid: villages.set_index("village_id").loc[vid, "village_name"],
        )
    with col3:
        available_tests = [t["code"] for t in scenario_config.get("lab_tests", []) if sample_type in t.get("sample_types", [])]
        test = st.selectbox(
            t("lab_test", default="Test"),
            available_tests or list(LAB_TEST_CATALOG.keys()),
            format_func=lab_test_label,
        )

    source_description = st.text_input("Source description (e.g., 'Case from Nalu')", "")

    # Patient linkage for human samples
    cases_pool = apply_case_definition(
        truth["individuals"],
        {
            "scenario_id": st.session_state.get("current_scenario"),
            "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
            "lab_results": st.session_state.lab_results,
        },
    )
    patient_options = ["Unlinked"] + cases_pool["person_id"].astype(str).tolist()
    selected_patient = None
    onset_date = None
    days_since_onset = None
    if sample_type in {"human_CSF", "human_serum", "blood", "urine"} and patient_options:
        selected = st.selectbox("Link to patient", patient_options)
        if selected != "Unlinked":
            selected_patient = selected
            case_row = cases_pool[cases_pool["person_id"].astype(str) == selected].head(1)
            if not case_row.empty:
                onset_date = case_row.iloc[0].get("onset_date")
                if onset_date:
                    scenario_start = pd.to_datetime(scenario_config.get("simulation_start_date", date.today()))
                    current_day = int(st.session_state.get("current_day", 1))
                    current_date = scenario_start + pd.Timedelta(days=current_day - 1)
                    days_since_onset = max(0, (current_date - pd.to_datetime(onset_date)).days)

    volume_ok = st.checkbox("Sample volume sufficient", value=True)
    contaminated = st.checkbox("Sample contaminated", value=False)

    # Calculate costs based on sample type
    costs = sample_costs.get(sample_type, {"time": 1.0, "budget": 25, "credits": 2})

    st.caption(f"This sample will cost: ⏱️ {costs['time']}h | 💰 ${costs['budget']} | 🧪 {costs['credits']} credits")

    if st.button("Submit lab order"):
        # Check resources
        can_proceed, msg = check_resources(costs['time'], costs['budget'])
        if not can_proceed:
            st.error(msg)
        elif st.session_state.lab_credits < costs['credits']:
            st.error(f"Not enough lab credits (need {costs['credits']}, have {st.session_state.lab_credits})")
        else:
            # Deduct resources
            spend_time(costs['time'], f"Sample collection: {sample_type}")
            spend_budget(costs['budget'], f"Sample collection: {sample_type}")
            st.session_state.lab_credits -= costs['credits']

            order = {
                "sample_type": sample_type,
                "village_id": village_id,
                "test": test,
                "source_description": source_description or "Unspecified source",
                "patient_id": selected_patient,
                "onset_date": onset_date,
                "days_since_onset": days_since_onset,
                "placed_day": st.session_state.current_day,
                "volume_ok": volume_ok,
                "contaminated": contaminated,
            }
            result = process_lab_order(order, truth["lab_samples"])
            st.session_state.lab_results.append(result)
            st.session_state.lab_samples_submitted.append(order)
            st.session_state.lab_orders.append(order)
            st.session_state.decisions["lab_orders"] = st.session_state.lab_orders

            # Log the lab test event
            jl.log_event(
                event_type='lab_test',
                location_id=village_id,
                cost_time=costs['time'],
                cost_budget=costs['budget'],
                payload={
                    'sample_type': sample_type,
                    'test': test,
                    'source_description': source_description or "Unspecified source",
                    'sample_id': result.get('sample_id'),
                    'placed_day': st.session_state.current_day,
                    'ready_day': result.get('ready_day'),
                    'patient_id': selected_patient,
                    'credits_used': costs['credits']
                }
            )

            st.success(
                f"Lab order submitted. Result: {result['result']} "
                f"(turnaround {result['days_to_result']} days)."
            )
            st.rerun()


    if st.session_state.get('lab_results'):
        st.markdown(f"### {t('lab_results', default='Lab results')}")
        df = pd.DataFrame(st.session_state.lab_results).copy()

        villages_lookup = truth["villages"].set_index("village_id")["village_name"].to_dict()
        if "village_id" in df.columns:
            df["village"] = df["village_id"].map(villages_lookup).fillna(df["village_id"])

        if "test_display" not in df.columns:
            df["test_display"] = df.get("test", "").map(lab_test_label) if "test" in df.columns else ""

        day_now = int(st.session_state.get("current_day", 1))
        if "ready_day" in df.columns:
            df["days_remaining"] = df.apply(
                lambda r: max(0, int(r.get("ready_day", day_now)) - day_now)
                if str(r.get("result", "")).upper() == "PENDING"
                else 0,
                axis=1,
            )

        show_cols = [
            "sample_id", "sample_type", "village", "test_display",
            "source_description", "patient_id", "placed_day", "ready_day",
            "days_remaining", "result"
        ]
        show_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
