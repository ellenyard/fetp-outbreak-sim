"""Utility helpers for Day 1 workflows."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_DAY1_ASSETS: Dict[str, Dict[str, Any]] = {
    "aes_sidero_valley": {
        "clinic_log_entries": [
            {
                "entry_id": "CL-01",
                "raw_text": "06/03 09:10 Nalu HC - 6y M, high fever 39C, seizures overnight, vomiting x2. Onset 6/02.",
                "answer_key": {
                    "patient_id": "CL-01",
                    "visit_date": "2025-06-03",
                    "age": "6",
                    "sex": "M",
                    "village": "Nalu",
                    "symptom_onset_date": "2025-06-02",
                    "fever_y_n": "Yes",
                    "rash_y_n": "No",
                    "vomiting_y_n": "Yes",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "Yes",
                    "notes": "Seizures overnight; vomiting twice.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-02",
                "raw_text": "06/03 11:45 Kabwe - 4y F, fever and rash, itchy. No vomiting. Onset 6/01.",
                "answer_key": {
                    "patient_id": "CL-02",
                    "visit_date": "2025-06-03",
                    "age": "4",
                    "sex": "F",
                    "village": "Kabwe",
                    "symptom_onset_date": "2025-06-01",
                    "fever_y_n": "Yes",
                    "rash_y_n": "Yes",
                    "vomiting_y_n": "No",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "No",
                    "notes": "Itchy rash.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-03",
                "raw_text": "06/04 08:20 Nalu - 8y M brought for confusion, sleepy, fever 38.8. Mother unsure onset.",
                "answer_key": {
                    "patient_id": "CL-03",
                    "visit_date": "2025-06-04",
                    "age": "8",
                    "sex": "M",
                    "village": "Nalu",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "rash_y_n": "Unknown",
                    "vomiting_y_n": "Unknown",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "Unknown",
                    "notes": "Confusion and sleepiness noted.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-04",
                "raw_text": "06/04 10:00 Tamu - 2y F, watery diarrhea x1 day, no fever, playful.",
                "answer_key": {
                    "patient_id": "CL-04",
                    "visit_date": "2025-06-04",
                    "age": "2",
                    "sex": "F",
                    "village": "Tamu",
                    "symptom_onset_date": "2025-06-03",
                    "fever_y_n": "No",
                    "rash_y_n": "No",
                    "vomiting_y_n": "No",
                    "diarrhea_y_n": "Yes",
                    "seizure_y_n": "No",
                    "notes": "Watery diarrhea only.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-05",
                "raw_text": "06/04 13:15 Nalu - 7y F, fever, vomiting, stiff neck. No rash. Onset 6/03.",
                "answer_key": {
                    "patient_id": "CL-05",
                    "visit_date": "2025-06-04",
                    "age": "7",
                    "sex": "F",
                    "village": "Nalu",
                    "symptom_onset_date": "2025-06-03",
                    "fever_y_n": "Yes",
                    "rash_y_n": "No",
                    "vomiting_y_n": "Yes",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "Unknown",
                    "notes": "Stiff neck noted.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-06",
                "raw_text": "06/05 09:40 Kabwe - 12y M, fainted at school, no fever, headache only.",
                "answer_key": {
                    "patient_id": "CL-06",
                    "visit_date": "2025-06-05",
                    "age": "12",
                    "sex": "M",
                    "village": "Kabwe",
                    "symptom_onset_date": "2025-06-05",
                    "fever_y_n": "No",
                    "rash_y_n": "No",
                    "vomiting_y_n": "No",
                    "diarrhea_y_n": "No",
                    "seizure_y_n": "No",
                    "notes": "Fainted at school.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-07",
                "raw_text": "06/05 14:05 Nalu - 5y F, fever 39.2, seizure this morning, mother says started yesterday.",
                "answer_key": {
                    "patient_id": "CL-07",
                    "visit_date": "2025-06-05",
                    "age": "5",
                    "sex": "F",
                    "village": "Nalu",
                    "symptom_onset_date": "2025-06-04",
                    "fever_y_n": "Yes",
                    "rash_y_n": "Unknown",
                    "vomiting_y_n": "Unknown",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "Yes",
                    "notes": "Seizure this morning.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-08",
                "raw_text": "06/05 16:20 Moba - 9y M, fever and cough, no neuro signs. onset 6/04.",
                "answer_key": {
                    "patient_id": "CL-08",
                    "visit_date": "2025-06-05",
                    "age": "9",
                    "sex": "M",
                    "village": "Moba",
                    "symptom_onset_date": "2025-06-04",
                    "fever_y_n": "Yes",
                    "rash_y_n": "No",
                    "vomiting_y_n": "No",
                    "diarrhea_y_n": "No",
                    "seizure_y_n": "No",
                    "notes": "Fever with cough.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-09",
                "raw_text": "06/06 08:35 Nalu - 3y F, fever, vomiting, very sleepy, no rash.",
                "answer_key": {
                    "patient_id": "CL-09",
                    "visit_date": "2025-06-06",
                    "age": "3",
                    "sex": "F",
                    "village": "Nalu",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "rash_y_n": "No",
                    "vomiting_y_n": "Yes",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "Unknown",
                    "notes": "Very sleepy; onset unclear.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-10",
                "raw_text": "06/06 13:50 Tamu - 10y M, rash and sore throat, afebrile.",
                "answer_key": {
                    "patient_id": "CL-10",
                    "visit_date": "2025-06-06",
                    "age": "10",
                    "sex": "M",
                    "village": "Tamu",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "No",
                    "rash_y_n": "Yes",
                    "vomiting_y_n": "No",
                    "diarrhea_y_n": "No",
                    "seizure_y_n": "No",
                    "notes": "Rash with sore throat.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-11",
                "raw_text": "06/07 09:05 Kabwe - 6y F, fever, stiff neck, confused, mother mentions rice paddies.",
                "answer_key": {
                    "patient_id": "CL-11",
                    "visit_date": "2025-06-07",
                    "age": "6",
                    "sex": "F",
                    "village": "Kabwe",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "rash_y_n": "Unknown",
                    "vomiting_y_n": "Unknown",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "Unknown",
                    "notes": "Stiff neck, confusion. Exposure note in margins.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-12",
                "raw_text": "06/07 15:30 Nalu - 14y M, vomiting after bad food, no fever, resolved.",
                "answer_key": {
                    "patient_id": "CL-12",
                    "visit_date": "2025-06-07",
                    "age": "14",
                    "sex": "M",
                    "village": "Nalu",
                    "symptom_onset_date": "2025-06-07",
                    "fever_y_n": "No",
                    "rash_y_n": "No",
                    "vomiting_y_n": "Yes",
                    "diarrhea_y_n": "Unknown",
                    "seizure_y_n": "No",
                    "notes": "Food-related vomiting.",
                },
                "truth_case": False,
            },
        ],
        "case_cards": [
            {
                "case_id": "CARD-01",
                "title": "Severe neuro case",
                "clinical": "High fever, seizures, altered mental status, stiff neck.",
                "exposure": "Lives near rice paddies; no net use.",
                "lab": "CSF pleocytosis pending.",
                "missing_data": "Exact onset date unclear.",
                "tags": ["fever", "seizure", "neuro"],
            },
            {
                "case_id": "CARD-02",
                "title": "Atypical rash case",
                "clinical": "Fever with rash, no neuro signs.",
                "exposure": "School cluster reported.",
                "lab": "No labs ordered yet.",
                "missing_data": "No neuro exam documented.",
                "tags": ["fever", "rash"],
            },
            {
                "case_id": "CARD-03",
                "title": "Mild neuro symptoms",
                "clinical": "Low-grade fever, confusion, vomiting.",
                "exposure": "Sibling with fever last week.",
                "lab": "Pending CSF.",
                "missing_data": "No seizure history.",
                "tags": ["fever", "vomiting", "neuro"],
            },
            {
                "case_id": "CARD-04",
                "title": "Non-case trauma",
                "clinical": "Headache after fall, afebrile.",
                "exposure": "No notable exposures.",
                "lab": "No labs.",
                "missing_data": "Onset date uncertain.",
                "tags": ["trauma"],
            },
            {
                "case_id": "CARD-05",
                "title": "Seizure without fever",
                "clinical": "Single seizure, no fever reported.",
                "exposure": "Lives in Nalu, vaccinated per mother.",
                "lab": "No labs yet.",
                "missing_data": "Temperature not measured.",
                "tags": ["seizure"],
            },
            {
                "case_id": "CARD-06",
                "title": "Classic AES presentation",
                "clinical": "Fever 40C, seizures, coma.",
                "exposure": "Mosquito bites noted; pig pen nearby.",
                "lab": "IgM JE pending.",
                "missing_data": "Exposure timing uncertain.",
                "tags": ["fever", "seizure", "neuro"],
            },
        ],
        "lab_brief": {
            "summary": "The regional lab returned preliminary IgM testing on a subset of CSF/serum samples. Results are early and limited.",
            "results": [
                {"sample_id": "LAB-01", "test": "JE IgM (serum)", "result": "Positive"},
                {"sample_id": "LAB-02", "test": "JE IgM (CSF)", "result": "Pending"},
                {"sample_id": "LAB-03", "test": "JE IgM (serum)", "result": "Negative"},
                {"sample_id": "LAB-04", "test": "Malaria RDT", "result": "Negative"},
                {"sample_id": "LAB-05", "test": "Bacterial culture", "result": "Pending"},
            ],
            "limitations": [
                "IgM can be negative early in illness.",
                "Cross-reactivity with other flaviviruses is possible.",
                "Small sample size; results may not represent all cases.",
            ],
            "next_steps": [
                "Collect paired sera for seroconversion.",
                "Request PCR for JE virus on available CSF.",
                "Continue to rule out bacterial meningitis.",
            ],
        },
    },
    "lepto_rivergate": {
        "clinic_log_entries": [
            {
                "entry_id": "CL-01",
                "raw_text": "08/14 09:00 Northbend RHU - 32y M, fever 39C, calf pain, red eyes after flood cleanup. Onset 8/12.",
                "answer_key": {
                    "patient_id": "CL-01",
                    "visit_date": "2025-08-14",
                    "age": "32",
                    "sex": "M",
                    "village": "Northbend",
                    "symptom_onset_date": "2025-08-12",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "Yes",
                    "conjunctival_suffusion_y_n": "Yes",
                    "jaundice_y_n": "No",
                    "notes": "Flood cleanup exposure noted.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-02",
                "raw_text": "08/14 10:30 Southbank - 24y F, fever and cough, no myalgia, no red eyes.",
                "answer_key": {
                    "patient_id": "CL-02",
                    "visit_date": "2025-08-14",
                    "age": "24",
                    "sex": "F",
                    "village": "Southbank",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "No",
                    "conjunctival_suffusion_y_n": "No",
                    "jaundice_y_n": "No",
                    "notes": "Respiratory symptoms.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-03",
                "raw_text": "08/15 08:15 Northbend - 41y F, fever, severe calf pain, yellow eyes. Onset 8/13.",
                "answer_key": {
                    "patient_id": "CL-03",
                    "visit_date": "2025-08-15",
                    "age": "41",
                    "sex": "F",
                    "village": "Northbend",
                    "symptom_onset_date": "2025-08-13",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "Yes",
                    "conjunctival_suffusion_y_n": "Unknown",
                    "jaundice_y_n": "Yes",
                    "notes": "Jaundice observed.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-04",
                "raw_text": "08/15 11:05 East Pier - 19y M, mild fever, no myalgia, wading in flood water.",
                "answer_key": {
                    "patient_id": "CL-04",
                    "visit_date": "2025-08-15",
                    "age": "19",
                    "sex": "M",
                    "village": "East Pier",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "No",
                    "conjunctival_suffusion_y_n": "Unknown",
                    "jaundice_y_n": "No",
                    "notes": "Exposure without classic symptoms.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-05",
                "raw_text": "08/15 14:20 Northbend - 55y M, fever, severe myalgia, conjunctival suffusion, oliguria.",
                "answer_key": {
                    "patient_id": "CL-05",
                    "visit_date": "2025-08-15",
                    "age": "55",
                    "sex": "M",
                    "village": "Northbend",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "Yes",
                    "conjunctival_suffusion_y_n": "Yes",
                    "jaundice_y_n": "Unknown",
                    "notes": "Oliguria mentioned.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-06",
                "raw_text": "08/16 09:10 Southbank - 7y F, fever and diarrhea after street food.",
                "answer_key": {
                    "patient_id": "CL-06",
                    "visit_date": "2025-08-16",
                    "age": "7",
                    "sex": "F",
                    "village": "Southbank",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "No",
                    "conjunctival_suffusion_y_n": "No",
                    "jaundice_y_n": "No",
                    "notes": "GI complaint only.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-07",
                "raw_text": "08/16 13:40 Northbend - 28y F, fever, headache, calf pain, red eyes.",
                "answer_key": {
                    "patient_id": "CL-07",
                    "visit_date": "2025-08-16",
                    "age": "28",
                    "sex": "F",
                    "village": "Northbend",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "Yes",
                    "conjunctival_suffusion_y_n": "Yes",
                    "jaundice_y_n": "No",
                    "notes": "Classic triad noted.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-08",
                "raw_text": "08/16 16:25 East Pier - 30y M, fever, cough, no flood exposure mentioned.",
                "answer_key": {
                    "patient_id": "CL-08",
                    "visit_date": "2025-08-16",
                    "age": "30",
                    "sex": "M",
                    "village": "East Pier",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "No",
                    "conjunctival_suffusion_y_n": "No",
                    "jaundice_y_n": "No",
                    "notes": "Likely respiratory illness.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-09",
                "raw_text": "08/17 08:30 Northbend - 44y M, fever, jaundice, calf pain, cleaned barns after flood.",
                "answer_key": {
                    "patient_id": "CL-09",
                    "visit_date": "2025-08-17",
                    "age": "44",
                    "sex": "M",
                    "village": "Northbend",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "Yes",
                    "conjunctival_suffusion_y_n": "Unknown",
                    "jaundice_y_n": "Yes",
                    "notes": "Barn cleanup exposure.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-10",
                "raw_text": "08/17 11:10 Southbank - 60y F, fatigue only, no fever.",
                "answer_key": {
                    "patient_id": "CL-10",
                    "visit_date": "2025-08-17",
                    "age": "60",
                    "sex": "F",
                    "village": "Southbank",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "No",
                    "myalgia_y_n": "No",
                    "conjunctival_suffusion_y_n": "No",
                    "jaundice_y_n": "No",
                    "notes": "Fatigue only.",
                },
                "truth_case": False,
            },
            {
                "entry_id": "CL-11",
                "raw_text": "08/17 15:00 Northbend - 35y M, fever 38.7, red eyes, muscle aches. Onset 8/15.",
                "answer_key": {
                    "patient_id": "CL-11",
                    "visit_date": "2025-08-17",
                    "age": "35",
                    "sex": "M",
                    "village": "Northbend",
                    "symptom_onset_date": "2025-08-15",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "Yes",
                    "conjunctival_suffusion_y_n": "Yes",
                    "jaundice_y_n": "No",
                    "notes": "Classic early symptoms.",
                },
                "truth_case": True,
            },
            {
                "entry_id": "CL-12",
                "raw_text": "08/18 09:30 East Pier - 22y F, fever and headache, no red eyes, no myalgia.",
                "answer_key": {
                    "patient_id": "CL-12",
                    "visit_date": "2025-08-18",
                    "age": "22",
                    "sex": "F",
                    "village": "East Pier",
                    "symptom_onset_date": "Unknown",
                    "fever_y_n": "Yes",
                    "myalgia_y_n": "No",
                    "conjunctival_suffusion_y_n": "No",
                    "jaundice_y_n": "No",
                    "notes": "Headache without classic signs.",
                },
                "truth_case": False,
            },
        ],
        "case_cards": [
            {
                "case_id": "CARD-01",
                "title": "Severe Weil's disease",
                "clinical": "Fever, jaundice, oliguria, conjunctival suffusion.",
                "exposure": "Flood cleanup, barefoot.",
                "lab": "Creatinine elevated.",
                "missing_data": "MAT pending.",
                "tags": ["fever", "jaundice", "renal"],
            },
            {
                "case_id": "CARD-02",
                "title": "Mild febrile illness",
                "clinical": "Fever, headache, no myalgia.",
                "exposure": "No flood exposure reported.",
                "lab": "No labs.",
                "missing_data": "No exposure history.",
                "tags": ["fever"],
            },
            {
                "case_id": "CARD-03",
                "title": "Classic triad",
                "clinical": "Fever, calf myalgia, conjunctival suffusion.",
                "exposure": "Waded in flood water 1 week ago.",
                "lab": "IgM pending.",
                "missing_data": "No jaundice noted.",
                "tags": ["fever", "myalgia"],
            },
            {
                "case_id": "CARD-04",
                "title": "Respiratory illness",
                "clinical": "Cough, mild fever, no myalgia.",
                "exposure": "No animal exposure.",
                "lab": "No labs.",
                "missing_data": "No flood exposure history.",
                "tags": ["respiratory"],
            },
            {
                "case_id": "CARD-05",
                "title": "Atypical exposure",
                "clinical": "Fever and headache only.",
                "exposure": "Sewer worker after flood.",
                "lab": "CBC only.",
                "missing_data": "No myalgia recorded.",
                "tags": ["fever", "exposure"],
            },
            {
                "case_id": "CARD-06",
                "title": "Severe hemorrhagic",
                "clinical": "Fever, jaundice, hemoptysis, calf pain.",
                "exposure": "Barn cleanup after flood.",
                "lab": "Platelets low.",
                "missing_data": "MAT pending.",
                "tags": ["fever", "hemorrhage", "jaundice"],
            },
        ],
        "lab_brief": {
            "summary": "Preliminary testing returned IgM ELISA results on a small subset of samples.",
            "results": [
                {"sample_id": "LAB-01", "test": "Leptospira IgM ELISA", "result": "Positive"},
                {"sample_id": "LAB-02", "test": "Leptospira IgM ELISA", "result": "Negative"},
                {"sample_id": "LAB-03", "test": "MAT", "result": "Pending"},
                {"sample_id": "LAB-04", "test": "Dengue NS1", "result": "Negative"},
                {"sample_id": "LAB-05", "test": "Malaria RDT", "result": "Negative"},
            ],
            "limitations": [
                "IgM may be negative early in infection.",
                "MAT requires paired sera for confirmation.",
                "Cross-reactivity with other spirochetes possible.",
            ],
            "next_steps": [
                "Collect convalescent sera for MAT.",
                "Send PCR on blood/urine for early cases.",
                "Continue differential testing for dengue/malaria.",
            ],
        },
    },
    "default": {
        "clinic_log_entries": [],
        "case_cards": [],
        "lab_brief": {"summary": "", "results": [], "limitations": [], "next_steps": []},
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_day1_assets(scenario_id: str) -> Dict[str, Any]:
    """Load day 1 assets from scenario JSON with defaults for missing keys."""
    scenario_root = Path(f"scenarios/{scenario_id}/data")
    asset_path = scenario_root / "day1_assets.json"
    data: Dict[str, Any] = {}
    if asset_path.exists():
        data = json.loads(asset_path.read_text())
    defaults = DEFAULT_DAY1_ASSETS.get(scenario_id, DEFAULT_DAY1_ASSETS["default"])
    return _deep_merge(defaults, data)


def get_clinic_log_schema(scenario_type: str) -> List[str]:
    if scenario_type == "lepto":
        return [
            "patient_id",
            "visit_date",
            "age",
            "sex",
            "village",
            "symptom_onset_date",
            "fever_y_n",
            "myalgia_y_n",
            "conjunctival_suffusion_y_n",
            "jaundice_y_n",
            "notes",
        ]
    return [
        "patient_id",
        "visit_date",
        "age",
        "sex",
        "village",
        "symptom_onset_date",
        "fever_y_n",
        "rash_y_n",
        "vomiting_y_n",
        "diarrhea_y_n",
        "seizure_y_n",
        "notes",
    ]


def parse_case_definition_template(md_text: str) -> Dict[str, str]:
    """Extract suspected/probable/confirmed sections from a WHO-style template."""
    sections = {"suspected": "", "probable": "", "confirmed": ""}
    current = None
    for line in md_text.splitlines():
        if line.strip().lower().startswith("### suspected"):
            current = "suspected"
            continue
        if line.strip().lower().startswith("### probable"):
            current = "probable"
            continue
        if line.strip().lower().startswith("### confirmed"):
            current = "confirmed"
            continue
        if current:
            if line.strip().startswith("### ") and line.lower().strip().endswith("case"):
                current = None
                continue
            sections[current] += f"{line}\n"
    return {k: v.strip() for k, v in sections.items()}


def get_differential_prompts(scenario_type: str) -> List[Dict[str, str]]:
    if scenario_type == "lepto":
        return [
            {
                "dx": "Dengue fever",
                "supporting": "Fever with headache/myalgia, thrombocytopenia if available.",
                "against": "No rash/bleeding; flood exposure favors lepto.",
            },
            {
                "dx": "Malaria",
                "supporting": "Fever with chills, anemia in labs.",
                "against": "Conjunctival suffusion and jaundice with flood exposure less typical.",
            },
            {
                "dx": "Viral hepatitis",
                "supporting": "Jaundice, dark urine.",
                "against": "High fever and myalgia favor lepto.",
            },
            {
                "dx": "Typhoid fever",
                "supporting": "Sustained fever, abdominal pain.",
                "against": "Conjunctival suffusion/jaundice not classic.",
            },
        ]
    return [
        {
            "dx": "Bacterial meningitis",
            "supporting": "Fever, stiff neck, CSF neutrophils.",
            "against": "Lymphocytic CSF, no response to antibiotics.",
        },
        {
            "dx": "Cerebral malaria",
            "supporting": "Fever, coma, malaria exposure.",
            "against": "Negative RDT/smear, no travel to endemic zone.",
        },
        {
            "dx": "Toxic ingestion",
            "supporting": "Altered mental status without fever.",
            "against": "High fever and CSF pleocytosis.",
        },
    ]
