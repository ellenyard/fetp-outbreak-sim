"""Clinic and hospital record generation and parsing utilities.

Handles loading scenario data, generating clinic/hospital records,
parsing messy handwritten-style records, creating case records from
case-finding activities, and rendering records in the Streamlit UI.
"""

import json
import logging
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


def load_scenario_json(filename: str):
    """Load scenario-specific JSON data when available."""
    scenario_id = st.session_state.get("current_scenario")
    scenario_type = st.session_state.get("current_scenario_type")
    if not scenario_id:
        return None

    if scenario_type == "lepto":
        base_dir = Path("scenarios") / scenario_id / "data"
    else:
        base_dir = Path("scenarios") / scenario_id

    path = base_dir / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def generate_clinic_records(village_context="nalu"):
    """
    Generate messy, handwritten-style clinic records.
    Mix of AES cases and unrelated illnesses.
    Returns list of record dicts.

    Args:
        village_context: "nalu" (default - full messy list),
                        "kabwe" (mild fevers, cuts, 1-2 transferred AES),
                        "tamu" (coughs, snakebites, Panya traveler case)
    """
    scenario_type = st.session_state.get("current_scenario_type")
    if scenario_type == "lepto":
        scenario_records = load_scenario_json("clinic_records.json")
        if scenario_records:
            return scenario_records

    import random
    random.seed(42)

    # True AES cases that should be found (6-8 cases)
    true_aes_cases = [
        {
            "record_id": "NHC-0034",
            "date": "2-Jun",
            "patient": "Kwame A., male",
            "age": "7 yrs",
            "village": "Nalu",
            "complaint": "fever 3 days, confusion, jerking movements",
            "notes": "mother says child was playing near rice fields. referred to hosp.",
            "is_aes": True
        },
        {
            "record_id": "NHC-0041",
            "date": "4-Jun",
            "patient": "Esi M.",
            "age": "5",
            "village": "Nalu vill.",
            "complaint": "High fever, not responding to name, shaking",
            "notes": "very sick. Family has pigs. Sent to district hosp URGENT",
            "is_aes": True
        },
        {
            "record_id": "NHC-0047",
            "date": "5 June",
            "patient": "Yaw K. (boy)",
            "age": "9 years",
            "village": "Kabwe",
            "complaint": "fever, severe headache, vomited x3, then seizure in clinic",
            "notes": "Lives nr paddy fields. Admitted for obs then transferred",
            "is_aes": True
        },
        {
            "record_id": "NHC-0052",
            "date": "6/6",
            "patient": "Abena F.",
            "age": "4y",
            "village": "Nalu",
            "complaint": "feverish, drowsy, mother says 'not herself', stiff neck?",
            "notes": "neck stiffness uncertain - child crying. watch closely",
            "is_aes": True
        },
        {
            "record_id": "NHC-0058",
            "date": "7-June",
            "patient": "Kofi B.",
            "age": "11",
            "village": "Kabwe village",
            "complaint": "fever x4 days, confusion today, parents v. worried",
            "notes": "walks past pig coop to school daily. Referred to hosp",
            "is_aes": True
        },
        {
            "record_id": "NHC-0063",
            "date": "8 Jun",
            "patient": "Adwoa S., F",
            "age": "6 yr",
            "village": "Nalu",
            "complaint": "fever, then became unresponsive, jerking arms",
            "notes": "no net at home. near rice paddies. URGENT referral",
            "is_aes": True
        },
        {
            "record_id": "NHC-0071",
            "date": "9-Jun",
            "patient": "male child (name unclear)",
            "age": "~8",
            "village": "Nalu area",
            "complaint": "brought in fitting, high fever, confusion",
            "notes": "family farms rice + keeps pigs. transferred to DH",
            "is_aes": True
        },
    ]

    # Non-AES cases (noise - 18-22 records)
    non_aes_cases = [
        {
            "record_id": "NHC-0031",
            "date": "1-Jun",
            "patient": "Akua D.",
            "age": "34",
            "village": "Tamu",
            "complaint": "cough x2 weeks, some fever",
            "notes": "?TB - refer for sputum",
            "is_aes": False
        },
        {
            "record_id": "NHC-0032",
            "date": "1-Jun",
            "patient": "Mensah K.",
            "age": "45 yrs",
            "village": "Kabwe",
            "complaint": "painful urination, fever",
            "notes": "UTI. Gave antibiotics",
            "is_aes": False
        },
        {
            "record_id": "NHC-0033",
            "date": "2-Jun",
            "patient": "baby girl (Serwaa)",
            "age": "8 months",
            "village": "Nalu",
            "complaint": "diarrhea x3 days, not feeding well",
            "notes": "ORS given. mother counseled on feeding",
            "is_aes": False
        },
        {
            "record_id": "NHC-0035",
            "date": "2-Jun",
            "patient": "Owusu P.",
            "age": "52",
            "village": "Tamu",
            "complaint": "knee pain, swelling",
            "notes": "arthritis. gave pain meds",
            "is_aes": False
        },
        {
            "record_id": "NHC-0036",
            "date": "3-Jun",
            "patient": "Ama T.",
            "age": "28",
            "village": "Kabwe",
            "complaint": "pregnant, routine ANC visit",
            "notes": "28 weeks. All normal.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0037",
            "date": "3-Jun",
            "patient": "child (Kweku)",
            "age": "3",
            "village": "Nalu",
            "complaint": "fever, runny nose, cough",
            "notes": "common cold. supportive care",
            "is_aes": False
        },
        {
            "record_id": "NHC-0038",
            "date": "3 June",
            "patient": "Fatima A.",
            "age": "19",
            "village": "Tamu",
            "complaint": "headache, body pains, fever",
            "notes": "? malaria. RDT positive. Gave ACT.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0039",
            "date": "4-Jun",
            "patient": "elderly man (Nana K.)",
            "age": "~70",
            "village": "Kabwe",
            "complaint": "difficulty breathing, swollen legs",
            "notes": "heart failure? referred to hospital",
            "is_aes": False
        },
        {
            "record_id": "NHC-0040",
            "date": "4-Jun",
            "patient": "Adjoa M.",
            "age": "25",
            "village": "Nalu",
            "complaint": "skin rash, itching x1 week",
            "notes": "fungal infection. Gave cream.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0042",
            "date": "4-Jun",
            "patient": "Yaw A.",
            "age": "6",
            "village": "Tamu",
            "complaint": "ear pain, fever",
            "notes": "otitis media. antibiotics given",
            "is_aes": False
        },
        {
            "record_id": "NHC-0043",
            "date": "5-Jun",
            "patient": "Comfort O.",
            "age": "31",
            "village": "Kabwe",
            "complaint": "lower abdominal pain",
            "notes": "? PID. referred for further eval",
            "is_aes": False
        },
        {
            "record_id": "NHC-0044",
            "date": "5-Jun",
            "patient": "Kofi M.",
            "age": "40",
            "village": "Nalu",
            "complaint": "cut on hand from farming, infected",
            "notes": "wound cleaned, dressed, tetanus given",
            "is_aes": False
        },
        {
            "record_id": "NHC-0045",
            "date": "5-Jun",
            "patient": "Grace A.",
            "age": "15",
            "village": "Tamu",
            "complaint": "painful menstruation",
            "notes": "dysmenorrhea. pain meds given",
            "is_aes": False
        },
        {
            "record_id": "NHC-0046",
            "date": "5 Jun",
            "patient": "infant (Kwabena)",
            "age": "4 mo",
            "village": "Kabwe",
            "complaint": "immunization visit",
            "notes": "vaccines given. growing well.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0048",
            "date": "6-Jun",
            "patient": "Akosua B.",
            "age": "22",
            "village": "Nalu",
            "complaint": "vomiting, diarrhea since yesterday",
            "notes": "gastroenteritis. ORS, observe",
            "is_aes": False
        },
        {
            "record_id": "NHC-0049",
            "date": "6-Jun",
            "patient": "Kwame O.",
            "age": "55",
            "village": "Tamu",
            "complaint": "high BP at community screening",
            "notes": "BP 160/95. started on meds. f/u 2 weeks",
            "is_aes": False
        },
        {
            "record_id": "NHC-0050",
            "date": "6-Jun",
            "patient": "child (Ama)",
            "age": "2 yrs",
            "village": "Kabwe",
            "complaint": "not eating, mild fever, irritable",
            "notes": "teething? no serious illness. reassured mother",
            "is_aes": False
        },
        {
            "record_id": "NHC-0051",
            "date": "6/6",
            "patient": "Joseph K.",
            "age": "38",
            "village": "Nalu",
            "complaint": "back pain x1 month",
            "notes": "muscle strain from farming. rest + pain meds",
            "is_aes": False
        },
        {
            "record_id": "NHC-0053",
            "date": "7-Jun",
            "patient": "Afia S.",
            "age": "12",
            "village": "Tamu",
            "complaint": "fever, joint pains, headache",
            "notes": "malaria RDT neg. ? viral illness. observe",
            "is_aes": False
        },
        {
            "record_id": "NHC-0054",
            "date": "7-Jun",
            "patient": "Nana A.",
            "age": "65",
            "village": "Kabwe",
            "complaint": "blurry vision, eye pain",
            "notes": "? cataracts. referred to eye clinic",
            "is_aes": False
        },
        {
            "record_id": "NHC-0055",
            "date": "7-Jun",
            "patient": "Charity M.",
            "age": "29",
            "village": "Nalu",
            "complaint": "breast lump, worried",
            "notes": "small mobile lump. referred for mammo",
            "is_aes": False
        },
        {
            "record_id": "NHC-0056",
            "date": "7 Jun",
            "patient": "boy (Yaw)",
            "age": "10",
            "village": "Kabwe",
            "complaint": "fell from tree, arm pain",
            "notes": "? fracture. splinted, sent to hosp for xray",
            "is_aes": False
        },
        {
            "record_id": "NHC-0057",
            "date": "7-Jun",
            "patient": "Esi K.",
            "age": "8",
            "village": "Tamu",
            "complaint": "fever, vomiting, abdominal pain",
            "notes": "? acute abdomen. referred to hospital",
            "is_aes": False
        },
        {
            "record_id": "NHC-0059",
            "date": "8-Jun",
            "patient": "adult male",
            "age": "~30",
            "village": "Nalu",
            "complaint": "productive cough, night sweats",
            "notes": "TB suspect. sputum collected",
            "is_aes": False
        },
        {
            "record_id": "NHC-0060",
            "date": "8-Jun",
            "patient": "Abena K.",
            "age": "48",
            "village": "Kabwe",
            "complaint": "fatigue, weight loss, thirst",
            "notes": "? diabetes. referred for glucose test",
            "is_aes": False
        },
        {
            "record_id": "NHC-0061",
            "date": "8 Jun",
            "patient": "infant girl",
            "age": "6 mo",
            "village": "Tamu",
            "complaint": "rash on face and body",
            "notes": "eczema. gave moisturizer advice",
            "is_aes": False
        },
        {
            "record_id": "NHC-0062",
            "date": "8-Jun",
            "patient": "Kwesi A.",
            "age": "44",
            "village": "Nalu",
            "complaint": "epigastric pain after eating",
            "notes": "? peptic ulcer. gave antacids. diet advice",
            "is_aes": False
        },
    ]

    # Combine and shuffle
    all_records = true_aes_cases + non_aes_cases
    random.shuffle(all_records)

    # Filter based on village context
    if village_context == "kabwe":
        # Kabwe: mild fevers, cuts, 1-2 transferred AES cases
        kabwe_records = [r for r in all_records if r.get("village") == "Kabwe"]
        # Include only 1-2 AES cases from Kabwe
        kabwe_aes = [r for r in kabwe_records if r.get("is_aes")][:2]
        kabwe_non_aes = [r for r in kabwe_records if not r.get("is_aes")]
        return kabwe_aes + kabwe_non_aes

    elif village_context == "tamu":
        # Tamu: coughs, snakebites, and the "Panya" case (7yo who traveled to Nalu)
        tamu_records = [r for r in all_records if r.get("village") == "Tamu"]
        # Add Panya's case - 7yo girl who traveled to Nalu market
        panya_case = {
            "record_id": "NHC-0080",
            "date": "10-Jun",
            "patient": "Panya",
            "age": "7",
            "village": "Tamu",
            "complaint": "fever, confusion, difficulty walking",
            "notes": "Mother says traveled to Nalu market recently. Referred to district hospital.",
            "is_aes": True
        }
        return tamu_records + [panya_case]

    # Default: nalu - return existing messy list
    return all_records


