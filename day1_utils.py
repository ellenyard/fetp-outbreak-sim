"""
Day 1 Utilities for FETP Outbreak Simulation
=============================================

This module provides helper functions and data for Day 1 of the outbreak
investigation simulation. Day 1 focuses on:

- Initial case finding from clinic logs
- Building and refining case definitions
- Classifying cases as suspected/probable/confirmed
- Reviewing differential diagnoses

Key concepts:
- Clinic log entries: Raw patient records from health facilities
- Case cards: Summary cards for discussing individual cases
- Case definitions: Criteria for classifying cases (WHO-style tiered approach)
- Differential diagnosis: Ruling out other conditions

The module supports multiple scenarios (JE/AES in Sidero Valley, Leptospirosis
in Rivergate) with scenario-specific symptom schemas and case data.
"""

from __future__ import annotations

import json
import numpy as np
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


# =============================================================================
# DEFAULT DAY 1 ASSETS
# =============================================================================
# These provide fallback data if scenario-specific JSON files are incomplete.
# Each scenario has:
#   - clinic_log_entries: Simulated patient visits to health facilities
#   - case_cards: Summary cards for case review exercises
#   - lab_brief: Early laboratory results for discussion

DEFAULT_DAY1_ASSETS: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # AES (Acute Encephalitis Syndrome) / Japanese Encephalitis Scenario
    # Setting: Sidero Valley - rural Southeast Asian villages
    # =========================================================================
    "aes_sidero_valley": {
        # Clinic log entries simulate handwritten health center records
        # Each entry has:
        #   - entry_id: Unique identifier
        #   - raw_text: What the user sees (realistic messy notes)
        #   - answer_key: Structured data for auto-grading abstraction
        #   - truth_case: Whether this is truly a case (for scoring)
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
                "truth_case": True,  # Classic AES presentation
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
                "truth_case": False,  # Likely measles or allergic reaction
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
                "truth_case": True,  # Encephalitic features
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
                "truth_case": False,  # GI illness, not AES
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
                "truth_case": True,  # Meningeal signs
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
                "truth_case": False,  # Syncope without fever
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
                "truth_case": True,  # Febrile seizure / AES
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
                "truth_case": False,  # Respiratory illness
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
                "truth_case": True,  # Altered consciousness
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
                "truth_case": False,  # Viral exanthem
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
                "truth_case": True,  # Meningeal + exposure clue
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
                "truth_case": False,  # Food poisoning
            },
        ],

        # Case cards: Used for group exercises on case classification
        # Students discuss whether each card meets case definition criteria
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

        # Lab brief: Early results shared on Day 1 for discussion
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

    # =========================================================================
    # Leptospirosis Scenario
    # Setting: Rivergate municipality - post-typhoon flooding
    # =========================================================================
    "lepto_rivergate": {
        # Clinic entries focus on post-flood illness patterns
        # Key symptoms: fever, myalgia (esp. calf), conjunctival suffusion, jaundice
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
                "truth_case": True,  # Classic lepto triad
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
                "truth_case": False,  # Likely URI
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
                "truth_case": True,  # Icteric lepto (Weil's)
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
                "truth_case": False,  # Exposure only, not meeting criteria
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
                "truth_case": True,  # Severe with renal involvement
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
                "truth_case": False,  # Foodborne illness
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
                "truth_case": True,  # Classic lepto
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
                "truth_case": False,  # No exposure, respiratory
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
                "truth_case": True,  # Occupational exposure
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
                "truth_case": False,  # Non-specific, no fever
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
                "truth_case": True,  # Early lepto
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
                "truth_case": False,  # Non-specific febrile
            },
        ],

        # Case cards for leptospirosis scenario
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

        # Lab brief for leptospirosis
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

    # =========================================================================
    # Default/Fallback (empty structure for unknown scenarios)
    # =========================================================================
    "default": {
        "clinic_log_entries": [],
        "case_cards": [],
        "lab_brief": {"summary": "", "results": [], "limitations": [], "next_steps": []},
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries, with override values taking precedence.

    This allows scenario-specific JSON files to partially override defaults
    while inheriting values they don't specify.

    Args:
        base: The base dictionary (defaults)
        override: Dictionary with values to override

    Returns:
        Merged dictionary combining both, with override taking precedence

    Example:
        >>> base = {"a": 1, "b": {"x": 10, "y": 20}}
        >>> override = {"b": {"x": 100}}
        >>> _deep_merge(base, override)
        {"a": 1, "b": {"x": 100, "y": 20}}
    """
    merged = deepcopy(base)
    for key, value in override.items():
        # If both are dicts, merge recursively
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            # Otherwise, override takes precedence
            merged[key] = value
    return merged


# =============================================================================
# ASSET LOADING
# =============================================================================

def load_day1_assets(scenario_id: str) -> Dict[str, Any]:
    """
    Load Day 1 assets for a scenario, merging defaults with JSON overrides.

    Looks for: scenarios/{scenario_id}/data/day1_assets.json

    If the JSON file exists, its values override the built-in defaults.
    If missing keys exist in defaults, they're preserved.

    Args:
        scenario_id: The scenario identifier (e.g., "aes_sidero_valley")

    Returns:
        Complete Day 1 assets dictionary with all required keys
    """
    scenario_root = Path(f"scenarios/{scenario_id}/data")
    asset_path = scenario_root / "day1_assets.json"

    # Load JSON override if it exists
    data: Dict[str, Any] = {}
    if asset_path.exists():
        data = json.loads(asset_path.read_text())

    # Get defaults for this scenario (or generic default)
    defaults = DEFAULT_DAY1_ASSETS.get(scenario_id, DEFAULT_DAY1_ASSETS["default"])

    # Merge: JSON values override defaults, missing values inherited
    return _deep_merge(defaults, data)


# =============================================================================
# CASE FINDING
# =============================================================================

def get_case_finding_sources(assets: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get the list of case finding sources from Day 1 assets.

    Case finding sources represent places where cases might be found:
    - Clinic registers
    - Hospital records
    - Community health worker reports
    - School absentee lists

    Each source has detection probability and reporting delay parameters
    to simulate real-world under-ascertainment.

    Args:
        assets: Day 1 assets dictionary

    Returns:
        List of source dictionaries with entries and parameters
    """
    # Use explicit sources if defined
    sources = assets.get("case_finding_sources")
    if sources:
        return sources

    # Fall back to wrapping clinic entries as a single source
    clinic_entries = assets.get("clinic_log_entries", [])
    return [
        {
            "source_id": "clinic_log",
            "label": "Clinic register",
            "entries": clinic_entries,
            "detection_probability": 0.8,  # 80% chance of detecting each case
            "reporting_delay_days": 0,      # Available immediately
        }
    ]


def run_case_finding(
    sources: List[Dict[str, Any]],
    case_def: Dict[str, Any],
    scenario_config: Dict[str, Any],
    current_day: int,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Simulate case finding using the user's case definition.

    This function:
    1. Iterates through case finding sources (clinic logs, etc.)
    2. Applies detection probability (simulates under-ascertainment)
    3. Applies reporting delays (some sources not available until later days)
    4. Classifies detected cases using the structured case definition

    The random seed ensures reproducible results for the same inputs.

    Args:
        sources: List of case finding sources with entries
        case_def: User's structured case definition
        scenario_config: Scenario configuration with symptom mappings
        current_day: Current simulation day (affects reporting delays)
        random_seed: Seed for reproducible randomization

    Returns:
        Dictionary with results for each source, including matched cases
    """
    rng = np.random.default_rng(random_seed)
    results = {"sources": []}

    for source in sources:
        detected_entries = []

        # Get source parameters
        detection_prob = float(source.get("detection_probability", 0.8))
        delay_days = int(source.get("reporting_delay_days", 0) or 0)

        # Check if source is available yet (reporting delay)
        if current_day <= delay_days:
            # Source not yet reporting - mark as pending
            results["sources"].append({
                "source_id": source.get("source_id"),
                "label": source.get("label"),
                "matches": [],
                "pending": True,
            })
            continue

        # Process each entry in this source
        for entry in source.get("entries", []):
            row = entry.get("answer_key", entry)

            # Apply detection probability (simulate under-ascertainment)
            if rng.random() > detection_prob:
                continue  # Case not detected this time

            # Classify using the user's case definition
            classification = match_case_definition_structured(row, case_def, scenario_config)

            # Only include if classified as a case
            if classification in {"suspected", "probable", "confirmed"}:
                detected_entries.append({**row, "classification": classification})

        results["sources"].append({
            "source_id": source.get("source_id"),
            "label": source.get("label"),
            "matches": detected_entries,
            "pending": False,
        })

    return results


# =============================================================================
# CASE DEFINITION MATCHING
# =============================================================================

def get_clinic_log_schema(scenario_type: str) -> List[str]:
    """
    Get the expected column names for clinic log abstraction.

    Different scenarios have different symptom columns:
    - Lepto: myalgia, conjunctival suffusion, jaundice
    - AES/JE: rash, vomiting, diarrhea, seizure

    Args:
        scenario_type: Either "lepto" or other (defaults to AES schema)

    Returns:
        List of column names for the clinic log abstraction form
    """
    if scenario_type == "lepto":
        return [
            "patient_id",
            "visit_date",
            "age",
            "sex",
            "village",
            "symptom_onset_date",
            "fever_y_n",
            "myalgia_y_n",              # Muscle pain, especially calves
            "conjunctival_suffusion_y_n",  # Red eyes (not conjunctivitis)
            "jaundice_y_n",             # Yellow skin/eyes
            "notes",
        ]

    # Default: AES/JE schema
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


def _normalize_yes_no(value: Any) -> Optional[bool]:
    """
    Convert various yes/no representations to boolean.

    Handles common variations from form inputs and data entry:
    - "Yes", "Y", "true", "1" -> True
    - "No", "N", "false", "0" -> False
    - "Unknown", "N/A", "" -> None

    Args:
        value: Raw value from data entry

    Returns:
        True, False, or None (for unknown/missing)
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    # Positive indicators
    if text in {"yes", "y", "true", "1"}:
        return True

    # Negative indicators
    if text in {"no", "n", "false", "0"}:
        return False

    # Unknown/missing indicators
    if text in {"unknown", "unsure", "na", "n/a", ""}:
        return None

    # Unrecognized value - treat as unknown
    return None


def _symptom_value_from_row(
    row: Dict[str, Any],
    symptom_key: str,
    scenario_config: Dict[str, Any]
) -> Optional[bool]:
    """
    Extract a symptom value from a clinic log row using scenario mappings.

    The scenario config defines how internal symptom names map to actual
    column names in clinic data. For example:
    - "fever" might map to "fever_y_n" column
    - "myalgia" might require checking the "notes" field

    Args:
        row: A clinic log row (dictionary)
        symptom_key: Internal symptom name (e.g., "fever", "myalgia")
        scenario_config: Config with symptom_field_map

    Returns:
        True if symptom present, False if absent, None if unknown
    """
    # Get the field mapping for this symptom
    mapping = scenario_config.get("symptom_field_map", {}).get(symptom_key, {})
    field = mapping.get("clinic")

    if field and field in row:
        # Special case: notes field - search for symptom text
        if field == "notes":
            symptom_text = symptom_key.replace("_", " ")
            return symptom_text in str(row.get(field, "")).lower()

        # Normal field - normalize yes/no value
        return _normalize_yes_no(row.get(field))

    return None


def match_case_definition_structured(
    row: Dict[str, Any],
    case_def: Dict[str, Any],
    scenario_config: Dict[str, Any]
) -> str:
    """
    Classify a clinic record using a structured case definition.

    Implements WHO-style tiered case definitions:
    - Confirmed: Lab-confirmed cases (highest specificity)
    - Probable: Clinical + epidemiological link (medium specificity)
    - Suspected: Clinical criteria only (highest sensitivity)

    The function checks tiers in order of specificity (confirmed -> probable
    -> suspected) and returns the highest tier the case qualifies for.

    Case definition structure:
    {
        "tiers": {
            "suspected": {
                "required_any": ["fever"],      # At least one required
                "optional_symptoms": ["myalgia", "jaundice"],
                "min_optional": 0               # How many optional needed
            },
            ...
        }
    }

    Args:
        row: Patient record dictionary
        case_def: Structured case definition with tiers
        scenario_config: Scenario config with symptom mappings

    Returns:
        Classification string: "confirmed", "probable", "suspected", or "not_a_case"
    """
    if not case_def:
        return "not_a_case"

    tiers = case_def.get("tiers", {})

    # Check tiers in order of specificity (highest first)
    for tier_name in ["confirmed", "probable", "suspected"]:
        tier = tiers.get(tier_name, {})

        # Get tier criteria
        required_any = tier.get("required_any", []) or []
        optional = tier.get("optional_symptoms", []) or []
        min_optional = int(tier.get("min_optional", 0) or 0)

        # Check required symptoms (at least one must be present)
        any_ok = True
        if required_any:
            any_ok = any(
                _symptom_value_from_row(row, s, scenario_config) is True
                for s in required_any
            )

        # Count how many optional symptoms are present
        optional_count = sum(
            _symptom_value_from_row(row, s, scenario_config) is True
            for s in optional
        )

        # Check if this tier's criteria are met
        if any_ok and optional_count >= min_optional:
            return tier_name

    return "not_a_case"


def parse_case_definition_template(md_text: str) -> Dict[str, str]:
    """
    Extract case definition sections from a WHO-style markdown template.

    Parses markdown text looking for headers like:
    - ### Suspected Case
    - ### Probable Case
    - ### Confirmed Case

    Args:
        md_text: Markdown text of case definition template

    Returns:
        Dictionary with keys "suspected", "probable", "confirmed"
        containing the text content of each section
    """
    sections = {"suspected": "", "probable": "", "confirmed": ""}
    current = None

    for line in md_text.splitlines():
        lower_line = line.strip().lower()

        # Detect section headers
        if lower_line.startswith("### suspected"):
            current = "suspected"
            continue
        if lower_line.startswith("### probable"):
            current = "probable"
            continue
        if lower_line.startswith("### confirmed"):
            current = "confirmed"
            continue

        # Check for end of section (another ### header about cases)
        if current:
            if line.strip().startswith("### ") and lower_line.endswith("case"):
                current = None
                continue
            sections[current] += f"{line}\n"

    # Clean up whitespace
    return {k: v.strip() for k, v in sections.items()}


# =============================================================================
# DIFFERENTIAL DIAGNOSIS
# =============================================================================

def get_differential_prompts(scenario_type: str) -> List[Dict[str, str]]:
    """
    Get differential diagnosis discussion prompts for a scenario.

    These prompts help learners think through alternative diagnoses:
    - What findings would SUPPORT this alternative diagnosis?
    - What findings ARGUE AGAINST this alternative?

    Args:
        scenario_type: Either "lepto" or other (defaults to AES differentials)

    Returns:
        List of differential diagnosis prompts with supporting/against criteria
    """
    if scenario_type == "lepto":
        # Leptospirosis differentials: other causes of fever + jaundice
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

    # Default: AES/encephalitis differentials
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
