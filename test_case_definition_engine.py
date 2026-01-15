"""
Tests for structured case definition engine and lab logic.
"""

import sys
from unittest.mock import MagicMock

sys.modules["streamlit"] = MagicMock()

import outbreak_logic


def _build_case_def():
    return {
        "time_window": {"start": "2024-10-12", "end": "2024-10-22"},
        "villages": ["V1", "V2", "V3", "V4"],
        "exclusions": ["Malaria"],
        "tiers": {
            "suspected": {
                "required_any": ["fever"],
                "optional_symptoms": ["myalgia", "conjunctival_suffusion"],
                "min_optional": 0,
                "epi_link_required": False,
                "lab_required": False,
                "lab_tests": [],
            },
            "probable": {
                "required_any": ["fever"],
                "optional_symptoms": ["myalgia", "conjunctival_suffusion"],
                "min_optional": 1,
                "epi_link_required": True,
                "lab_required": False,
                "lab_tests": [],
            },
            "confirmed": {
                "required_any": ["fever"],
                "optional_symptoms": ["myalgia"],
                "min_optional": 1,
                "epi_link_required": False,
                "lab_required": True,
                "lab_tests": ["LEPTO_PCR_BLOOD"],
            },
        },
    }


def test_case_definition_changes_case_counts():
    truth = outbreak_logic.load_truth_data("scenarios/lepto_rivergate/data")
    individuals_full = truth["individuals_seed"].copy()
    case_def = _build_case_def()
    base_cases = outbreak_logic.apply_case_definition(
        individuals_full,
        {"scenario_id": "lepto_rivergate", "case_definition_structured": case_def},
    )
    stricter = _build_case_def()
    stricter["tiers"]["suspected"]["min_optional"] = 1
    strict_cases = outbreak_logic.apply_case_definition(
        individuals_full,
        {"scenario_id": "lepto_rivergate", "case_definition_structured": stricter},
    )
    assert len(strict_cases) <= len(base_cases)


def test_exclusion_rule_out_removes_case():
    truth = outbreak_logic.load_truth_data("scenarios/lepto_rivergate/data")
    individuals_full = truth["individuals_seed"].copy()
    case_def = _build_case_def()
    cases = outbreak_logic.apply_case_definition(
        individuals_full,
        {"scenario_id": "lepto_rivergate", "case_definition_structured": case_def},
    )
    assert len(cases) > 0
    patient_id = cases.iloc[0]["person_id"]
    lab_results = [{"patient_id": patient_id, "test": "MALARIA_RDT", "result": "POSITIVE"}]
    filtered = outbreak_logic.apply_case_definition(
        individuals_full,
        {
            "scenario_id": "lepto_rivergate",
            "case_definition_structured": case_def,
            "lab_results": lab_results,
        },
    )
    assert patient_id not in filtered["person_id"].astype(str).tolist()


def test_lab_turnaround_delayed():
    truth = outbreak_logic.load_truth_data("scenarios/lepto_rivergate/data")
    order = {
        "sample_type": "blood",
        "village_id": "V1",
        "test": "LEPTO_MAT",
        "placed_day": 1,
        "days_since_onset": 2,
    }
    result = outbreak_logic.process_lab_order(order, truth["lab_samples"], random_seed=1)
    assert result["ready_day"] >= 3


def test_lepto_config_has_no_je_tests():
    config = outbreak_logic.load_scenario_config("lepto_rivergate")
    codes = [t["code"] for t in config.get("lab_tests", [])]
    assert not any(code.startswith("JE_") for code in codes)


def test_study_design_validation_requires_justification():
    config = outbreak_logic.load_scenario_config("lepto_rivergate")
    decisions = {"study_design": {"type": "cohort"}}
    ok, missing = outbreak_logic.validate_study_design_requirements(decisions, config)
    assert not ok
    assert "justification" in missing


if __name__ == "__main__":
    test_case_definition_changes_case_counts()
    test_exclusion_rule_out_removes_case()
    test_lab_turnaround_delayed()
    test_lepto_config_has_no_je_tests()
    test_study_design_validation_requires_justification()
    print("✅ CASE DEFINITION ENGINE TESTS PASSED")