def parse_clinic_record_age(age_str: str) -> int:
    """Parse messy age strings from clinic records into integer years."""
    if not age_str:
        return 0
    age_str = str(age_str).lower().strip()
    # Remove common suffixes
    age_str = re.sub(r'\s*(years?|yrs?|y|yr)\s*$', '', age_str)
    age_str = re.sub(r'\s*mo(nths?)?\s*$', '', age_str)
    # Handle approximate ages like "~8"
    age_str = age_str.replace('~', '').strip()
    try:
        return int(float(age_str))
    except (ValueError, TypeError):
        return 5  # Default for children if parsing fails


def parse_clinic_record_date(date_str: str, year: int = 2025) -> str:
    """Parse messy date strings from clinic records into YYYY-MM-DD format."""
    if not date_str:
        return None
    date_str = str(date_str).strip()

    # Handle various formats: "2-Jun", "4-Jun", "5 June", "6/6", "7-June", etc.
    month_map = {
        'jan': '01', 'january': '01',
        'feb': '02', 'february': '02',
        'mar': '03', 'march': '03',
        'apr': '04', 'april': '04',
        'may': '05',
        'jun': '06', 'june': '06',
        'jul': '07', 'july': '07',
        'aug': '08', 'august': '08',
        'sep': '09', 'september': '09',
        'oct': '10', 'october': '10',
        'nov': '11', 'november': '11',
        'dec': '12', 'december': '12',
    }

    # Try format like "2-Jun" or "5 June" or "7-June"
    match = re.match(r'(\d{1,2})[-\s]?([a-zA-Z]+)', date_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        for key, val in month_map.items():
            if month_name.startswith(key):
                return f"{year}-{val}-{day:02d}"

    # Try format like "6/6"
    match = re.match(r'(\d{1,2})/(\d{1,2})', date_str)
    if match:
        day_or_month = int(match.group(1))
        month_or_day = int(match.group(2))
        # Assume day/month format
        return f"{year}-{month_or_day:02d}-{day_or_month:02d}"

    return None


def parse_clinic_record_sex(patient_str: str) -> str:
    """Parse sex from patient description."""
    patient_lower = patient_str.lower()
    if 'male' in patient_lower or 'boy' in patient_lower:
        return 'M'
    if 'female' in patient_lower or 'girl' in patient_lower or ', f' in patient_lower:
        return 'F'
    # Default based on common names
    male_names = ['kwame', 'kofi', 'yaw', 'kwesi', 'kweku', 'kwabena']
    female_names = ['esi', 'ama', 'abena', 'adwoa', 'akua', 'afia']
    for name in male_names:
        if name in patient_lower:
            return 'M'
    for name in female_names:
        if name in patient_lower:
            return 'F'
    return 'M'  # Default


def parse_clinic_record_village(village_str: str) -> str:
    """Map clinic record village names to village_id."""
    village_lower = str(village_str).lower().strip()
    if 'nalu' in village_lower:
        return 'V1'
    elif 'kabwe' in village_lower:
        return 'V2'
    elif 'tamu' in village_lower:
        return 'V3'
    if 'north' in village_lower:
        return 'V1'
    if 'east' in village_lower:
        return 'V2'
    if 'south' in village_lower:
        return 'V3'
    if 'high' in village_lower:
        return 'V4'
    return 'V1'  # Default to Nalu


def create_found_case_records(clinic_records: list, selected_record_ids: list,
                               existing_individuals: pd.DataFrame,
                               existing_households: pd.DataFrame) -> tuple:
    """
    Create individual and household records for correctly identified AES cases from clinic records.

    Args:
        clinic_records: List of clinic record dicts
        selected_record_ids: List of record_ids that the user selected
        existing_individuals: Current individuals DataFrame
        existing_households: Current households DataFrame

    Returns:
        Tuple of (new_individuals_df, new_households_df) to be concatenated with existing data
    """
    # Find true positive selections (correctly identified AES cases)
    true_positive_records = [
        r for r in clinic_records
        if r['record_id'] in selected_record_ids and (r.get('truth_case', r.get('is_aes', False)))
    ]

    if not true_positive_records:
        return pd.DataFrame(), pd.DataFrame()

    # Get the highest existing person_id and hh_id numbers to avoid collisions
    existing_person_nums = []
    for pid in existing_individuals['person_id']:
        try:
            num = int(str(pid).replace('P', '').replace('_CF', ''))
            existing_person_nums.append(num)
        except (ValueError, AttributeError):
            pass
    max_person_num = max(existing_person_nums) if existing_person_nums else 0

    existing_hh_nums = []
    for hid in existing_households['hh_id']:
        try:
            num = int(str(hid).replace('HH', '').replace('_CF', ''))
            existing_hh_nums.append(num)
        except (ValueError, AttributeError):
            pass
    max_hh_num = max(existing_hh_nums) if existing_hh_nums else 0

    new_individuals = []
    new_households = []

    scenario_type = st.session_state.get("current_scenario_type")
    for i, record in enumerate(true_positive_records):
        # Create unique IDs for case-finding discovered cases
        person_id = f"P_CF{max_person_num + 1000 + i:03d}"
        hh_id = f"HH_CF{max_hh_num + 1000 + i:03d}"

        # Parse data from the clinic record
        age = parse_clinic_record_age(record.get('age', ''))
        sex = parse_clinic_record_sex(record.get('patient', ''))
        village_id = parse_clinic_record_village(record.get('village', ''))
        onset_date = parse_clinic_record_date(record.get('date', ''))

        # Infer severity from complaint/notes
        complaint = record.get('complaint', '').lower()
        notes = record.get('notes', '').lower()
        combined_text = complaint + ' ' + notes

        severe_neuro = any(word in combined_text for word in
                          ['seizure', 'fitting', 'unresponsive', 'jerking', 'convuls'])

        # Infer outcome - most clinic referrals lead to hospitalization
        outcome = 'hospitalized' if 'refer' in combined_text or 'hosp' in combined_text else 'recovered'

        # Determine occupation based on age
        if age < 5:
            occupation = 'child'
        elif age < 18:
            occupation = 'student'
        else:
            occupation = 'farmer'

        # Create individual record
        individual = {
            'person_id': person_id,
            'hh_id': hh_id,
            'village_id': village_id,
            'age': age,
            'sex': sex,
            'occupation': occupation,
            'onset_date': onset_date,
            'outcome': outcome,
            'name_hint': record.get('patient', ''),
            'found_via_case_finding': True,
            'clinic_record_id': record.get('record_id', ''),
        }
        if scenario_type == "lepto":
            individual.update({
                "symptoms_fever": "fever" in combined_text,
                "symptoms_myalgia": "myalgia" in combined_text or "calf" in combined_text,
                "symptoms_conjunctival_suffusion": "red eye" in combined_text or "conjunctival" in combined_text,
                "symptoms_jaundice": "jaundice" in combined_text or "yellow" in combined_text,
                "symptoms_renal_failure": "oliguria" in combined_text or "renal" in combined_text,
            })
        else:
            individual.update({
                'JE_vaccinated': False,
                'evening_outdoor_exposure': True,
                'true_je_infection': True,
                'symptomatic_AES': True,
                'severe_neuro': severe_neuro,
            })
        new_individuals.append(individual)

        # Create household record with typical outbreak characteristics
        # (pigs nearby, near rice fields, no nets - risk factors)
        household = {
            'hh_id': hh_id,
            'village_id': village_id,
        }
        if scenario_type == "lepto":
            household.update({
                "cleanup_participation": "cleanup" in combined_text,
                "flood_depth_category": "deep" if "deep" in combined_text else "moderate",
            })
        else:
            household.update({
                'pigs_owned': 2 if 'pig' in combined_text else 1,
                'pig_pen_distance_m': 20.0,
                'uses_mosquito_nets': 'no net' in combined_text or 'no mosquito' in combined_text,
                'rice_field_distance_m': 50.0 if 'rice' in combined_text or 'paddy' in combined_text else 100.0,
                'children_under_15': 2,
                'JE_vaccination_children': 'none',
            })
            household['uses_mosquito_nets'] = not ('no net' in combined_text or 'no mosquito' in combined_text)
        new_households.append(household)

    return pd.DataFrame(new_individuals), pd.DataFrame(new_households)


def create_structured_case_records(
    entries: list,
    existing_individuals: pd.DataFrame,
    existing_households: pd.DataFrame,
    scenario_config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create case records from structured case-finding entries."""
    if not entries:
        return pd.DataFrame(), pd.DataFrame()

    existing_person_nums = []
    for pid in existing_individuals["person_id"]:
        try:
            num = int(str(pid).replace("P", "").replace("_CF", ""))
            existing_person_nums.append(num)
        except Exception:
            continue
    max_person_num = max(existing_person_nums) if existing_person_nums else 0

    existing_hh_nums = []
    for hid in existing_households["hh_id"]:
        try:
            num = int(str(hid).replace("HH", "").replace("_CF", ""))
            existing_hh_nums.append(num)
        except Exception:
            continue
    max_hh_num = max(existing_hh_nums) if existing_hh_nums else 0

    symptom_map = scenario_config.get("symptom_field_map", {})
    new_individuals = []
    new_households = []
    for i, entry in enumerate(entries):
        person_id = f"P_CF{max_person_num + 2000 + i:03d}"
        hh_id = f"HH_CF{max_hh_num + 2000 + i:03d}"
        age = int(entry.get("age") or 0)
        sex = str(entry.get("sex") or "U")
        village_id = parse_clinic_record_village(entry.get("village", entry.get("village_id", "")))
        onset_date = entry.get("symptom_onset_date") or entry.get("onset_date")

        individual = {
            "person_id": person_id,
            "hh_id": hh_id,
            "village_id": village_id,
            "age": age,
            "sex": sex,
            "occupation": "other",
            "onset_date": onset_date,
            "outcome": "recovering",
            "name_hint": entry.get("patient_id", ""),
            "found_via_case_finding": True,
        }

        for _, mapping in symptom_map.items():
            indiv_field = mapping.get("individuals")
            clinic_field = mapping.get("clinic")
            if not indiv_field or not clinic_field:
                continue
            value = str(entry.get(clinic_field, "")).strip().lower()
            if value in {"yes", "y", "true"}:
                individual[indiv_field] = True
            elif value in {"no", "n", "false"}:
                individual[indiv_field] = False

        new_individuals.append(individual)
        new_households.append({"hh_id": hh_id, "village_id": village_id})

    return pd.DataFrame(new_individuals), pd.DataFrame(new_households)


def add_found_cases_to_truth(truth: dict, clinic_records: list, selected_record_ids: list,
                             session_state=None) -> int:
    """
    Add correctly identified cases from case finding to the truth data.

    Args:
        truth: The truth dictionary containing individuals and households DataFrames
        clinic_records: List of clinic record dicts
        selected_record_ids: List of record_ids selected by the user
        session_state: Optional session state to store found cases for persistence

    Returns:
        Number of cases added
    """
    new_individuals, new_households = create_found_case_records(
        clinic_records,
        selected_record_ids,
        truth['individuals'],
        truth['households']
    )

    if len(new_individuals) == 0:
        return 0

    # Store found cases separately for persistence (truth is regenerated on load)
    if session_state is not None:
        session_state['found_case_individuals'] = new_individuals
        session_state['found_case_households'] = new_households

    # Concatenate new records to existing DataFrames
    truth['individuals'] = pd.concat([truth['individuals'], new_individuals], ignore_index=True)
    truth['households'] = pd.concat([truth['households'], new_households], ignore_index=True)

    return len(new_individuals)


def restore_found_cases_to_truth(truth: dict, session_state) -> int:
    """
    Restore found cases from session state to truth data.
    Called after truth is regenerated from CSV files on session load.

    Args:
        truth: The truth dictionary containing individuals and households DataFrames
        session_state: Session state containing found_case_individuals and found_case_households

    Returns:
        Number of cases restored
    """
    found_individuals = session_state.get('found_case_individuals')
    found_households = session_state.get('found_case_households')

    if found_individuals is None or len(found_individuals) == 0:
        return 0

    # Check if cases are already in truth (avoid duplicates)
    if 'found_via_case_finding' in truth['individuals'].columns:
        existing_found = truth['individuals'][truth['individuals']['found_via_case_finding'] == True]
        if len(existing_found) > 0:
            # Cases already restored, don't add duplicates
            return 0

    # Concatenate found cases to truth
    truth['individuals'] = pd.concat([truth['individuals'], found_individuals], ignore_index=True)
    if found_households is not None and len(found_households) > 0:
        truth['households'] = pd.concat([truth['households'], found_households], ignore_index=True)

    return len(found_individuals)


def generate_hospital_records():
    """
    Generate detailed hospital medical records for 2 of the hospitalized cases.
    These contain more clinical detail than clinic records - typical for a
    district hospital in a developing country.
    """
    scenario_type = st.session_state.get("current_scenario_type")
    if scenario_type == "lepto":
        scenario_records = load_scenario_json("hospital_records.json")
        if scenario_records:
            return scenario_records

    records = {
        "case_1": {
            "patient_id": "DH-2025-0847",
            "name": "Kwame Asante",
            "age": "7 years",
            "sex": "Male",
            "village": "Nalu Village",
            "admission_date": "3-Jun-2025",
            "admission_time": "14:30",
            "brought_by": "Mother (Ama Asante)",
            "chief_complaint": "High fever (40.2C) and generalized seizures",
            "history_present_illness": """
Child well until 2 days ago. Sudden onset fever (40C), headache, vomiting.
Seizures began this morning. No history of previous seizures. No recent travel.
No sick contacts known.

Child plays regularly in rice fields near home after school. Family keeps 3 pigs
in pen behind house. No mosquito net use - mother says 'it is too hot.'
""",
            "past_medical_history": "No significant PMH. Immunizations up to date per mother (card not available). No known allergies.",
            "physical_exam": """
Temp 40.2C, HR 150. Unconscious. Neck stiffness positive.
No pinpoint pupils (rules out opiates/organophosphates).
No drooling or lacrimation.
""",
            "investigations": """
- WBC: 16,000 (85% Lymphocytes) -> Viral picture
- Hemoglobin: Normal
- Metabolic Panel: Normal anion gap (Rules out many toxins/metabolic causes)
- CSF: Clear, 120 WBC (Lymphocytic), Glucose Normal.
- Malaria RDT: Negative
""",
            "initial_diagnosis": "Acute Viral Encephalitis",
            "differential": "Viral Encephalitis vs Bacterial Meningitis. (Toxin unlikely due to high fever and lymphocytosis)",
            "treatment": """
- IV fluids: D5 0.45% saline at maintenance
- Ceftriaxone 100mg/kg IV (empiric while awaiting cultures)
- Phenobarbital loading dose for seizure prophylaxis
- Paracetamol for fever
- Close neuro obs
""",
            "progress_notes": """
Day 2: Remains febrile. Had 2 more brief seizures overnight. Added acyclovir empirically.
Day 3: Fever persisting. More alert today. No further seizures.
Day 4: Improving. GCS 14. Taking oral fluids. Mother asking about discharge.
Day 7: Stable. Some residual weakness L arm. Discharge planned with f/u in 2 weeks.
""",
            "discharge_diagnosis": "Acute viral encephalitis - etiology undetermined",
            "outcome": "Survived with mild residual weakness"
        },

        "case_2": {
            "patient_id": "DH-2025-0851",
            "name": "Esi Mensah",
            "age": "5 years",
            "sex": "Female",
            "village": "Nalu Village",
            "admission_date": "4-Jun-2025",
            "admission_time": "11:15",
            "brought_by": "Father (Kofi Mensah)",
            "chief_complaint": "Confusion and inability to walk",
            "history_present_illness": """
Previously healthy child. Father reports 2 days of high fever before she
'stopped making sense' and then became unresponsive this morning. Multiple
episodes of shaking/jerking movements witnessed at home. No vomiting or
diarrhea. No rash. No recent illness in household.

Family lives near the pig cooperative - father works there caring for pigs.
Child often accompanies him to work. Family does not use mosquito nets.
House is approximately 50 meters from rice paddies.
""",
            "past_medical_history": "Born at home, no birth complications. Growth normal. Immunization card lost but mother believes she received most vaccines. Had malaria 6 months ago, treated.",
            "physical_exam": """
Temp 39.5C. Ataxic gait. Tremors. No rash.
""",
            "investigations": """
WBC: 14,500 (Lymphocytic). CSF: Pleocytosis. Toxicology Screen: Negative for organophosphates.
""",
            "initial_diagnosis": "Severe acute encephalitis syndrome with raised ICP",
            "differential": "Viral encephalitis, bacterial meningitis, cerebral malaria",
            "treatment": """
- Oxygen via nasal prongs
- IV fluids restricted (2/3 maintenance for raised ICP)
- Mannitol 0.5g/kg for raised ICP
- Ceftriaxone 100mg/kg IV
- Acyclovir 20mg/kg IV q8h
- Phenytoin loading then maintenance
- Head elevation 30 degrees
- ICU admission
""",
            "progress_notes": """
Day 2: Remains critical. GCS 5. Required intubation for airway protection.
       On ventilator. Seizures controlled with phenytoin.
Day 3: No improvement. Developed aspiration pneumonia. Started on gentamicin.
Day 4: Persistent coma. Family counseled about poor prognosis.
Day 5: Declared dead at 06:45. Family declined autopsy.
""",
            "discharge_diagnosis": "Acute viral encephalitis with raised ICP and aspiration pneumonia",
            "outcome": "Died"
        }
    }

    return records


def render_hospital_record(record: dict):
    """Render a detailed hospital medical record."""

    st.markdown(f"""
    <div style="
        background: white;
        border: 1px solid #ccc;
        border-radius: 5px;
        padding: 20px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        margin-bottom: 20px;
    ">
    <div style="text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 15px;">
        <strong style="font-size: 14px;">SIDERO VALLEY DISTRICT HOSPITAL</strong><br>
        <em>Medical Records Department</em>
    </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Patient ID:** {record['patient_id']}")
        st.markdown(f"**Name:** {record['name']}")
        st.markdown(f"**Age/Sex:** {record['age']} / {record['sex']}")
        st.markdown(f"**Village:** {record['village']}")

    with col2:
        st.markdown(f"**Admission Date:** {record['admission_date']}")
        st.markdown(f"**Admission Time:** {record['admission_time']}")
        st.markdown(f"**Brought By:** {record['brought_by']}")

    st.markdown("---")

    st.markdown(f"**Chief Complaint:** {record['chief_complaint']}")

    with st.expander("\U0001f4cb History of Present Illness", expanded=True):
        st.markdown(record['history_present_illness'])

    with st.expander("\U0001f4cb Past Medical History"):
        st.markdown(record['past_medical_history'])

    with st.expander("\U0001fa7a Physical Examination", expanded=True):
        st.markdown(f"```\n{record['physical_exam']}\n```")

    with st.expander("\U0001f9ea Investigations"):
        st.markdown(f"```\n{record['investigations']}\n```")

    st.markdown(f"**Initial Diagnosis:** {record['initial_diagnosis']}")
    st.markdown(f"**Differential:** {record['differential']}")

    with st.expander("\U0001f48a Treatment"):
        st.markdown(record['treatment'])

    with st.expander("\U0001f4dd Progress Notes"):
        st.markdown(record['progress_notes'])

    st.markdown(f"**Discharge Diagnosis:** {record['discharge_diagnosis']}")
    st.markdown(f"**Outcome:** {record['outcome']}")


def render_clinic_record(record: dict, show_checkbox: bool = True) -> bool:
    """
    Render a single clinic record in a handwritten style.
    Returns True if selected as potential case.
    """
    # Simulate messy handwriting with varied formatting
    style = """
    <div style="
        background: #fffef0;
        border: 1px solid #d4c99e;
        border-radius: 2px;
        padding: 12px;
        margin: 8px 0;
        font-family: 'Comic Sans MS', 'Segoe Script', cursive;
        font-size: 14px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        transform: rotate({rotation}deg);
    ">
        <div style="color: #666; font-size: 11px; border-bottom: 1px dashed #ccc; padding-bottom: 4px; margin-bottom: 8px;">
            <strong>{record_id}</strong> &nbsp;|&nbsp; {date}
        </div>
        <div><strong>Pt:</strong> {patient} &nbsp; <strong>Age:</strong> {age}</div>
        <div><strong>Village:</strong> {village}</div>
        <div style="margin-top: 6px;"><strong>Complaint:</strong> {complaint}</div>
        <div style="margin-top: 6px; color: #555; font-style: italic;">Notes: {notes}</div>
    </div>
    """

    import random
    rotation = random.uniform(-0.5, 0.5)

    html = style.format(
        rotation=rotation,
        record_id=record.get("record_id", "???"),
        date=record.get("date", "???"),
        patient=record.get("patient", "???"),
        age=record.get("age", "?"),
        village=record.get("village", "?"),
        complaint=record.get("complaint", ""),
        notes=record.get("notes", "")
    )

    st.markdown(html, unsafe_allow_html=True)

    if show_checkbox:
        return st.checkbox(
            f"Add to line list",
            key=f"select_{record['record_id']}",
            value=record['record_id'] in st.session_state.get('selected_clinic_cases', [])
        )
    return False
