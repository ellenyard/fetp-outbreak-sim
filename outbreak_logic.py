"""
outbreak_logic.py - Multi-Scenario Outbreak Simulation Logic

This module contains the core logic for:
- Loading truth data
- Generating populations from seed data
- Case definition → dataset generation
- Lab test simulation
- Consequence engine

Supported scenarios:
- JE (Japanese Encephalitis) - AES in Sidero Valley
- Lepto (Leptospirosis) - Post-flood outbreak in Rivergate, Aruvia

Separating logic from UI enables:
- Easier testing
- Plug-and-play scenarios
- Cleaner code organization
"""

import pandas as pd
import numpy as np
import json
import copy
from datetime import datetime, timedelta
from pathlib import Path
import uuid

import io
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import streamlit as st
except ImportError:
    # Allow module to be imported in non-Streamlit contexts (e.g., testing)
    st = None


# ============================================================================
# CANONICAL EVENT LOGGING
# ============================================================================

def log_event(event_type, location_id=None, cost_time=0, cost_budget=0, payload=None):
    """
    Canonical event logging function for the Outbreak Simulation.

    Records a decision/action event to both the new _decision_log (for future features)
    and the legacy decisions dict (for backward compatibility with scoring engine).

    Args:
        event_type: Type of event (e.g., 'interview', 'lab_test', 'site_inspection')
        location_id: Optional location identifier (village_id, npc_key, etc.)
        cost_time: Time cost in hours
        cost_budget: Budget cost in dollars
        payload: Optional dictionary with additional event details
    """
    if st is None:
        # Not in a Streamlit context, skip logging
        return

    # Initialize _decision_log if it doesn't exist
    if '_decision_log' not in st.session_state:
        st.session_state['_decision_log'] = []

    # Create event record
    event = {
        'event_id': str(uuid.uuid4()),
        'timestamp': datetime.now().isoformat(),
        'game_day': st.session_state.get('current_day', 1),
        'type': event_type,
        'location_id': location_id,
        'cost_time': cost_time,
        'cost_budget': cost_budget,
        'details': payload or {}
    }

    # Append to new decision log
    st.session_state['_decision_log'].append(event)

    # BACKWARD COMPATIBILITY: Update legacy 'decisions' dict if it exists
    # This ensures the scoring engine continues to work
    if 'decisions' not in st.session_state:
        st.session_state['decisions'] = {}

    # Store the _decision_log reference in decisions for scoring engine access
    st.session_state['decisions']['_decision_log'] = st.session_state['_decision_log']


# ============================================================================
# CANONICAL TRUTH SCHEMA (used for XLSForm mapping/rendering)
# ============================================================================

CANONICAL_SCHEMA: Dict[str, Dict[str, Any]] = {
    # Demographics
    "age": {"source": "individuals", "column": "age", "domain": "demographics", "value_type": "int",
            "description": "Age in years."},
    "sex": {"source": "individuals", "column": "sex", "domain": "demographics", "value_type": "category",
            "categories": ["M", "F"], "description": "Sex (M/F)."},
    "occupation": {"source": "individuals", "column": "occupation", "domain": "demographics", "value_type": "category",
                   "categories": ["child", "farmer", "caretaker", "student", "trader", "teacher", "healthcare", "other"],
                   "description": "Primary occupation / role."},

    # Clinical
    "symptomatic_AES": {"source": "individuals", "column": "symptomatic_AES", "domain": "clinical", "value_type": "bool",
                        "description": "Meets AES clinical syndrome in scenario truth."},
    "severe_neuro": {"source": "individuals", "column": "severe_neuro", "domain": "clinical", "value_type": "bool",
                     "description": "Severe neurologic signs in scenario truth."},
    "onset_date": {"source": "individuals", "column": "onset_date", "domain": "clinical", "value_type": "date",
                   "description": "Date of symptom onset (YYYY-MM-DD)."},
    "outcome": {"source": "individuals", "column": "outcome", "domain": "clinical", "value_type": "category",
                "categories": ["recovered", "hospitalized", "died"], "description": "Clinical outcome."},
    "has_sequelae": {"source": "individuals", "column": "has_sequelae", "domain": "clinical", "value_type": "bool",
                     "description": "Patient has long-term complications (neurological sequelae)."},

    # Vaccination
    "JE_vaccinated": {"source": "individuals", "column": "JE_vaccinated", "domain": "vaccination", "value_type": "bool",
                      "description": "Received JE vaccine (truth)."},
    "JE_vaccination_children": {"source": "households", "column": "JE_vaccination_children", "domain": "vaccination",
                                "value_type": "category", "categories": ["none", "low", "medium", "high"],
                                "description": "Household child JE vaccination coverage level (truth)."},

    # Behavior/exposure
    "evening_outdoor_exposure": {"source": "individuals", "column": "evening_outdoor_exposure", "domain": "behavior",
                                 "value_type": "bool", "description": "Often outdoors at dusk/evening (truth)."},
    "uses_mosquito_nets": {"source": "households", "column": "uses_mosquito_nets", "domain": "vector",
                           "value_type": "bool", "description": "Household reports mosquito net use (truth)."},

    # One Health / animals
    "pigs_owned": {"source": "households", "column": "pigs_owned", "domain": "animals", "value_type": "int",
                   "description": "Number of pigs owned by household (truth)."},
    "pig_pen_distance_m": {"source": "households", "column": "pig_pen_distance_m", "domain": "animals", "value_type": "float",
                           "description": "Distance from home to pig pen in meters (truth)."},
    "pigs_near_home": {"source": "derived", "column": "pigs_near_home", "domain": "animals", "value_type": "bool",
                       "description": "Derived: pigs present and pig pen within 30m."},

    # Environment
    "rice_field_distance_m": {"source": "households", "column": "rice_field_distance_m", "domain": "environment",
                              "value_type": "float", "description": "Distance to nearest rice field in meters (truth)."},
    "rice_field_nearby": {"source": "derived", "column": "rice_field_nearby", "domain": "environment", "value_type": "bool",
                          "description": "Derived: rice field within 100m."},
}

SUPPORTED_XLSFORM_BASE_TYPES = {"text", "integer", "decimal", "date", "select_one", "select_multiple"}

# ============================================================================
# DATA LOADING
# ============================================================================

def load_scenario_config(scenario_id: str) -> Dict[str, Any]:
    """Load scenario configuration metadata."""
    config_path = Path(f"scenarios/{scenario_id}/scenario_config.json")
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_truth_data(data_dir: str = "scenarios/aes_sidero_valley"):
    """
    Load all truth tables from CSV/JSON files.
    Returns a dictionary of DataFrames and the NPC truth dict.

    Args:
        data_dir: Directory containing CSV/JSON files. Default is "scenarios/aes_sidero_valley".
    """
    data_path = Path(data_dir)
    
    required_files = [
        "villages.csv",
        "households_seed.csv",
        "individuals_seed.csv",
        "lab_samples.csv",
        "environment_sites.csv",
        "npc_truth.json"
    ]
    
    # Check all files exist before loading
    missing = [f for f in required_files if not (data_path / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required data files in '{data_path.absolute()}': {missing}\n"
            f"Make sure these files are in your scenario's data folder."
        )

    truth = {}

    # Load CSV files with error handling for each file
    csv_files = {
        'villages': "villages.csv",
        'households_seed': "households_seed.csv",
        'individuals_seed': "individuals_seed.csv",
        'lab_samples': "lab_samples.csv",
        'environment_sites': "environment_sites.csv",
    }

    for key, filename in csv_files.items():
        try:
            truth[key] = pd.read_csv(data_path / filename)
        except pd.errors.EmptyDataError:
            raise ValueError(f"CSV file '{filename}' is empty. Please provide valid data.")
        except pd.errors.ParserError as e:
            raise ValueError(f"Failed to parse CSV file '{filename}': {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error loading CSV file '{filename}': {str(e)}") from e

    # Load JSON file with error handling
    try:
        with open(data_path / "npc_truth.json") as f:
            npc_truth = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON file 'npc_truth.json': {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error loading JSON file 'npc_truth.json': {str(e)}") from e

    if isinstance(npc_truth, list):
        npc_map = {}
        for entry in npc_truth:
            if not isinstance(entry, dict):
                raise ValueError("NPC truth entries must be objects when provided as a list.")
            npc_id = entry.get("npc_id")
            if not npc_id:
                raise ValueError("NPC truth entries must include an 'npc_id' when provided as a list.")
            if npc_id in npc_map:
                raise ValueError(f"Duplicate npc_id '{npc_id}' in NPC truth list.")
            entry_copy = dict(entry)
            entry_copy.pop("npc_id", None)
            npc_map[npc_id] = entry_copy
        npc_truth = npc_map

    truth['npc_truth'] = npc_truth

    return truth


def get_hospital_triage_list(scenario_id: str = None):
    """
    Returns the Day 1 Hospital Ward Triage List.
    Scenario-aware: returns appropriate patient data based on current scenario.
    """
    # Get scenario from session state if not provided
    if scenario_id is None and st is not None:
        scenario_id = st.session_state.get("current_scenario", "aes_sidero")

    if scenario_id == "lepto_rivergate":
        # Lepto scenario: Adult males with leptospirosis from flood cleanup
        # Village mapping: V1=Ward Northbend, V2=Ward East Terrace, V3=Ward Southshore, V4=Ward Highridge
        return [
            # --- Confirmed Leptospirosis Cases ---
            {"id": "P0001", "name": "Adrian Vale", "age": "42y", "sex": "M", "village": "Ward Northbend", "symptom": "High Fever 39.5°C, Severe Myalgia, Jaundice, Conjunctival Suffusion", "notes": "Critical. Renal failure. Farmer, flood cleanup.", "is_case": True, "status": "Deceased", "onset": "2024-10-13"},
            {"id": "P0003", "name": "Tomas Fernandez", "age": "38y", "sex": "M", "village": "Ward Northbend", "symptom": "Fever 39°C, Myalgia, Jaundice, Conjunctival Suffusion", "notes": "Severe. Farmer, flood cleanup exposure.", "is_case": True, "status": "Admitted", "onset": "2024-10-14"},
            {"id": "P0006", "name": "Elder Merrin", "age": "51y", "sex": "M", "village": "Ward Northbend", "symptom": "Fever 38.8°C, Severe Myalgia, Jaundice", "notes": "Severe. Farmer with flood exposure.", "is_case": True, "status": "Recovering", "onset": "2024-10-12"},
            {"id": "P0007", "name": "Grant Orr", "age": "45y", "sex": "M", "village": "Ward Northbend", "symptom": "Fever 38.5°C, Myalgia, Conjunctival Suffusion", "notes": "Moderate. Day laborer.", "is_case": True, "status": "Admitted", "onset": "2024-10-15"},
            {"id": "P0015", "name": "Gregorio Mercado", "age": "48y", "sex": "M", "village": "Ward Northbend", "symptom": "High Fever 40°C, Severe Myalgia, Conjunctival Suffusion", "notes": "Critical. Farmer, deceased.", "is_case": True, "status": "Deceased", "onset": "2024-10-13"},
            {"id": "P0002", "name": "Luz Fernandez", "age": "34y", "sex": "F", "village": "Ward Northbend", "symptom": "Fever 38.2°C, Myalgia, Headache", "notes": "Moderate. Vendor, flood cleanup.", "is_case": True, "status": "Recovered", "onset": "2024-10-14"},

            # --- Non-Leptospirosis Cases (differential diagnosis practice) ---
            {"id": "HOSP-L01", "name": "Rosa Santos", "age": "28y", "sex": "F", "village": "Ward Northbend", "symptom": "Fever, Cough, Runny Nose", "notes": "Upper respiratory infection. No flood exposure.", "is_case": False, "status": "Discharged", "onset": "2024-10-15"},
            {"id": "HOSP-L02", "name": "Miguel Torres", "age": "55y", "sex": "M", "village": "Ward East Terrace", "symptom": "Chest Pain, Shortness of Breath", "notes": "Cardiac workup. No myalgia.", "is_case": False, "status": "Admitted", "onset": "2024-10-14"},
            {"id": "HOSP-L03", "name": "Ana Reyes", "age": "19y", "sex": "F", "village": "Ward Southshore", "symptom": "Fever, Rash, Joint Pain", "notes": "Dengue suspected. No conjunctival suffusion.", "is_case": False, "status": "Admitted", "onset": "2024-10-16"},
        ]
    else:
        # AES/JE scenario (default): Children with encephalitis
        return [
            # --- The 4 JES Cases (2 known, 2 new) ---
            {"id": "HOSP-01", "age": "6y", "sex": "F", "village": "Nalu", "symptom": "High Fever, Seizures", "notes": "Admitted.", "is_case": True, "parent_type": "parent_ward", "status": "Admitted"},
            {"id": "HOSP-02", "age": "8y", "sex": "M", "village": "Nalu", "symptom": "Fever, Coma", "notes": "Critical.", "is_case": True, "parent_type": "parent_general", "status": "Admitted"},
            {"id": "HOSP-07", "age": "5y", "sex": "M", "village": "Kabwe", "symptom": "Seizures, Confusion", "notes": "New admission.", "is_case": True, "parent_type": "parent_general", "status": "Admitted"},
            {"id": "HOSP-04", "age": "7y", "sex": "F", "village": "Tamu", "symptom": "Fever, Lethargy", "notes": "The outlier case.", "is_case": True, "parent_type": "parent_tamu", "status": "Discharged"},

            # --- The 5 Non-JES Cases ---
            {"id": "HOSP-03", "age": "34y", "sex": "M", "village": "Nalu", "symptom": "Broken Leg", "notes": "Trauma.", "is_case": False, "parent_type": "none", "status": "Admitted"},
            {"id": "HOSP-05", "age": "4y", "sex": "M", "village": "Kabwe", "symptom": "Severe Dehydration", "notes": "No fever. Diarrhea.", "is_case": False, "parent_type": "none", "status": "Discharged"},
            {"id": "HOSP-06", "age": "2m", "sex": "F", "village": "Kabwe", "symptom": "Cough", "notes": "Bronchiolitis.", "is_case": False, "parent_type": "none", "status": "Discharged"},
            {"id": "HOSP-08", "age": "10y", "sex": "F", "village": "Nalu", "symptom": "Rash, Joint Pain", "notes": "Dengue suspected.", "is_case": False, "parent_type": "none", "status": "Discharged"},
            {"id": "HOSP-09", "age": "60y", "sex": "M", "village": "Tamu", "symptom": "Chest Pain", "notes": "Cardiac.", "is_case": False, "parent_type": "none", "status": "Admitted"},
        ]


def get_medical_chart(patient_id):
    """
    Returns a patient's medical chart containing ONLY clinical and demographic data.
    NO exposure data (pigs, water, mosquitoes, etc.) is included.

    Args:
        patient_id: Patient ID (e.g., "HOSP-01", "P0001")

    Returns:
        Dictionary containing: Name, Age, Sex, Village, Date of Onset,
        Temperature, Neuro Signs, WBC Count, and Outcome.
        Returns None if patient not found.
    """
    # Log the event
    log_event(
        event_type='view_medical_chart',
        location_id=patient_id,
        cost_time=5,
        cost_budget=0,
        payload={'patient_id': patient_id}
    )

    # Get hospital triage list
    triage_patients = get_hospital_triage_list()

    # Find patient in triage list
    patient = None
    for p in triage_patients:
        if p['id'] == patient_id:
            patient = p
            break

    if not patient:
        return None

    # Extract clinical data only (NO exposure data)
    # Parse symptoms to extract temperature and neuro signs
    symptom_text = patient.get('symptom', '')
    notes_text = patient.get('notes', '')

    # Extract temperature
    temp_match = re.search(r'(\d+\.?\d*)[°CcF]', symptom_text + ' ' + notes_text)
    temperature = f"{temp_match.group(1)}°C" if temp_match else "Unknown"

    # Extract neuro signs
    neuro_signs = []
    symptom_lower = symptom_text.lower()
    if 'seizure' in symptom_lower or 'convulsion' in symptom_lower:
        neuro_signs.append('Seizure')
    if 'coma' in symptom_lower or "won't wake" in symptom_lower:
        neuro_signs.append('Coma')
    if 'confusion' in symptom_lower or 'lethargy' in symptom_lower:
        neuro_signs.append('Altered mental status')
    if 'tremor' in symptom_lower:
        neuro_signs.append('Tremors')

    neuro_text = ', '.join(neuro_signs) if neuro_signs else 'None documented'

    # Extract WBC count
    wbc_match = re.search(r'WBC\s+(\d+k?)', notes_text, re.IGNORECASE)
    wbc_count = wbc_match.group(1) if wbc_match else 'Not tested'

    # Determine outcome
    outcome_map = {
        'Admitted': 'Admitted',
        'Currently Admitted': 'Admitted',
        'Discharged': 'Recovered',
        'Deceased': 'Died'
    }
    outcome = outcome_map.get(patient.get('status'), 'Unknown')

    # Parse age to extract just the number and unit
    age_str = patient.get('age', 'Unknown')

    # Get patient name if available
    name = patient.get('name', f"Patient {patient_id}")

    # Get onset date from patient data if available, otherwise use mapping
    onset_date = patient.get('onset', None)
    if not onset_date:
        # Fallback onset dates for AES scenario
        onset_dates = {
            'HOSP-01': 'June 3, 2025',
            'HOSP-02': 'June 4, 2025',
            'HOSP-04': 'June 9, 2025',
            'HOSP-05': 'June 7, 2025',
        }
        onset_date = onset_dates.get(patient_id, 'Unknown')

    # Construct medical chart (CLINICAL DATA ONLY)
    chart = {
        'Patient ID': patient_id,
        'Name': name,
        'Age': age_str,
        'Sex': patient.get('sex', 'Unknown'),
        'Village': patient.get('village', 'Unknown'),
        'Date of Onset': onset_date,
        'Temperature': temperature,
        'Neuro Signs': neuro_text,
        'WBC Count': wbc_count,
        'Outcome': outcome
    }

    return chart


def get_clinic_log(village_id, scenario_id: str = None):
    """
    Returns a realistic clinic logbook with raw, natural language entries.
    Simulates handwritten notes with natural complaint descriptions.
    Scenario-aware: returns appropriate data based on current scenario.

    Args:
        village_id: Village ID (e.g., "V1", "V2", "V3") or village name
        scenario_id: Optional scenario identifier

    Returns:
        List of 10-15 clinic log entries with natural language complaints.
    """
    # Log the event
    log_event(
        event_type='view_clinic_log',
        location_id=village_id,
        cost_time=15,
        cost_budget=0,
        payload={'village_id': village_id}
    )

    # Get scenario from session state if not provided
    if scenario_id is None and st is not None:
        scenario_id = st.session_state.get("current_scenario", "aes_sidero")

    if scenario_id == "lepto_rivergate":
        # Lepto scenario village name mapping
        village_name_map = {
            'ward northbend': 'V1',
            'northbend': 'V1',
            'v1': 'V1',
            'ward east terrace': 'V2',
            'east terrace': 'V2',
            'v2': 'V2',
            'ward southshore': 'V3',
            'southshore': 'V3',
            'v3': 'V3',
            'ward highridge': 'V4',
            'highridge': 'V4',
            'v4': 'V4'
        }

        # Normalize village_id
        if isinstance(village_id, str):
            village_id = village_name_map.get(village_id.lower(), village_id.upper())

        # Lepto-specific clinic logs - adult males with flood exposure
        clinic_logs = {
            'V1': [  # Ward Northbend - HIGHEST CASE LOAD (epicenter)
                {'name': 'Adrian Vale', 'age': 42, 'complaint': 'Very high fever, severe leg pain, red eyes. Did flood cleanup.', 'date': 'Oct 13'},
                {'name': 'Tomas Fernandez', 'age': 38, 'complaint': 'Fever, muscle aches especially calves, yellowish eyes', 'date': 'Oct 14'},
                {'name': 'Luz Fernandez', 'age': 34, 'complaint': 'Fever 38C, body aches, headache. Helped with cleanup.', 'date': 'Oct 14'},
                {'name': 'Derek Carver', 'age': 29, 'complaint': 'High fever, severe muscle pain in legs', 'date': 'Oct 13'},
                {'name': 'Elder Merrin', 'age': 51, 'complaint': 'Fever, jaundice noticed, very weak', 'date': 'Oct 12'},
                {'name': 'Mrs. Santos', 'age': 45, 'complaint': 'Cough, no fever, chest congestion', 'date': 'Oct 14'},
                {'name': 'Grant Orr', 'age': 45, 'complaint': 'Fever, red eyes, muscle pain after wading in flood', 'date': 'Oct 15'},
                {'name': 'Joel Halden', 'age': 28, 'complaint': 'Mild fever, leg cramps, worked barefoot in mud', 'date': 'Oct 16'},
                {'name': 'Baby Cruz', 'age': 2, 'complaint': 'Diarrhea, no fever', 'date': 'Oct 15'},
                {'name': 'Pedro Holt', 'age': 37, 'complaint': 'Fever, severe myalgia, flood cleanup work', 'date': 'Oct 15'},
                {'name': 'Mrs. Reyes', 'age': 60, 'complaint': 'Joint pain, old arthritis acting up', 'date': 'Oct 16'},
                {'name': 'Gregorio Mercado', 'age': 48, 'complaint': 'Very high fever, vomiting, cant urinate properly', 'date': 'Oct 13'}
            ],
            'V2': [  # Ward East Terrace - MODERATE CASE LOAD
                {'name': 'Roberto Tan', 'age': 31, 'complaint': 'Fever, muscle pain, helped clear debris', 'date': 'Oct 16'},
                {'name': 'Mr. Lim', 'age': 55, 'complaint': 'Back pain from lifting flood debris', 'date': 'Oct 14'},
                {'name': 'Maria Torres', 'age': 28, 'complaint': 'Cough and cold symptoms', 'date': 'Oct 15'},
                {'name': 'Diego Sanchez', 'age': 26, 'complaint': 'Fever, red eyes, worked in floodwater', 'date': 'Oct 19'},
                {'name': 'Mrs. Garcia', 'age': 42, 'complaint': 'Headache, stress from flood damage', 'date': 'Oct 16'},
                {'name': 'Boy Santos', 'age': 8, 'complaint': 'Scraped knee from playing', 'date': 'Oct 17'},
                {'name': 'Mr. Cruz', 'age': 48, 'complaint': 'Chest tightness, worried about heart', 'date': 'Oct 18'},
                {'name': 'Ana Reyes', 'age': 19, 'complaint': 'Fever, rash, joint pain', 'date': 'Oct 16'}
            ],
            'V3': [  # Ward Southshore - LOWER CASE LOAD
                {'name': 'Emmanuel Ramos', 'age': 35, 'complaint': 'High fever, severe leg pain, jaundice. Fisher.', 'date': 'Oct 15'},
                {'name': 'Mrs. Luna', 'age': 50, 'complaint': 'Cough for one week', 'date': 'Oct 14'},
                {'name': 'Boy Perez', 'age': 10, 'complaint': 'Stomach ache', 'date': 'Oct 16'},
                {'name': 'Mr. Valdez', 'age': 62, 'complaint': 'Knee pain, old injury', 'date': 'Oct 17'},
                {'name': 'Rosa Santos', 'age': 28, 'complaint': 'Fever, runny nose, cough', 'date': 'Oct 15'},
                {'name': 'Baby Torres', 'age': 1, 'complaint': 'Mild fever, teething', 'date': 'Oct 18'}
            ],
            'V4': [  # Ward Highridge - CONTROL AREA (minimal flooding)
                {'name': 'Mr. Aquino', 'age': 55, 'complaint': 'Back pain from farm work', 'date': 'Oct 14'},
                {'name': 'Mrs. Bautista', 'age': 38, 'complaint': 'Headache, fatigue', 'date': 'Oct 15'},
                {'name': 'Girl Mendoza', 'age': 7, 'complaint': 'Ear infection', 'date': 'Oct 16'},
                {'name': 'Mr. Reyes', 'age': 45, 'complaint': 'Cut hand while farming', 'date': 'Oct 17'},
                {'name': 'Baby Lopez', 'age': 3, 'complaint': 'Common cold', 'date': 'Oct 18'}
            ]
        }
    else:
        # AES/JE scenario (default)
        village_name_map = {
            'nalu': 'V1',
            'nalu village': 'V1',
            'kabwe': 'V2',
            'kabwe village': 'V2',
            'tamu': 'V3',
            'tamu village': 'V3'
        }

        # Normalize village_id
        if isinstance(village_id, str) and village_id.lower() in village_name_map:
            village_id = village_name_map[village_id.lower()]

        # AES-specific clinic logs with natural language complaints
        clinic_logs = {
            'V1': [  # Nalu Village - HIGH CASE LOAD
                {'name': 'Lan', 'age': 6, 'complaint': 'Hot to touch, shaking badly', 'date': 'June 3'},
                {'name': 'Minh', 'age': 9, 'complaint': 'Head hurts, body burning hot', 'date': 'June 4'},
                {'name': 'Mrs. Pham', 'age': 30, 'complaint': 'Cut finger while cooking', 'date': 'June 4'},
                {'name': 'Baby Tuan', 'age': 4, 'complaint': 'Fever and shaking, very sleepy', 'date': 'June 6'},
                {'name': 'Kiet', 'age': 8, 'complaint': 'Coughing and runny nose', 'date': 'June 5'},
                {'name': 'Thanh', 'age': 12, 'complaint': 'Stomach ache, ate too many mangoes', 'date': 'June 6'},
                {'name': 'Mr. Hoang', 'age': 45, 'complaint': 'Back pain from lifting', 'date': 'June 7'},
                {'name': 'Little Duc', 'age': 5, 'complaint': 'Broken arm from tree fall', 'date': 'June 8'},
                {'name': 'Anh', 'age': 7, 'complaint': 'Hot fever, then sleeping and won\'t wake up', 'date': 'June 7'},
                {'name': 'Mai', 'age': 11, 'complaint': 'Toothache', 'date': 'June 9'},
                {'name': 'Baby Linh', 'age': 2, 'complaint': 'Rash on legs, itchy', 'date': 'June 9'},
                {'name': 'Quan', 'age': 14, 'complaint': 'Twisted ankle playing football', 'date': 'June 10'}
            ],
            'V2': [  # Kabwe Village - MODERATE CASE LOAD
                {'name': 'Hoa', 'age': 7, 'complaint': 'Very hot, body shaking, confused', 'date': 'June 7'},
                {'name': 'Mr. Tran', 'age': 35, 'complaint': 'Sore throat, cough', 'date': 'June 5'},
                {'name': 'Little Mai', 'age': 2, 'complaint': 'Fever, but playing normally', 'date': 'June 9'},
                {'name': 'Binh', 'age': 9, 'complaint': 'Diarrhea for 2 days', 'date': 'June 6'},
                {'name': 'Mrs. Nguyen', 'age': 40, 'complaint': 'Headache and tired', 'date': 'June 7'},
                {'name': 'Tien', 'age': 6, 'complaint': 'Earache', 'date': 'June 8'},
                {'name': 'Khoa', 'age': 11, 'complaint': 'Cut on foot from glass', 'date': 'June 9'},
                {'name': 'Baby Tam', 'age': 1, 'complaint': 'Coughing, wheezing', 'date': 'June 10'},
                {'name': 'Phuong', 'age': 8, 'complaint': 'Hot skin, won\'t eat, stiff neck', 'date': 'June 8'},
                {'name': 'Mr. Minh', 'age': 50, 'complaint': 'Chest pain, worried', 'date': 'June 9'}
            ],
            'V3': [  # Tamu Village - MINIMAL CASES (Outlier case)
                {'name': 'Panya', 'age': 7, 'complaint': 'Burning hot, shaking, then very sleepy', 'date': 'June 9'},
                {'name': 'Ratana', 'age': 12, 'complaint': 'Common cold, sneezing', 'date': 'June 5'},
                {'name': 'Mr. Somchai', 'age': 38, 'complaint': 'Scraped knee from fall', 'date': 'June 6'},
                {'name': 'Baby Niran', 'age': 3, 'complaint': 'Teething pain', 'date': 'June 7'},
                {'name': 'Mrs. Kulap', 'age': 42, 'complaint': 'Joint pain, rainy season', 'date': 'June 8'},
                {'name': 'Sakda', 'age': 10, 'complaint': 'Insect bite, swollen', 'date': 'June 9'},
                {'name': 'Lawan', 'age': 6, 'complaint': 'Stomach upset', 'date': 'June 10'},
                {'name': 'Mr. Boon', 'age': 55, 'complaint': 'Cough for 1 week', 'date': 'June 8'},
                {'name': 'Mali', 'age': 9, 'complaint': 'Eye irritation from dust', 'date': 'June 9'},
                {'name': 'Suda', 'age': 4, 'complaint': 'Mild fever, runny nose', 'date': 'June 10'}
            ]
        }

    # Return appropriate log or empty list if village not found
    return clinic_logs.get(village_id, [])


def get_nalu_child_register():
    """
    Returns the Nalu Health Center Child Register with 38 entries.
    Includes 3 hospital referrals, 1 new death, 2 moderate cases, and 32 noise cases.

    Returns:
        List of 38 child register entries with ID, name, age, visit_date, complaint, and status.
    """
    # Log the event
    log_event(
        event_type='view_nalu_child_register',
        location_id='nalu_health_center',
        cost_time=30,
        cost_budget=0,
        payload={'register': 'child_register'}
    )

    register = [
        # === THE 3 REFERRALS (Known Hospital Patients) ===
        {'id': 'NALU-CH-001', 'name': 'Lan', 'age': 6, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 3', 'complaint': 'High fever, shaking, very sleepy',
         'status': 'Referred to Hospital'},
        {'id': 'NALU-CH-002', 'name': 'Minh', 'age': 9, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 4', 'complaint': 'Burning hot, head hurts badly, confused',
         'status': 'Referred to Hospital'},
        {'id': 'NALU-CH-017', 'name': 'Baby Tuan', 'age': 4, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 6', 'complaint': 'Fever, shaking, won\'t wake up',
         'status': 'Referred to Hospital'},

        # === THE NEW DEATH (New Discovery) ===
        {'id': 'NALU-CH-023', 'name': 'Anh', 'age': 7, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 7', 'complaint': 'Hot fever, then seizures at home',
         'status': 'Died at home June 8'},

        # === THE 2 MODERATE CASES (New Cases) ===
        {'id': 'NALU-CH-015', 'name': 'Hien', 'age': 8, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 5', 'complaint': 'Fever, headache, neck feels stiff',
         'status': 'Sent home with medicine'},
        {'id': 'NALU-CH-022', 'name': 'Linh', 'age': 6, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 7', 'complaint': 'Fever, headache, stiff neck, tired',
         'status': 'Sent home with medicine'},

        # === NOISE CASES (32 entries: well-baby, vaccinations, malaria, minor illnesses) ===
        {'id': 'NALU-CH-003', 'name': 'Baby Nga', 'age': 2, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 1', 'complaint': 'Well-baby checkup', 'status': 'Healthy'},
        {'id': 'NALU-CH-004', 'name': 'Phuc', 'age': 5, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 1', 'complaint': 'Vaccination (DPT booster)', 'status': 'Vaccinated'},
        {'id': 'NALU-CH-005', 'name': 'Thu', 'age': 3, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 2', 'complaint': 'Cough, runny nose', 'status': 'Treated'},
        {'id': 'NALU-CH-006', 'name': 'Khai', 'age': 7, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 2', 'complaint': 'Diarrhea for 1 day', 'status': 'ORS given'},
        {'id': 'NALU-CH-007', 'name': 'Baby Vy', 'age': 1, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 3', 'complaint': 'Well-baby checkup', 'status': 'Healthy'},
        {'id': 'NALU-CH-008', 'name': 'Tung', 'age': 9, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 3', 'complaint': 'Malaria-like fever, tested negative', 'status': 'Treated'},
        {'id': 'NALU-CH-009', 'name': 'Chi', 'age': 4, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 4', 'complaint': 'Skin rash, itchy', 'status': 'Cream applied'},
        {'id': 'NALU-CH-010', 'name': 'Bao', 'age': 6, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 4', 'complaint': 'Vaccination (MMR)', 'status': 'Vaccinated'},
        {'id': 'NALU-CH-011', 'name': 'My', 'age': 8, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 5', 'complaint': 'Scraped knee from fall', 'status': 'Cleaned and bandaged'},
        {'id': 'NALU-CH-012', 'name': 'Dat', 'age': 5, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 5', 'complaint': 'Stomach ache, ate too much fruit', 'status': 'Observation'},
        {'id': 'NALU-CH-013', 'name': 'Baby Hong', 'age': 2, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 6', 'complaint': 'Well-baby checkup', 'status': 'Healthy'},
        {'id': 'NALU-CH-014', 'name': 'Tai', 'age': 10, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 6', 'complaint': 'Toothache', 'status': 'Referred to dentist'},
        {'id': 'NALU-CH-016', 'name': 'Huong', 'age': 3, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 6', 'complaint': 'Vaccination (Polio)', 'status': 'Vaccinated'},
        {'id': 'NALU-CH-018', 'name': 'Nam', 'age': 7, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 7', 'complaint': 'Malaria test (positive)', 'status': 'Antimalarial given'},
        {'id': 'NALU-CH-019', 'name': 'Tuyet', 'age': 5, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 7', 'complaint': 'Cough for 3 days', 'status': 'Treated'},
        {'id': 'NALU-CH-020', 'name': 'Baby Son', 'age': 1, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 8', 'complaint': 'Well-baby checkup', 'status': 'Healthy'},
        {'id': 'NALU-CH-021', 'name': 'Phuong', 'age': 9, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 8', 'complaint': 'Eye irritation from dust', 'status': 'Eye drops given'},
        {'id': 'NALU-CH-024', 'name': 'Dung', 'age': 4, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 8', 'complaint': 'Vaccination (Hepatitis B)', 'status': 'Vaccinated'},
        {'id': 'NALU-CH-025', 'name': 'Hanh', 'age': 6, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 9', 'complaint': 'Fever, tested for malaria (negative)', 'status': 'Paracetamol given'},
        {'id': 'NALU-CH-026', 'name': 'Vinh', 'age': 8, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 9', 'complaint': 'Minor cut on hand', 'status': 'Cleaned and bandaged'},
        {'id': 'NALU-CH-027', 'name': 'Baby Quynh', 'age': 2, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 9', 'complaint': 'Well-baby checkup', 'status': 'Healthy'},
        {'id': 'NALU-CH-028', 'name': 'Thao', 'age': 7, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 10', 'complaint': 'Earache', 'status': 'Antibiotics given'},
        {'id': 'NALU-CH-029', 'name': 'Loc', 'age': 5, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 10', 'complaint': 'Vaccination (Measles)', 'status': 'Vaccinated'},
        {'id': 'NALU-CH-030', 'name': 'Nhi', 'age': 9, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 10', 'complaint': 'Stomach ache, vomiting once', 'status': 'ORS given'},
        {'id': 'NALU-CH-031', 'name': 'Baby Khang', 'age': 1, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 11', 'complaint': 'Well-baby checkup', 'status': 'Healthy'},
        {'id': 'NALU-CH-032', 'name': 'Yen', 'age': 6, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 11', 'complaint': 'Insect bite, swollen', 'status': 'Antihistamine given'},
        {'id': 'NALU-CH-033', 'name': 'Hung', 'age': 10, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 11', 'complaint': 'Sprained ankle from sports', 'status': 'Rest advised'},
        {'id': 'NALU-CH-034', 'name': 'Giang', 'age': 4, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 12', 'complaint': 'Mild fever, playing normally', 'status': 'Observation'},
        {'id': 'NALU-CH-035', 'name': 'Tri', 'age': 7, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 12', 'complaint': 'Vaccination (Typhoid)', 'status': 'Vaccinated'},
        {'id': 'NALU-CH-036', 'name': 'Baby Ly', 'age': 2, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 12', 'complaint': 'Well-baby checkup', 'status': 'Healthy'},
        {'id': 'NALU-CH-037', 'name': 'Quang', 'age': 8, 'sex': 'M', 'village': 'Nalu',
         'visit_date': 'June 13', 'complaint': 'Runny nose, sneezing', 'status': 'Treated'},
        {'id': 'NALU-CH-038', 'name': 'Hoa', 'age': 5, 'sex': 'F', 'village': 'Nalu',
         'visit_date': 'June 13', 'complaint': 'Skin rash on arms', 'status': 'Cream applied'},
    ]

    return register


def get_nalu_medical_record(patient_id):
    """
    Returns a "messier" medical record from Nalu Health Center.
    Records have missing vitals, brief notes, and incomplete data compared to hospital charts.

    Args:
        patient_id: Patient ID from the child register (e.g., "NALU-CH-023")

    Returns:
        Dictionary with medical record data, or None if not found.
    """
    # Log the event
    log_event(
        event_type='view_nalu_medical_record',
        location_id=patient_id,
        cost_time=5,
        cost_budget=0,
        payload={'patient_id': patient_id}
    )

    # Messier medical records for key patients
    records = {
        # The 3 Hospital Referrals
        'NALU-CH-001': {
            'Patient ID': 'NALU-CH-001',
            'Name': 'Lan',
            'Age': '6 years',
            'Sex': 'F',
            'Village': 'Nalu',
            'Visit Date': 'June 3',
            'Complaint': 'Mother says "hot to touch, shaking badly"',
            'Vitals': 'Hot skin (no thermometer available)',
            'Exam': 'Shaking. Very sleepy. Not responding well.',
            'Notes': 'REFERRED TO HOSPITAL - too sick for clinic',
            'Outcome': 'Sent to District Hospital'
        },
        'NALU-CH-002': {
            'Patient ID': 'NALU-CH-002',
            'Name': 'Minh',
            'Age': '9 years',
            'Sex': 'M',
            'Village': 'Nalu',
            'Visit Date': 'June 4',
            'Complaint': 'Head hurts, burning hot, confused',
            'Vitals': 'Temp: high (thermometer broken)',
            'Exam': 'Confused. Doesn\'t know where he is.',
            'Notes': 'REFERRED TO HOSPITAL - needs doctor',
            'Outcome': 'Sent to District Hospital'
        },
        'NALU-CH-017': {
            'Patient ID': 'NALU-CH-017',
            'Name': 'Baby Tuan',
            'Age': '4 years',
            'Sex': 'M',
            'Village': 'Nalu',
            'Visit Date': 'June 6',
            'Complaint': 'Fever, shaking, won\'t wake up',
            'Vitals': 'Very hot',
            'Exam': 'Won\'t wake up. Shaking.',
            'Notes': 'REFERRED TO HOSPITAL URGENTLY',
            'Outcome': 'Sent to District Hospital'
        },

        # The New Death
        'NALU-CH-023': {
            'Patient ID': 'NALU-CH-023',
            'Name': 'Anh',
            'Age': '7 years',
            'Sex': 'F',
            'Village': 'Nalu',
            'Visit Date': 'June 7',
            'Complaint': 'Hot fever, then seizures at home',
            'Vitals': 'Not recorded (came after hours)',
            'Exam': 'Mother says "shaking, then stopped breathing at home"',
            'Notes': 'Family brought body to clinic morning of June 8. Said child had fever June 7, then seizures at night. Died at home.',
            'Outcome': 'DIED AT HOME - June 8'
        },

        # The 2 Moderate Cases
        'NALU-CH-015': {
            'Patient ID': 'NALU-CH-015',
            'Name': 'Hien',
            'Age': '8 years',
            'Sex': 'M',
            'Village': 'Nalu',
            'Visit Date': 'June 5',
            'Complaint': 'Fever, headache, neck feels stiff',
            'Vitals': 'Temp: high (no exact reading)',
            'Exam': 'Neck stiff. Says head hurts. Hot skin.',
            'Notes': 'Gave paracetamol. Told mother to watch for worsening.',
            'Outcome': 'Sent home with medicine'
        },
        'NALU-CH-022': {
            'Patient ID': 'NALU-CH-022',
            'Name': 'Linh',
            'Age': '6 years',
            'Sex': 'F',
            'Village': 'Nalu',
            'Visit Date': 'June 7',
            'Complaint': 'Fever, headache, stiff neck, tired',
            'Vitals': 'Temp: feels very hot',
            'Exam': 'Stiff neck. Very tired. Headache.',
            'Notes': 'Gave paracetamol. Advised rest and fluids.',
            'Outcome': 'Sent home with medicine'
        },
    }

    return records.get(patient_id, None)


def update_nurse_rapport(choice, session_state=None):
    """
    Updates nurse rapport based on dialogue choice.

    Args:
        choice: 'demand' (rapport -10) or 'empathize' (rapport +10) or 'animals' (track count)
        session_state: Streamlit session state object (optional)

    Returns:
        Dictionary with 'rapport', 'message', and 'unlocks' keys.
    """
    if session_state is None and st:
        session_state = st.session_state

    # Initialize rapport if not exists
    if 'nurse_rapport' not in session_state:
        session_state['nurse_rapport'] = 0

    # Initialize animal question count
    if 'nurse_animal_questions' not in session_state:
        session_state['nurse_animal_questions'] = 0

    # Update based on choice
    if choice == 'demand':
        session_state['nurse_rapport'] -= 10
        message = "The nurse crosses her arms. 'I don't have time for this right now. Come back later.'"
        unlocks = {}
    elif choice == 'empathize':
        session_state['nurse_rapport'] += 10
        message = "The nurse's expression softens slightly. 'Thank you... it has been hard.'"
        unlocks = {}
    elif choice == 'animals':
        session_state['nurse_animal_questions'] += 1
        message = None  # Will be handled by NPC chat
        unlocks = {}
    else:
        message = "Invalid choice."
        unlocks = {}

    # Check unlocks
    rapport = session_state['nurse_rapport']
    animal_q = session_state.get('nurse_animal_questions', 0)

    if rapport > 10:
        unlocks['records_access'] = True
    else:
        unlocks['records_access'] = False

    if rapport > 20 or animal_q >= 3:
        unlocks['pig_clue'] = True
    else:
        unlocks['pig_clue'] = False

    return {
        'rapport': rapport,
        'message': message,
        'unlocks': unlocks
    }


def check_nurse_rapport(session_state=None):
    """
    Checks if nurse permits records access based on rapport.

    Args:
        session_state: Streamlit session state object (optional)

    Returns:
        Boolean indicating if records access is permitted.
    """
    if session_state is None and st:
        session_state = st.session_state

    rapport = session_state.get('nurse_rapport', 0)
    return rapport > 10


def check_case_definition(criteria, patient=None):
    """
    Validates case definition criteria to ensure they include Clinical + Time/Place
    elements, with optional epi link and lab criteria.

    Args:
        criteria: Dictionary or list of criteria fields/terms
        patient: Optional patient dictionary to validate against criteria

    Returns:
        Dictionary with 'valid' (bool) and 'message' (str) keys.
        If invalid, includes error message about missing elements.
    """
    # Log the event
    log_event(
        event_type='check_case_definition',
        location_id=None,
        cost_time=0,
        cost_budget=0,
        payload={'criteria': criteria}
    )

    # Convert criteria to searchable format
    if isinstance(criteria, dict):
        criteria_text = ' '.join(list(str(k).lower() for k in criteria.keys()) + [str(v).lower() for v in criteria.values()])
    elif isinstance(criteria, list):
        criteria_text = ' '.join(str(c).lower() for c in criteria)
    else:
        criteria_text = str(criteria).lower()

    clinical_terms = [
        "fever", "seizure", "confusion", "jaundice", "myalgia",
        "vomiting", "rash", "stiff neck", "altered", "renal"
    ]
    time_place_terms = ["date", "onset", "village", "district", "ward", "area", "between"]
    has_clinical = any(term in criteria_text for term in clinical_terms)
    has_time_place = any(term in criteria_text for term in time_place_terms)

    if not has_clinical or not has_time_place:
        missing = []
        if not has_clinical:
            missing.append("clinical criteria")
        if not has_time_place:
            missing.append("time/place boundaries")
        return {
            'valid': False,
            'message': f"Case Definitions should include {' and '.join(missing)}."
        }

    # If patient is provided, validate patient matches criteria
    if patient:
        # This is where you would implement actual case matching logic
        # For now, we'll just return valid
        pass

    return {
        'valid': True,
        'message': 'Case definition criteria are valid.'
    }


def _weighted_choice(options: List[str], weights: List[float]) -> str:
    """Helper to select a single item from options using weights."""
    return np.random.choice(options, p=weights)


def _lepto_flood_depth_category(flood_depth_m: float) -> str:
    if flood_depth_m >= 1.5:
        return _weighted_choice(["deep", "moderate"], [0.7, 0.3])
    if flood_depth_m >= 0.8:
        return _weighted_choice(["moderate", "shallow"], [0.6, 0.4])
    if flood_depth_m >= 0.3:
        return _weighted_choice(["shallow", "minimal"], [0.7, 0.3])
    return _weighted_choice(["minimal", "shallow"], [0.8, 0.2])


def _lepto_cleanup_participation(cleanup_intensity: float) -> str:
    if isinstance(cleanup_intensity, str):
        intensity_map = {
            "very_high": 0.85,
            "high": 0.75,
            "medium": 0.6,
            "low": 0.35,
            "minimal": 0.15,
        }
        cleanup_intensity = intensity_map.get(cleanup_intensity.lower(), 0.5)
    if cleanup_intensity >= 0.75:
        return _weighted_choice(["heavy", "moderate", "light", "none"], [0.5, 0.3, 0.15, 0.05])
    if cleanup_intensity >= 0.45:
        return _weighted_choice(["heavy", "moderate", "light", "none"], [0.3, 0.4, 0.2, 0.1])
    return _weighted_choice(["moderate", "light", "none"], [0.3, 0.5, 0.2])


def _lepto_sanitation_type(coverage: float) -> str:
    if coverage >= 0.8:
        return _weighted_choice(["flush_toilet", "pit_latrine", "none"], [0.7, 0.25, 0.05])
    if coverage >= 0.6:
        return _weighted_choice(["flush_toilet", "pit_latrine", "none"], [0.5, 0.35, 0.15])
    return _weighted_choice(["flush_toilet", "pit_latrine", "none"], [0.3, 0.45, 0.25])


def _lepto_water_source(quality: str) -> str:
    quality = str(quality).lower()
    if quality == "good":
        return _weighted_choice(["municipal", "spring", "well"], [0.6, 0.25, 0.15])
    if quality == "fair":
        return _weighted_choice(["well", "municipal", "irrigation_canal"], [0.45, 0.25, 0.3])
    return _weighted_choice(["river", "irrigation_canal", "well"], [0.5, 0.35, 0.15])


def _lepto_rat_sightings(rat_population: str) -> str:
    rat_population = str(rat_population).lower()
    if rat_population in {"very_high", "high"}:
        return _weighted_choice(["very_many", "many", "some", "few"], [0.45, 0.3, 0.2, 0.05])
    if rat_population == "medium":
        return _weighted_choice(["many", "some", "few", "rare"], [0.3, 0.35, 0.25, 0.1])
    return _weighted_choice(["some", "few", "rare", "none"], [0.3, 0.35, 0.25, 0.1])


def _lepto_distance_to_river(flood_risk: str) -> float:
    flood_risk = str(flood_risk).lower()
    if flood_risk in {"very_high", "high"}:
        return float(np.random.uniform(10, 200))
    if flood_risk == "medium":
        return float(np.random.uniform(80, 400))
    return float(np.random.uniform(250, 800))


def _lepto_household_size() -> int:
    return int(_weighted_choice([3, 4, 5, 6, 7], [0.15, 0.25, 0.25, 0.2, 0.15]))


def _lepto_occupation(age: int) -> str:
    if age < 6:
        return "child"
    if age < 18:
        return "student"
    return _weighted_choice(
        ["farmer", "construction", "day_laborer", "vendor", "fisher", "teacher", "healthcare", "other"],
        [0.35, 0.15, 0.15, 0.1, 0.1, 0.05, 0.04, 0.06],
    )


def _initialize_row(columns: List[str]) -> Dict[str, Any]:
    return {column: None for column in columns}


def generate_full_population(villages_df, households_seed, individuals_seed, random_seed=42, scenario_type="je"):
    """
    Generate a complete population from seed data + generation rules.
    INCLUDES: Injection of specific 'Story Cases' (e.g. Tamu outlier for JE).

    Args:
        villages_df: DataFrame with village data
        households_seed: DataFrame with seed households
        individuals_seed: DataFrame with seed individuals
        random_seed: Random seed for reproducibility (default: 42)
        scenario_type: Type of outbreak scenario - "je" or "lepto" (default: "je")

    Uses (JE scenario):
    - Poisson distribution for pig ownership (λ=3 Nalu, λ=1 Kabwe, 0-1 Tamu)
    - Village-specific net use rates (30%, 50%, 70%)
    - Risk-based infection assignment

    Uses (Lepto scenario):
    - Flood depth, cleanup participation, rat sightings as risk factors
    - Male adults 18-60 at highest risk
    - Post-flood onset dates starting 2024-10-10
    """
    np.random.seed(random_seed)
    
    # Start with seed data
    all_households = [households_seed.copy()]
    all_individuals = [individuals_seed.copy()]
    
    # Track existing IDs and find max household/person numbers to avoid collisions
    existing_hh_ids = set(households_seed['hh_id'].tolist())
    max_hh_num = max([int(hh_id[2:]) for hh_id in existing_hh_ids]) if existing_hh_ids else 0
    hh_counter = max_hh_num + 1

    existing_person_ids = set(individuals_seed['person_id'].tolist())
    max_person_num = max([int(pid[1:]) for pid in existing_person_ids]) if existing_person_ids else 0
    person_counter = max(max_person_num + 1, 3000)  # Start at 3000 minimum for generated IDs
    if scenario_type == "je":
        # Generation parameters
        village_params = {
            'V1': {'pig_lambda': 3, 'net_rate': 0.30, 'rice_dist': (20, 150), 'proportion': 0.40},
            'V2': {'pig_lambda': 1, 'net_rate': 0.50, 'rice_dist': (80, 200), 'proportion': 0.40},
            'V3': {'pig_lambda': 0.2, 'net_rate': 0.70, 'rice_dist': (200, 500), 'proportion': 0.20}
        }

        target_households = 350

        # Generate additional households
        for village_id, params in village_params.items():
            n_hh = int(target_households * params['proportion'])
            village_row = villages_df[villages_df['village_id'] == village_id].iloc[0]

            for _ in range(n_hh):
                # Generate unique household ID (skip if already exists)
                hh_id = f'HH{hh_counter:03d}'
                while hh_id in existing_hh_ids:
                    hh_counter += 1
                    hh_id = f'HH{hh_counter:03d}'
                hh_counter += 1
                existing_hh_ids.add(hh_id)

                # Pig ownership (Poisson)
                pigs = min(np.random.poisson(params['pig_lambda']), 12)
                pig_dist = np.random.uniform(5, 50) if pigs > 0 else None

                # Mosquito nets
                nets = np.random.random() < params['net_rate']

                # Rice field distance
                rice_dist = np.random.uniform(*params['rice_dist'])

                # Children
                n_children = min(np.random.poisson(1.8), 5)

                # Scenario-specific vaccination attributes
                # JE vaccination coverage
                vacc_coverage = village_row.get('JE_vacc_coverage', 0.0)
                vacc_probs = [
                    1 - vacc_coverage,  # none
                    vacc_coverage * 0.4,  # low
                    vacc_coverage * 0.35,  # medium
                    vacc_coverage * 0.25   # high
                ]
                child_vacc = np.random.choice(['none', 'low', 'medium', 'high'], p=vacc_probs)

                all_households.append(pd.DataFrame([{
                    'hh_id': hh_id,
                    'village_id': village_id,
                    'pigs_owned': pigs,
                    'pig_pen_distance_m': pig_dist,
                    'uses_mosquito_nets': nets,
                    'rice_field_distance_m': rice_dist,
                    'children_under_15': n_children,
                    'JE_vaccination_children': child_vacc
                }]))

                # Generate household members
                n_adults = np.random.choice([1, 2, 3], p=[0.2, 0.6, 0.2])

                for i in range(n_adults):
                    age = np.random.randint(18, 65)
                    sex = 'M' if i == 0 and np.random.random() < 0.6 else np.random.choice(['M', 'F'])
                    occupation = np.random.choice(
                        ['farmer', 'trader', 'teacher', 'healthcare', 'other'],
                        p=[0.50, 0.20, 0.10, 0.05, 0.15]
                    )
                    vaccinated = np.random.random() < (vacc_coverage * 0.5)
                    evening_outdoor = np.random.random() < (0.8 if occupation == 'farmer' else 0.4)

                    all_individuals.append(pd.DataFrame([{
                        'person_id': f'P{person_counter:04d}',
                        'hh_id': hh_id,
                        'village_id': village_id,
                        'age': age,
                        'sex': sex,
                        'occupation': occupation,
                        'JE_vaccinated': vaccinated,
                        'evening_outdoor_exposure': evening_outdoor,
                        'true_je_infection': False,
                        'symptomatic_AES': False,
                        'severe_neuro': False,
                        'onset_date': None,
                        'outcome': None,
                        'has_sequelae': False,
                        'name_hint': None
                    }]))
                    person_counter += 1

                # Generate children
                for i in range(n_children):
                    age = np.random.randint(1, 15)
                    sex = np.random.choice(['M', 'F'])
                    occupation = 'child' if age < 6 else 'student'

                    if child_vacc == 'high':
                        vaccinated = np.random.random() < 0.85
                    elif child_vacc == 'medium':
                        vaccinated = np.random.random() < 0.50
                    elif child_vacc == 'low':
                        vaccinated = np.random.random() < 0.20
                    else:
                        vaccinated = False

                    evening_outdoor = np.random.random() < 0.7

                    all_individuals.append(pd.DataFrame([{
                        'person_id': f'P{person_counter:04d}',
                        'hh_id': hh_id,
                        'village_id': village_id,
                        'age': age,
                        'sex': sex,
                        'occupation': occupation,
                        'JE_vaccinated': vaccinated,
                        'evening_outdoor_exposure': evening_outdoor,
                        'true_je_infection': False,
                        'symptomatic_AES': False,
                        'severe_neuro': False,
                        'onset_date': None,
                        'outcome': None,
                        'has_sequelae': False,
                        'name_hint': None
                    }]))
                    person_counter += 1
    else:
        household_columns = list(households_seed.columns)
        individual_columns = list(individuals_seed.columns)
        village_targets = villages_df.set_index("village_id")["households"].to_dict()
        for village_id, target in village_targets.items():
            village_row = villages_df[villages_df["village_id"] == village_id].iloc[0]
            existing_count = households_seed[households_seed["village_id"] == village_id].shape[0]
            n_hh = max(0, int(target) - existing_count)

            for _ in range(n_hh):
                hh_id = f'HH{hh_counter:03d}'
                while hh_id in existing_hh_ids:
                    hh_counter += 1
                    hh_id = f'HH{hh_counter:03d}'
                hh_counter += 1
                existing_hh_ids.add(hh_id)

                household_size = _lepto_household_size()
                sanitation_type = _lepto_sanitation_type(village_row.get("sanitation_coverage", 0.6))
                water_source = _lepto_water_source(village_row.get("water_source_quality", "fair"))
                cleanup_participation = _lepto_cleanup_participation(village_row.get("cleanup_intensity", 0.5))
                flood_depth_category = _lepto_flood_depth_category(village_row.get("flood_depth_m", 0.3))
                rat_sightings = _lepto_rat_sightings(village_row.get("rat_population", "medium"))
                distance_to_river_m = _lepto_distance_to_river(village_row.get("flood_risk", "medium"))
                pig_ownership = int(min(np.random.poisson(1.1), 8))
                chicken_ownership = int(min(np.random.poisson(3.0), 12))

                household_row = _initialize_row(household_columns)
                household_row.update({
                    "hh_id": hh_id,
                    "village_id": village_id,
                    "household_size": household_size,
                    "sanitation_type": sanitation_type,
                    "water_source": water_source,
                    "flood_depth_category": flood_depth_category,
                    "cleanup_participation": cleanup_participation,
                    "rat_sightings_post_flood": rat_sightings,
                    "distance_to_river_m": distance_to_river_m,
                    "pig_ownership": pig_ownership,
                    "chicken_ownership": chicken_ownership,
                })
                all_households.append(pd.DataFrame([household_row]))

                for _ in range(household_size):
                    age = int(np.random.choice(
                        [np.random.randint(1, 15), np.random.randint(15, 61), np.random.randint(61, 85)],
                        p=[0.25, 0.6, 0.15],
                    ))
                    sex = np.random.choice(["M", "F"])
                    occupation = _lepto_occupation(age)
                    cleanup_prob = {
                        "heavy": 0.7,
                        "moderate": 0.5,
                        "light": 0.3,
                        "none": 0.05,
                    }.get(cleanup_participation, 0.2)
                    exposure_cleanup = np.random.random() < cleanup_prob if age >= 12 else np.random.random() < 0.1
                    barefoot_prob = 0.6 if cleanup_participation in {"heavy", "moderate"} else 0.3
                    exposure_barefoot = exposure_cleanup and (np.random.random() < barefoot_prob)
                    exposure_wounds = exposure_barefoot and (np.random.random() < 0.45)
                    animal_contact = (pig_ownership + chicken_ownership) > 0 and (np.random.random() < 0.45)
                    rat_contact = np.random.random() < (0.55 if rat_sightings in {"very_many", "many"} else 0.25)

                    individual_row = _initialize_row(individual_columns)
                    individual_row.update({
                        "person_id": f'P{person_counter:04d}',
                        "hh_id": hh_id,
                        "village_id": village_id,
                        "age": age,
                        "sex": sex,
                        "occupation": occupation,
                        "symptoms_fever": False,
                        "symptoms_headache": False,
                        "symptoms_myalgia": False,
                        "symptoms_conjunctival_suffusion": False,
                        "symptoms_jaundice": False,
                        "symptoms_renal_failure": False,
                        "outcome": None,
                        "days_to_hospital": None,
                        "exposure_cleanup_work": exposure_cleanup,
                        "exposure_barefoot_water": exposure_barefoot,
                        "exposure_skin_wounds": exposure_wounds,
                        "exposure_animal_contact": animal_contact,
                        "exposure_rat_contact": rat_contact,
                        "reported_to_hospital": False,
                        "name_hint": None,
                        "clinical_severity": None,
                        "onset_date": None,
                    })
                    all_individuals.append(pd.DataFrame([individual_row]))
                    person_counter += 1
    
    households_df = pd.concat(all_households, ignore_index=True)
    individuals_df = pd.concat(all_individuals, ignore_index=True)

    # === Scenario-specific infection assignment ===
    if scenario_type == "je":
        # === MANUALLY INJECT "TAMU OUTLIER" CASE (JE only) ===
        # Find a child in Tamu (V3)
        tamu_kids = individuals_df[
            (individuals_df['village_id'] == 'V3') &
            (individuals_df['age'] > 4) &
            (individuals_df['age'] < 10)
        ]

        if not tamu_kids.empty:
            # Pick one to be the "Story Case"
            idx = tamu_kids.index[0]
            # Make them sick
            individuals_df.at[idx, 'true_je_infection'] = True
            individuals_df.at[idx, 'symptomatic_AES'] = True
            individuals_df.at[idx, 'severe_neuro'] = True
            individuals_df.at[idx, 'outcome'] = 'recovered'
            individuals_df.at[idx, 'has_sequelae'] = True
            # Add the 'Secret' column that only appears if you dig
            individuals_df.at[idx, 'travel_history_note'] = "Visited Nalu 2 weeks ago."
            individuals_df.at[idx, 'name_hint'] = "Panya"

        # Assign JE infections using risk model (skip seed individuals)
        individuals_df = assign_je_infections(individuals_df, households_df)

    elif scenario_type == "lepto":
        # Assign Leptospirosis infections using risk model
        individuals_df = assign_lepto_infections(individuals_df, households_df)

    else:
        raise ValueError(f"Unknown scenario_type: {scenario_type}. Supported: 'je', 'lepto'")

    return households_df, individuals_df


def assign_je_infections(individuals_df, households_df):
    """
    Assign JE (Japanese Encephalitis) infections based on risk model.
    Preserves seed individual status.

    JE epidemiology:
    - Only ~1 in 250-1000 infections become symptomatic (encephalitis)
    - Attack rates in outbreaks: 1-10 per 10,000 population
    - We have ~5 seed symptomatic cases
    - Target: ~10-15 additional symptomatic cases (15-20 total)

    With ~1400 population and ~5% average infection rate, we'd get ~70 infections.
    We compress the ratio for teaching purposes but keep it realistic.
    """
    # Base infection risk by village (very low - most infections are asymptomatic)
    base_risk = {'V1': 0.025, 'V2': 0.010, 'V3': 0.002}
    
    # Create household lookup
    hh_lookup = households_df.set_index('hh_id').to_dict('index')
    
    def calculate_risk(row):
        # PROTECT SEED/INJECTED CASES
        if row.get('name_hint') == "Panya":
            return True  # Ensure Panya stays infected

        # Seed individuals keep their status
        if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
            if len(row['person_id']) <= 5:  # P0001, P1001, etc.
                return row['true_je_infection']
        
        risk = base_risk.get(row['village_id'], 0.002)
        
        hh = hh_lookup.get(row['hh_id'], {})
        if hh:
            # Risk factors (small increments)
            if hh.get('pigs_owned', 0) >= 3:
                risk += 0.015
            if pd.notna(hh.get('pig_pen_distance_m')) and hh.get('pig_pen_distance_m', 100) < 20:
                risk += 0.010
            if not hh.get('uses_mosquito_nets', True):
                risk += 0.010
            if hh.get('rice_field_distance_m', 200) < 100:
                risk += 0.008
        
        if row.get('JE_vaccinated', False):
            risk *= 0.15
        
        return np.random.random() < min(risk, 0.08)
    
    individuals_df['true_je_infection'] = individuals_df.apply(calculate_risk, axis=1)
    
    # Symptomatic AES - only a fraction of infections become encephalitis
    # Real rate is ~1/250, but we use higher for teaching purposes
    def assign_symptomatic(row):
        # PROTECT SEED/INJECTED CASES
        if row.get('name_hint') == "Panya":
            return row['symptomatic_AES']  # Preserve story case status

        if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
            if len(row['person_id']) <= 5:
                return row['symptomatic_AES']
        if not row['true_je_infection']:
            return False
        # Children much more likely to be symptomatic
        p_symp = 0.08 if row['age'] < 15 else 0.02
        return np.random.random() < p_symp
    
    individuals_df['symptomatic_AES'] = individuals_df.apply(assign_symptomatic, axis=1)
    
    # Severe neuro
    def assign_severe(row):
        # PROTECT SEED/INJECTED CASES
        if row.get('name_hint') == "Panya":
            return row['severe_neuro']  # Preserve story case status

        if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
            if len(row['person_id']) <= 5:
                return row['severe_neuro']
        if not row['symptomatic_AES']:
            return False
        return np.random.random() < 0.25
    
    individuals_df['severe_neuro'] = individuals_df.apply(assign_severe, axis=1)
    
    # Onset dates - spread over 2-3 weeks prior to start date
    def assign_onset(row):
        if pd.notna(row['onset_date']):
            return row['onset_date']
        if not row['symptomatic_AES']:
            return None

        # Start date is June 1, 2025
        # Spread onset dates over 2-3 weeks PRIOR (14-21 days before)
        base = datetime(2025, 6, 1)
        if row['village_id'] == 'V1':
            # Nalu: -21 to -7 days (May 11 to May 25)
            offset = np.random.randint(-21, -6)
        elif row['village_id'] == 'V2':
            # Kabwe: -18 to -7 days (May 14 to May 25)
            offset = np.random.randint(-18, -6)
        else:
            # Tamu: -21 to -10 days (May 11 to May 22)
            offset = np.random.randint(-21, -9)

        return (base + timedelta(days=offset)).strftime('%Y-%m-%d')
    
    individuals_df['onset_date'] = individuals_df.apply(assign_onset, axis=1)
    
    # Outcomes - now split into outcome and has_sequelae
    def assign_outcome(row):
        if pd.notna(row['outcome']):
            return row['outcome']
        if not row['symptomatic_AES']:
            return None
        if row['severe_neuro']:
            r = np.random.random()
            if r < 0.20:
                return 'died'
            else:
                return 'recovered'
        return 'recovered'

    def assign_sequelae(row):
        # Preserve existing has_sequelae if already set (e.g., Panya story case)
        if pd.notna(row.get('has_sequelae')) and row.get('has_sequelae'):
            return True
        if not row['symptomatic_AES']:
            return False
        if row['severe_neuro'] and row['outcome'] == 'recovered':
            # 45% of severe cases that recover have sequelae (65% - 20% died)
            return np.random.random() < 0.65
        elif row['outcome'] == 'recovered':
            # 5% of mild cases have sequelae
            return np.random.random() < 0.05
        return False

    individuals_df['outcome'] = individuals_df.apply(assign_outcome, axis=1)
    individuals_df['has_sequelae'] = individuals_df.apply(assign_sequelae, axis=1)

    return individuals_df


def assign_lepto_infections(individuals_df, households_df):
    """
    Assign Leptospirosis infections based on post-flood risk model.
    Preserves seed individual status.

    Leptospirosis epidemiology (post-flood outbreak):
    - Transmission via contact with contaminated floodwater/soil (rat urine)
    - Incubation: 2-30 days (median ~10 days, lognormal distribution)
    - Symptomatic rate: ~15% of infections
    - Severe cases (Weil's disease): ~25% of symptomatic
    - CFR: ~10% of severe cases (jaundice + renal failure)

    Risk factors:
    - Flood depth (deep > moderate > shallow > minimal)
    - Cleanup participation (heavy > moderate > light > none)
    - Rat sightings post-flood (very_many > many > some > few > rare > none)
    - Poor sanitation (none > pit_latrine > flush_toilet)
    - Unsafe water source (river > irrigation_canal > well > municipal > spring)
    - Demographics: males 18-60 at highest risk (occupational exposure)

    Target case counts:
    - V1 (Malinao): ~28 cases (epicenter)
    - V2 (San Rafael): ~4 cases
    - V3 (Riverside): ~2 cases
    - V4 (Malinis): 0 cases (control, upland)
    """
    # Base infection risk by village
    base_risk = {
        'V1': 0.035,  # Epicenter - severe flooding
        'V2': 0.005,  # Moderate risk
        'V3': 0.003,  # Low risk
        'V4': 0.000   # Control - no flooding
    }

    # Risk multipliers for household factors
    flood_depth_risk = {
        'deep': 1.5,
        'moderate': 1.0,
        'shallow': 0.5,
        'minimal': 0.1
    }

    cleanup_risk = {
        'heavy': 1.5,
        'moderate': 1.0,
        'light': 0.6,
        'none': 0.3
    }

    rat_sightings_risk = {
        'very_many': 1.8,
        'many': 1.4,
        'some': 1.0,
        'few': 0.6,
        'rare': 0.3,
        'none': 0.1
    }

    sanitation_risk = {
        'none': 1.5,
        'pit_latrine': 1.0,
        'flush_toilet': 0.5
    }

    water_source_risk = {
        'river': 1.6,
        'irrigation_canal': 1.4,
        'well': 1.0,
        'municipal': 0.6,
        'spring': 0.4
    }

    # Create household lookup
    hh_lookup = households_df.set_index('hh_id').to_dict('index')

    def calculate_lepto_risk(row):
        # Seed individuals keep their status (preserve seed cases)
        if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
            if len(row['person_id']) <= 5:  # P0001, P1001, etc.
                # For lepto, check if they have symptoms (seed cases are already assigned)
                return row.get('symptoms_fever', False) or row.get('true_lepto_infection', False)

        # V4 has no cases (control area)
        if row['village_id'] == 'V4':
            return False

        risk = base_risk.get(row['village_id'], 0.0)

        hh = hh_lookup.get(row['hh_id'], {})
        if hh:
            # Apply household risk multipliers
            risk *= flood_depth_risk.get(hh.get('flood_depth_category', 'minimal'), 0.5)
            risk *= cleanup_risk.get(hh.get('cleanup_participation', 'none'), 0.5)
            risk *= rat_sightings_risk.get(hh.get('rat_sightings_post_flood', 'few'), 0.5)
            risk *= sanitation_risk.get(hh.get('sanitation_type', 'flush_toilet'), 0.5)
            risk *= water_source_risk.get(hh.get('water_source', 'municipal'), 0.5)

        # Demographic risk: males 18-60 have highest exposure (cleanup work, outdoor labor)
        if row['sex'] == 'M' and 18 <= row['age'] <= 60:
            risk *= 1.8
        elif row['sex'] == 'M':
            risk *= 1.2
        # Women have lower occupational exposure
        elif row['sex'] == 'F' and 18 <= row['age'] <= 60:
            risk *= 0.8

        # Cap risk at reasonable level
        return np.random.random() < min(risk, 0.15)

    # Initialize lepto-specific columns if they don't exist
    if 'true_lepto_infection' not in individuals_df.columns:
        individuals_df['true_lepto_infection'] = False
    if 'symptomatic_lepto' not in individuals_df.columns:
        individuals_df['symptomatic_lepto'] = False
    if 'severe_lepto' not in individuals_df.columns:
        individuals_df['severe_lepto'] = False

    individuals_df['true_lepto_infection'] = individuals_df.apply(calculate_lepto_risk, axis=1)

    # Symptomatic cases - ~15% of infections become symptomatic
    def assign_lepto_symptomatic(row):
        # Preserve seed case status
        if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
            if len(row['person_id']) <= 5:
                return row.get('symptoms_fever', False)
        if not row['true_lepto_infection']:
            return False
        return np.random.random() < 0.15

    individuals_df['symptomatic_lepto'] = individuals_df.apply(assign_lepto_symptomatic, axis=1)

    # Severe cases (Weil's disease) - ~25% of symptomatic
    def assign_lepto_severe(row):
        # Preserve seed case status
        if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
            if len(row['person_id']) <= 5:
                severity = row.get('clinical_severity', '')
                return severity in ['severe', 'critical']
        if not row['symptomatic_lepto']:
            return False
        return np.random.random() < 0.25

    individuals_df['severe_lepto'] = individuals_df.apply(assign_lepto_severe, axis=1)

    # Onset dates - lognormal distribution, median 10 days post-flood
    # Flood ended 2024-10-10
    def assign_lepto_onset(row):
        if pd.notna(row.get('onset_date')):
            return row['onset_date']
        if not row['symptomatic_lepto']:
            return None

        # Lognormal incubation: median 10 days, range 2-30 days
        # lognormal params: mu=log(10), sigma=0.5 gives median ~10, range ~3-30
        incubation_days = int(np.random.lognormal(mean=np.log(10), sigma=0.5))
        incubation_days = max(2, min(30, incubation_days))  # Clamp to 2-30 days

        # Flood end date: 2024-10-10
        flood_end = datetime(2024, 10, 10)
        onset = flood_end + timedelta(days=incubation_days)
        return onset.strftime('%Y-%m-%d')

    individuals_df['onset_date'] = individuals_df.apply(assign_lepto_onset, axis=1)

    # Outcomes
    def assign_lepto_outcome(row):
        if pd.notna(row.get('outcome')):
            return row['outcome']
        if not row['symptomatic_lepto']:
            return None
        if row['severe_lepto']:
            # CFR ~10% of severe cases
            if np.random.random() < 0.10:
                return 'died'
            # Remaining severe cases hospitalized or recovering
            return np.random.choice(['hospitalized', 'recovering'], p=[0.6, 0.4])
        # Non-severe symptomatic cases mostly recover
        return np.random.choice(['recovered', 'recovering'], p=[0.7, 0.3])

    individuals_df['outcome'] = individuals_df.apply(assign_lepto_outcome, axis=1)

    # Assign individual symptoms based on symptomatic/severe status
    # This ensures case definition matching works for generated cases
    def assign_lepto_symptoms(row):
        # Skip seed cases - they already have symptoms from CSV
        if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
            if len(row['person_id']) <= 5:
                return row  # Keep existing values

        # Non-symptomatic cases have no symptoms
        if not row.get('symptomatic_lepto', False):
            return row

        # Symptomatic cases get symptoms based on severity
        is_severe = row.get('severe_lepto', False)

        # Fever - almost universal in symptomatic leptospirosis (>95%)
        row['symptoms_fever'] = np.random.random() < 0.98

        # Headache - very common (~80%)
        row['symptoms_headache'] = np.random.random() < 0.80

        # Myalgia (especially calf) - hallmark symptom (~85%)
        row['symptoms_myalgia'] = np.random.random() < 0.85

        # Conjunctival suffusion - common but more diagnostic (~50% mild, ~70% severe)
        if is_severe:
            row['symptoms_conjunctival_suffusion'] = np.random.random() < 0.70
        else:
            row['symptoms_conjunctival_suffusion'] = np.random.random() < 0.45

        # Jaundice - mainly severe cases (Weil's disease)
        if is_severe:
            row['symptoms_jaundice'] = np.random.random() < 0.85
        else:
            row['symptoms_jaundice'] = np.random.random() < 0.05

        # Renal failure - severe cases only
        if is_severe:
            row['symptoms_renal_failure'] = np.random.random() < 0.60
        else:
            row['symptoms_renal_failure'] = False

        return row

    individuals_df = individuals_df.apply(assign_lepto_symptoms, axis=1)

    return individuals_df


# ============================================================================
# CASE DEFINITION & DATASET GENERATION
# ============================================================================

CASE_CLASSIFICATIONS = ("confirmed", "probable", "suspected", "excluded", "not_a_case")


def _normalize_yes_no(value: Any) -> Optional[bool]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"yes", "y", "true", "1", "positive", "pos"}:
        return True
    if text in {"no", "n", "false", "0", "negative", "neg"}:
        return False
    if text in {"unknown", "unsure", "na", "n/a", ""}:
        return None
    return None


def _parse_date(value: Any) -> Optional[datetime]:
    if not value or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def _default_case_definition_structured(scenario_config: Dict[str, Any]) -> Dict[str, Any]:
    defaults = scenario_config.get("case_definition_defaults", {})
    symptoms = [s.get("key") for s in scenario_config.get("symptoms", []) if s.get("key")]
    core_symptom = symptoms[0:1] if symptoms else []
    return {
        "time_window": {
            "start": defaults.get("onset_start"),
            "end": defaults.get("onset_end"),
        },
        "villages": defaults.get("villages", []),
        "exclusions": scenario_config.get("exclusion_conditions", []),
        "tiers": {
            "suspected": {
                "required_any": core_symptom,
                "optional_symptoms": symptoms[1:],
                "min_optional": 0,
                "epi_link_required": False,
                "lab_required": False,
                "lab_tests": [],
            },
            "probable": {
                "required_any": core_symptom,
                "optional_symptoms": symptoms[1:],
                "min_optional": 0,
                "epi_link_required": True,
                "lab_required": False,
                "lab_tests": [],
            },
            "confirmed": {
                "required_any": core_symptom,
                "optional_symptoms": symptoms[1:],
                "min_optional": 0,
                "epi_link_required": False,
                "lab_required": True,
                "lab_tests": scenario_config.get("confirmatory_tests", []),
            },
        },
    }


def _normalize_case_definition(case_def: Optional[Dict[str, Any]], scenario_config: Dict[str, Any]) -> Dict[str, Any]:
    base = _default_case_definition_structured(scenario_config)
    if not case_def:
        return base
    normalized = copy.deepcopy(base)
    normalized.update({k: v for k, v in case_def.items() if k in {"time_window", "villages", "exclusions", "tiers"}})
    tiers = normalized.get("tiers", {})
    for tier in ("suspected", "probable", "confirmed"):
        if tier in case_def.get("tiers", {}):
            tiers[tier].update(case_def["tiers"][tier])
    normalized["tiers"] = tiers
    return normalized


def _get_symptom_value(row: pd.Series, symptom_key: str, scenario_config: Dict[str, Any], source: str) -> Optional[bool]:
    mapping = scenario_config.get("symptom_field_map", {}).get(symptom_key, {})
    field = mapping.get(source)
    if field and field in row:
        if field == "notes":
            text = str(row.get(field, "")).lower()
            if symptom_key.replace("_", " ") in text:
                return True
            return None
        return _normalize_yes_no(row.get(field))
    if symptom_key in row:
        return _normalize_yes_no(row.get(symptom_key))
    return None


def _epi_link_present(row: pd.Series, epi_fields: List[Dict[str, Any]]) -> bool:
    for field in epi_fields:
        key = field.get("key")
        if key and key in row and _normalize_yes_no(row.get(key)) is True:
            return True
    return False


def _within_time_place(row: pd.Series, case_def: Dict[str, Any]) -> bool:
    time_window = case_def.get("time_window", {})
    start = _parse_date(time_window.get("start"))
    end = _parse_date(time_window.get("end"))
    onset = _parse_date(row.get("onset_date"))
    if start and onset and onset < start:
        return False
    if end and onset and onset > end:
        return False
    villages = case_def.get("villages", [])
    if villages and row.get("village_id") not in villages:
        return False
    return True


def _build_lab_index(lab_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    lab_index: Dict[str, List[Dict[str, Any]]] = {}
    for result in lab_results or []:
        pid = str(result.get("patient_id") or result.get("linked_person_id") or "").strip()
        if not pid:
            continue
        lab_index.setdefault(pid, []).append(result)
    return lab_index


def _lab_status_for_patient(patient_id: str, lab_index: Dict[str, List[Dict[str, Any]]], scenario_config: Dict[str, Any]) -> Dict[str, Any]:
    results = lab_index.get(str(patient_id), [])
    confirmatory = set(scenario_config.get("confirmatory_tests", []))
    supportive = set(scenario_config.get("supportive_tests", []))
    exclusion_map = {e.get("code"): e.get("condition") for e in scenario_config.get("exclusion_tests", [])}
    status = {
        "confirmatory_positive": False,
        "supportive_positive": False,
        "exclusion_condition": None,
    }
    for r in results:
        test_code = r.get("test")
        result = str(r.get("result", "")).upper()
        if result != "POSITIVE":
            continue
        if test_code in confirmatory:
            status["confirmatory_positive"] = True
        if test_code in supportive:
            status["supportive_positive"] = True
        if test_code in exclusion_map:
            status["exclusion_condition"] = exclusion_map[test_code]
    return status


def _positive_tests(patient_id: str, lab_index: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    results = lab_index.get(str(patient_id), [])
    return [r.get("test") for r in results if str(r.get("result", "")).upper() == "POSITIVE"]


def _clinical_match(row: pd.Series, tier: Dict[str, Any], scenario_config: Dict[str, Any], source: str) -> bool:
    required_any = tier.get("required_any", []) or []
    optional = tier.get("optional_symptoms", []) or []
    min_optional = int(tier.get("min_optional", 0) or 0)

    any_ok = True
    if required_any:
        any_ok = any(_get_symptom_value(row, s, scenario_config, source) is True for s in required_any)
    optional_true = sum(_get_symptom_value(row, s, scenario_config, source) is True for s in optional)
    return any_ok and optional_true >= min_optional


def classify_record(
    row: pd.Series,
    case_def: Dict[str, Any],
    scenario_config: Dict[str, Any],
    lab_index: Dict[str, List[Dict[str, Any]]],
    source: str = "individuals",
) -> Tuple[str, Optional[str]]:
    case_def = _normalize_case_definition(case_def, scenario_config)
    if not _within_time_place(row, case_def):
        return "not_a_case", "Outside time/place window"

    lab_status = _lab_status_for_patient(str(row.get("person_id", "")), lab_index, scenario_config)
    if lab_status.get("exclusion_condition"):
        return "excluded", f"Rule-out: {lab_status['exclusion_condition']}"

    epi_required = case_def.get("tiers", {}).get("probable", {}).get("epi_link_required", False)
    epi_link = _epi_link_present(row, scenario_config.get("epi_link_fields", []))
    if epi_required and not epi_link:
        epi_link = False

    tiers = case_def.get("tiers", {})
    confirmed = tiers.get("confirmed", {})
    probable = tiers.get("probable", {})
    suspected = tiers.get("suspected", {})

    if confirmed and _clinical_match(row, confirmed, scenario_config, source):
        if confirmed.get("lab_required", True):
            allowed_tests = confirmed.get("lab_tests") or scenario_config.get("confirmatory_tests", [])
            positive_tests = _positive_tests(str(row.get("person_id", "")), lab_index)
            if any(test in allowed_tests for test in positive_tests):
                return "confirmed", None
        else:
            return "confirmed", None

    if probable and _clinical_match(row, probable, scenario_config, source):
        if probable.get("epi_link_required") and not epi_link:
            pass
        else:
            if probable.get("lab_required"):
                allowed_tests = probable.get("lab_tests") or scenario_config.get("supportive_tests", [])
                positive_tests = _positive_tests(str(row.get("person_id", "")), lab_index)
                if any(test in allowed_tests for test in positive_tests):
                    return "probable", None
            else:
                return "probable", None

    if suspected and _clinical_match(row, suspected, scenario_config, source):
        return "suspected", None

    return "not_a_case", None


def classify_individuals(
    individuals_df: pd.DataFrame,
    case_def: Optional[Dict[str, Any]],
    scenario_config: Dict[str, Any],
    lab_results: Optional[List[Dict[str, Any]]] = None,
) -> pd.DataFrame:
    df = individuals_df.copy()
    lab_index = _build_lab_index(lab_results or [])
    classifications = []
    exclusion_reasons = []
    for _, row in df.iterrows():
        classification, reason = classify_record(row, case_def, scenario_config, lab_index, source="individuals")
        classifications.append(classification)
        exclusion_reasons.append(reason)
    df["case_classification"] = classifications
    df["exclusion_reason"] = exclusion_reasons
    return df


def apply_case_definition(individuals_df: pd.DataFrame, case_criteria: dict) -> pd.DataFrame:
    """
    Apply case definition criteria to filter individuals.

    Args:
        individuals_df: DataFrame with individual records
        case_criteria: Dictionary with structured case definition and scenario metadata

    Returns:
        DataFrame filtered to individuals meeting case definition tiers
    """
    df = individuals_df.copy()
    scenario_id = case_criteria.get("scenario_id")
    scenario_config = load_scenario_config(scenario_id) if scenario_id else {}
    case_def = case_criteria.get("case_definition_structured", case_criteria.get("case_definition", case_criteria))
    lab_results = case_criteria.get("lab_results", [])
    classified = classify_individuals(df, case_def, scenario_config, lab_results)
    return classified[classified["case_classification"].isin({"suspected", "probable", "confirmed"})].copy()


# ============================================================================
# XLSFORM PARSING + MAPPING + RENDERING
# ============================================================================

def detect_xlsform_type(file_bytes: bytes) -> str:
    """Return 'xlsform' | 'submission_export' | 'unknown'."""
    if not (isinstance(file_bytes, (bytes, bytearray)) and len(file_bytes) > 4):
        return "unknown"
    if file_bytes[:2] != b"PK":
        return "unknown"
    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
        sheet_l = {s.lower(): s for s in xl.sheet_names}
        if "survey" in sheet_l:
            return "xlsform"
        for s in xl.sheet_names[:3]:
            df = pd.read_excel(xl, sheet_name=s, nrows=5)
            cols = {str(c).lower() for c in df.columns}
            if any(meta in cols for meta in ["_submission_time", "_uuid", "_id", "_index"]):
                return "submission_export"
    except Exception:
        return "unknown"
    return "unknown"


def parse_xlsform(file_bytes: bytes) -> Dict[str, Any]:
    """Parse an XLSForm definition (.xlsx) into a normalized questionnaire object."""
    ftype = detect_xlsform_type(file_bytes)
    if ftype == "submission_export":
        raise ValueError(
            "This looks like a DATA export (submissions), not an XLSForm (form definition). "
            "In Kobo, open the form and download the XLSForm, then upload that file here."
        )
    if ftype != "xlsform":
        raise ValueError(
            "Could not find a 'survey' sheet. Please upload the XLSForm (form definition) exported from Kobo."
        )

    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    sheet_l = {s.lower(): s for s in xl.sheet_names}
    survey = pd.read_excel(xl, sheet_name=sheet_l["survey"]).copy()
    survey.columns = [str(c).strip() for c in survey.columns]
    if "type" not in survey.columns or "name" not in survey.columns:
        raise ValueError("XLSForm 'survey' sheet must include at least 'type' and 'name' columns.")

    choices = pd.DataFrame(columns=["list_name", "name", "label"])
    if "choices" in sheet_l:
        choices = pd.read_excel(xl, sheet_name=sheet_l["choices"]).copy()
        choices.columns = [str(c).strip() for c in choices.columns]

    # Try to coerce choice column names
    lower_map = {c.lower(): c for c in choices.columns}
    if "list_name" not in lower_map and "list name" in lower_map:
        choices = choices.rename(columns={lower_map["list name"]: "list_name"})
    if "list_name" in lower_map and lower_map["list_name"] != "list_name":
        choices = choices.rename(columns={lower_map["list_name"]: "list_name"})
    if "name" in lower_map and lower_map["name"] != "name":
        choices = choices.rename(columns={lower_map["name"]: "name"})
    if "label" in lower_map and lower_map["label"] != "label":
        choices = choices.rename(columns={lower_map["label"]: "label"})

    for c in ["list_name", "name", "label"]:
        if c not in choices.columns:
            choices[c] = np.nan

    qnames = survey["name"].astype(str).fillna("").str.strip()
    bad = qnames.eq("") | qnames.str.contains(r"\s")
    if bad.any():
        bad_rows = survey.loc[bad, ["name"]].index.tolist()
        raise ValueError(f"Invalid question 'name' (blank or contains spaces) at survey rows: {bad_rows[:10]}")
    if qnames.duplicated().any():
        dups = qnames[qnames.duplicated()].unique().tolist()
        raise ValueError(f"Duplicate question names detected: {dups[:10]}")

    # Build choices dictionary
    choice_map: Dict[str, List[Dict[str, str]]] = {}
    if len(choices) > 0:
        for ln, grp in choices.groupby("list_name"):
            if pd.isna(ln):
                continue
            opts: List[Dict[str, str]] = []
            for _, r in grp.iterrows():
                oname = str(r.get("name", "")).strip()
                if not oname:
                    continue
                opts.append({"name": oname, "label": str(r.get("label", "")).strip()})
            choice_map[str(ln).strip()] = opts

    questions: List[Dict[str, Any]] = []
    for _, row in survey.iterrows():
        qtype = str(row.get("type", "")).strip()
        qname = str(row.get("name", "")).strip()
        if not qtype or not qname:
            continue

        qtype_l = qtype.lower()
        if qtype_l.startswith("begin ") or qtype_l.startswith("end ") or qtype_l in {"note", "calculate"}:
            continue

        base_type = qtype_l.split()[0]
        list_name = None
        if base_type in {"select_one", "select_multiple"}:
            parts = qtype.split()
            if len(parts) >= 2:
                list_name = parts[1].strip()

        label = str(row.get("label", row.get("label::English", ""))).strip()

        questions.append({
            "name": qname,
            "label": label,
            "type_raw": qtype,
            "base_type": base_type,
            "list_name": list_name,
            "choices": choice_map.get(list_name, []) if list_name else [],
            "relevant": str(row.get("relevant", "")).strip(),
            "constraint": str(row.get("constraint", "")).strip(),
        })

    if not questions:
        raise ValueError("No survey questions were found. (Rows like begin/end group or notes are ignored.)")

    return {
        "meta": {"parsed_at": datetime.utcnow().isoformat() + "Z", "n_questions": len(questions)},
        "questions": questions,
    }


def _extract_json(text: str) -> Any:
    """Best-effort extraction of JSON from an LLM response."""
    text = text.strip()
    m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
    if not m:
        raise ValueError("No JSON found in response.")

    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"Found JSON-like structure but failed to parse it: {str(e)}") from e



# NOTE: llm_map_xlsform_questions is defined later in this file (around line 3000+)
# with improved error handling and updated model defaults.


def _find_other_choice_name(choices: List[Dict[str, str]]) -> Optional[str]:
    """Return the choice 'name' that best represents an 'Other' option, if any."""
    for c in choices:
        nm = str(c.get("name", "")).strip()
        lb = str(c.get("label", "")).strip()
        if not nm:
            continue
        if nm.lower() in {"other", "other_specify", "other_spec"}:
            return nm
        if "other" in lb.lower():
            return nm
    return None


def _apply_choice_map_with_fallback(values: pd.Series,
                                   choice_map: Dict[str, Optional[str]],
                                   choices: List[Dict[str, str]]) -> pd.Series:
    """Map truth categorical values to trainee choice names, falling back to 'Other' when available."""
    other_name = _find_other_choice_name(choices)
    def _map_one(v):
        if pd.isna(v):
            return np.nan
        key = str(v)
        out = choice_map.get(key)
        if out is None or out == "" or (isinstance(out, float) and np.isnan(out)):
            return other_name if other_name else np.nan
        return out
    return values.apply(_map_one)



# NOTE: llm_build_select_one_choice_maps is defined later in this file (around line 3000+)
# with improved error handling and updated model defaults.


def _is_yes_no_choice_set(choices: List[Dict[str, str]]) -> Optional[Dict[bool, str]]:
    names = [str(c.get("name", "")).strip().lower() for c in choices]
    yes_tokens = {"yes", "y", "1", "true"}
    no_tokens = {"no", "n", "0", "false"}
    if any(n in yes_tokens for n in names) and any(n in no_tokens for n in names):
        yes_name = next(c.get("name") for c in choices if str(c.get("name", "")).strip().lower() in yes_tokens)
        no_name = next(c.get("name") for c in choices if str(c.get("name", "")).strip().lower() in no_tokens)
        return {True: yes_name, False: no_name}
    return None


def _messy_text_variants_for_category(cat: str) -> List[str]:
    base = cat.strip().lower()
    if base == "farmer":
        return ["farmer", "rice farmer", "farm work", "works in fields", "agriculture"]
    if base == "caretaker":
        return ["caretaker", "home duties", "stays at home", "caregiver", "house work"]
    if base == "trader":
        return ["trader", "market seller", "sells goods", "small business", "shop/market"]
    if base == "student":
        return ["student", "school", "in school", "pupil", "studying"]
    if base == "child":
        return ["child", "young child", "kid", "small child", "too young for work"]
    if base == "teacher":
        return ["teacher", "school teacher", "teaches", "primary teacher", "classroom teacher"]
    if base == "healthcare":
        return ["health worker", "clinic staff", "healthcare", "nurse aide", "hospital worker"]
    if base == "other":
        return ["other", "odd jobs", "casual work", "day labor", "misc work"]
    return [cat]


def prepare_question_render_plan(questionnaire: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure each question has enough info to render values (choice maps, etc.)."""
    for q in questionnaire.get("questions", []):
        base = q.get("base_type")
        mapped = q.get("mapped_var")
        if base not in SUPPORTED_XLSFORM_BASE_TYPES:
            continue

        meta = CANONICAL_SCHEMA.get(mapped, {}) if mapped else {}
        q["value_type"] = meta.get("value_type")
        q.setdefault("render", {})
        q["render"].setdefault("missing_base", 0.05)

        if base == "select_one" and mapped and meta.get("value_type") == "bool":
            yn = _is_yes_no_choice_set(q.get("choices", []))
            if yn:
                q["render"]["choice_map"] = {"true": yn[True], "false": yn[False]}

        if base == "select_one" and mapped and meta.get("value_type") == "category":
            if "choice_map" not in q.get("render", {}):
                categories = meta.get("categories", [])
                options = [c.get("name") for c in q.get("choices", []) if c.get("name")]
                opt_l = {str(o).lower(): o for o in options}
                cm = {str(cat): opt_l.get(str(cat).lower()) for cat in categories if str(cat).lower() in opt_l}
                if cm:
                    q["render"]["choice_map"] = cm

        if base == "select_multiple":
            if "choice_var_map" not in q.get("render", {}):
                choice_var_map: Dict[str, str] = {}
                for ch in q.get("choices", []):
                    nm = str(ch.get("name", "")).lower()
                    lb = str(ch.get("label", "")).lower()
                    txt = nm + " " + lb
                    if "net" in txt or "bed" in txt:
                        choice_var_map[ch.get("name")] = "uses_mosquito_nets"
                    elif "pig" in txt:
                        choice_var_map[ch.get("name")] = "pigs_near_home"
                    elif "rice" in txt or "paddy" in txt:
                        choice_var_map[ch.get("name")] = "rice_field_nearby"
                    elif "vacc" in txt or "immun" in txt:
                        choice_var_map[ch.get("name")] = "JE_vaccinated"
                    elif "dusk" in txt or "even" in txt or "night" in txt:
                        choice_var_map[ch.get("name")] = "evening_outdoor_exposure"
                if choice_var_map:
                    q["render"]["choice_var_map"] = choice_var_map

    questionnaire.setdefault("meta", {})
    questionnaire["meta"]["render_plan_ready_at"] = datetime.utcnow().isoformat() + "Z"
    return questionnaire


def _apply_missingness(series: pd.Series, missing_rate: float, rng: np.random.RandomState) -> pd.Series:
    if missing_rate <= 0:
        return series
    mask = rng.rand(len(series)) < missing_rate
    out = series.copy()
    out.loc[mask] = np.nan
    return out



def render_dataset_from_xlsform(master_df: pd.DataFrame, questionnaire: Dict[str, Any],
                                unlocked_domains: Optional[set] = None,
                                random_seed: int = 42) -> pd.DataFrame:
    """Render trainee-visible dataset columns based on XLSForm question types + mappings.

    Key behaviors:
    - Uses LLM-derived mappings (q['render']['mapped_var']) to pull values from the truth/master dataset.
    - If a question is **unmapped**, uses the stored LLM generator spec (q['render']['unmapped_spec'])
      to synthesize plausible values **without per-row LLM calls**.
    - Output column names are the trainee's XLSForm *question names*.
    - unlocked_domains (if provided) gates domains until evidence is gathered via interviews/actions.
    """
    rng = np.random.RandomState(random_seed)

    # Minimal identifiers always included
    base_cols = [c for c in ["person_id", "hh_id", "village_id", "case_status"] if c in master_df.columns]
    out = master_df[base_cols].copy()

    questions = questionnaire.get("questions", []) or []
    locked_domains = set()
    for idx, q in enumerate(questions):
        base = q.get("base_type")
        if base not in SUPPORTED_XLSFORM_BASE_TYPES:
            continue

        qname = q.get("name")
        if not qname:
            continue

        mapped = q.get("mapped_var")

        # Unmapped → synthesize values (if a spec exists)
        if (not mapped) or (mapped not in CANONICAL_SCHEMA) or (CANONICAL_SCHEMA.get(mapped, {}).get("column") not in master_df.columns):
            spec_obj = (q.get("render") or {}).get("unmapped_spec")
            if isinstance(spec_obj, dict) and spec_obj:
                # use a different seed per question for stability
                out[qname] = _generate_unmapped_column(out, q, random_seed=random_seed + 1000 + idx)
            else:
                out[qname] = np.nan
            continue

        if unlocked_domains is not None:
            domain = CANONICAL_SCHEMA.get(mapped, {}).get("domain")
            if domain and domain not in unlocked_domains:
                out[qname] = np.nan
                locked_domains.add(domain)
                continue

        truth_col = CANONICAL_SCHEMA[mapped]["column"]
        values = master_df[truth_col].copy()

        missing_rate = float((q.get("render") or {}).get("missing_base", 0.05))

        if base == "text":
            if mapped == "occupation":
                def _render_occ(v):
                    if pd.isna(v):
                        return np.nan
                    variants = _messy_text_variants_for_category(str(v))
                    return rng.choice(variants)
                rendered = values.apply(_render_occ)
            else:
                rendered = values.astype(str)
            out[qname] = _apply_missingness(rendered, missing_rate, rng)

        elif base == "integer":
            rendered = pd.to_numeric(values, errors="coerce").round()
            rendered = rendered.astype("Int64")
            out[qname] = _apply_missingness(rendered.astype("float"), missing_rate, rng).astype("Int64")

        elif base == "decimal":
            rendered = pd.to_numeric(values, errors="coerce")
            out[qname] = _apply_missingness(rendered, missing_rate, rng)

        elif base == "date":
            rendered = pd.to_datetime(values, errors="coerce").dt.strftime("%Y-%m-%d")
            out[qname] = _apply_missingness(rendered, missing_rate, rng)

        elif base == "select_one":
            choices = q.get("choices", []) or []
            choice_map = (q.get("render") or {}).get("choice_map", {}) or {}
            vt = CANONICAL_SCHEMA[mapped].get("value_type")

            if vt == "bool" and choice_map:
                rendered = values.astype(bool).map({True: choice_map.get("true"), False: choice_map.get("false")})
            elif vt == "category" and choice_map:
                rendered = _apply_choice_map_with_fallback(values, choice_map, choices)
            else:
                opt_l = {str(c.get("name")).lower(): c.get("name") for c in choices if c.get("name")}
                rendered = values.astype(str).map(lambda v: opt_l.get(str(v).lower(), np.nan))

            out[qname] = _apply_missingness(rendered, missing_rate, rng)

        elif base == "select_multiple":
            # Use choice_var_map heuristic where available; else generate sparse random selection.
            choices = q.get("choices", []) or []
            choice_var_map = (q.get("render") or {}).get("choice_var_map", {}) or {}
            choice_names = [c.get("name") for c in choices if c.get("name")]
            if not choice_names:
                out[qname] = _apply_missingness(pd.Series([""] * len(master_df)), missing_rate, rng)
            else:
                selected_strings = []
                for row_i in range(len(master_df)):
                    sel = []
                    for nm in choice_names:
                        mapped_var = choice_var_map.get(nm)
                        if mapped_var and mapped_var in CANONICAL_SCHEMA and CANONICAL_SCHEMA[mapped_var]["column"] in master_df.columns:
                            v = master_df.loc[master_df.index[row_i], CANONICAL_SCHEMA[mapped_var]["column"]]
                            # bool-ish trigger
                            if isinstance(v, (bool, np.bool_)) and bool(v):
                                if rng.rand() < 0.85:
                                    sel.append(nm)
                            elif pd.notna(v) and str(v).lower() in {"1", "true", "yes"}:
                                if rng.rand() < 0.85:
                                    sel.append(nm)
                        else:
                            # small baseline chance
                            if rng.rand() < 0.05:
                                sel.append(nm)
                    # cap to keep realistic
                    if len(sel) > 3:
                        sel = list(rng.choice(sel, size=3, replace=False))
                    selected_strings.append(" ".join(sel) if sel else "")
                out[qname] = _apply_missingness(pd.Series(selected_strings, index=master_df.index), missing_rate, rng)

        else:
            out[qname] = np.nan

    if isinstance(questionnaire, dict):
        questionnaire.setdefault("meta", {})
        if locked_domains:
            questionnaire["meta"]["locked_domains"] = sorted(locked_domains)
    return out

def _age_group(age: Any) -> str:
    try:
        a = float(age)
    except Exception:
        return "unk"
    if a < 5:
        return "0-4"
    if a < 15:
        return "5-14"
    if a < 30:
        return "15-29"
    if a < 45:
        return "30-44"
    if a < 60:
        return "45-59"
    return "60+"

def ensure_reported_to_hospital(individuals_df: pd.DataFrame, random_seed: int = 42) -> pd.DataFrame:
    """Create a realistic 'reported_to_hospital' proxy if not already present."""
    if "reported_to_hospital" in individuals_df.columns:
        return individuals_df

    rng = np.random.default_rng(random_seed)

    # Base healthcare-seeking + severity gradient (tunable)
    village_factor = individuals_df.get("village_id", pd.Series(["V2"] * len(individuals_df))).map(
        {"V1": 0.08, "V2": 0.05, "V3": 0.02}
    ).fillna(0.04)

    symptomatic = individuals_df.get("symptomatic_AES", pd.Series([False] * len(individuals_df))).astype(bool)
    severe = individuals_df.get("severe_neuro", pd.Series([False] * len(individuals_df))).astype(bool)
    vaccinated = individuals_df.get("JE_vaccinated", pd.Series([False] * len(individuals_df))).astype(bool)

    p = (
        0.04
        + village_factor
        + symptomatic.astype(float) * 0.20
        + severe.astype(float) * 0.35
        - vaccinated.astype(float) * 0.06
    )
    p = np.clip(p.to_numpy(dtype=float), 0.01, 0.95)

    reported = rng.random(len(individuals_df)) < p
    out = individuals_df.copy()
    out["reported_to_hospital"] = reported
    return out


def _eligible_controls_pool(
    individuals_df: pd.DataFrame,
    cases_df: pd.DataFrame,
    households_df: pd.DataFrame,
    control_source: str,
    include_symptomatic_noncase: bool,
    eligible_villages: Optional[List[str]],
    control_age_range: Optional[Dict[str, int]],
    random_seed: int,
) -> pd.DataFrame:
    """Build the eligible pool for controls under different sources (community/neighborhood/clinic)."""
    df = individuals_df.copy()

    # Define non-cases
    if include_symptomatic_noncase:
        non_cases = df[df.get("symptomatic_AES", False).astype(bool) == False].copy()
    else:
        non_cases = df[df.get("symptomatic_AES", False).astype(bool) == False].copy()

    # Village eligibility default = same villages as selected cases
    if not eligible_villages:
        eligible_villages = sorted(list(set(cases_df["village_id"].dropna().astype(str).tolist())))

    non_cases = non_cases[non_cases["village_id"].isin(eligible_villages)].copy()

    # Age eligibility
    if control_age_range and isinstance(control_age_range, dict):
        amin = int(control_age_range.get("min", 0))
        amax = int(control_age_range.get("max", 120))
        non_cases = non_cases[(non_cases["age"] >= amin) & (non_cases["age"] <= amax)].copy()

    # Control source behavior
    control_source = (control_source or "community").lower()

    if control_source in {"clinic", "hospital", "hospital_controls"}:
        non_cases = ensure_reported_to_hospital(non_cases, random_seed=random_seed)
        non_cases = non_cases[non_cases["reported_to_hospital"] == True].copy()

    elif control_source in {"neighborhood", "neighbourhood", "near"}:
        # Approximate neighborhood: prefer households numerically close to case households (HH###).
        rng = np.random.default_rng(random_seed)
        case_hh = set(cases_df["hh_id"].dropna().astype(str).tolist())
        # If no parseable HH IDs, fall back to same-village community.
        def _hh_num(hh: str) -> Optional[int]:
            m = re.search(r"(\d+)", str(hh))
            return int(m.group(1)) if m else None

        case_nums = [n for n in (_hh_num(h) for h in case_hh) if n is not None]
        if case_nums:
            # score households by closeness to any case HH number
            hh_nums = non_cases["hh_id"].astype(str).apply(_hh_num)
            # compute distance to closest case hh
            closest = []
            for n in hh_nums:
                if n is None:
                    closest.append(999)
                else:
                    closest.append(min(abs(n - cn) for cn in case_nums))
            non_cases = non_cases.copy()
            non_cases["_hh_dist"] = closest
            # weight selection toward closer households
            non_cases["_w"] = np.exp(-np.clip(non_cases["_hh_dist"].to_numpy(dtype=float), 0, 50) / 8.0)
            # Keep pool but store weights for later sampling
        else:
            non_cases["_w"] = 1.0

    else:
        # Community
        non_cases["_w"] = 1.0

    return non_cases


def _apply_nonresponse_and_replacements(
    selected: pd.DataFrame,
    pool: pd.DataFrame,
    target_n: int,
    nonresponse_rate: float,
    allow_replacement: bool,
    match_keys: Optional[List[str]],
    random_seed: int,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Apply nonresponse; optionally replace with similar individuals from the remaining pool."""
    rng = np.random.default_rng(random_seed)
    selected = selected.copy()

    # Mark response
    nonresponse_rate = float(np.clip(nonresponse_rate, 0.0, 0.95))
    responded = rng.random(len(selected)) >= nonresponse_rate
    selected["responded"] = responded

    responded_df = selected[selected["responded"] == True].copy()
    nonresp_df = selected[selected["responded"] == False].copy()

    report = {
        "selected": int(len(selected)),
        "responded": int(len(responded_df)),
        "nonresponded": int(len(nonresp_df)),
        "replaced": 0,
        "replacement_relaxed": 0,
    }

    if not allow_replacement:
        final = responded_df.copy()
        return final, report

    need = max(0, int(target_n) - int(len(responded_df)))
    if need == 0:
        return responded_df.copy(), report

    remaining_pool = pool.copy()
    # Exclude anyone already selected
    if "person_id" in remaining_pool.columns:
        remaining_pool = remaining_pool[~remaining_pool["person_id"].isin(set(selected["person_id"].tolist()))].copy()

    replacements = []
    relaxed = 0

    def _sample_from(dfsub: pd.DataFrame, k: int) -> pd.DataFrame:
        if dfsub.empty or k <= 0:
            return dfsub.head(0)
        if "_w" in dfsub.columns:
            w = dfsub["_w"].to_numpy(dtype=float)
            w = np.clip(w, 1e-6, None)
            w = w / w.sum()
            idx = rng.choice(dfsub.index.to_numpy(), size=min(k, len(dfsub)), replace=False, p=w)
            return dfsub.loc[idx].copy()
        return dfsub.sample(n=min(k, len(dfsub)), random_state=random_seed)

    # Try strict matching first
    if match_keys:
        # Build a flexible candidate subset by matching on the most important keys
        strict_keys = list(match_keys)
        # If any keys missing in pool, drop them
        strict_keys = [k for k in strict_keys if k in remaining_pool.columns and k in responded_df.columns]

        if strict_keys:
            # Frequency-match to the distribution in responded_df
            for _, grp in responded_df.groupby(strict_keys):
                if len(replacements) >= need:
                    break
                cond = True
                for k in strict_keys:
                    cond = cond & (remaining_pool[k] == grp.iloc[0][k])
                cand = remaining_pool[cond].copy()
                take = min(int(len(grp)), need - len(replacements))
                samp = _sample_from(cand, take)
                if not samp.empty:
                    replacements.append(samp)

    if replacements:
        rep_df = pd.concat(replacements, ignore_index=True)
    else:
        rep_df = remaining_pool.head(0)

    if len(rep_df) < need:
        # Relax: sample from any remaining
        relaxed = need - len(rep_df)
        extra = _sample_from(remaining_pool[~remaining_pool.index.isin(set(rep_df.index))], relaxed)
        if not extra.empty:
            rep_df = pd.concat([rep_df, extra], ignore_index=True)

    if not rep_df.empty:
        rep_df = rep_df.head(need).copy()
        rep_df["responded"] = True
        rep_df["replaced_flag"] = True
        report["replaced"] = int(len(rep_df))
        report["replacement_relaxed"] = int(relaxed)

    final = pd.concat([responded_df, rep_df], ignore_index=True)
    final["replaced_flag"] = final.get("replaced_flag", False).fillna(False)
    return final, report


def generate_study_dataset(individuals_df, households_df, decisions, random_seed=42):
    """
    Generate a trainee-visible dataset based on their study design, sampling decisions, and questionnaire.

    Sampling enhancements:
    - Trainees can manually select cases/controls by person_id (decisions['selected_cases'], decisions['selected_controls'])
    - Supports clinic controls (healthcare-seeking proxy), neighborhood controls (approximate), and community controls
    - Applies nonresponse (5–25% typical) and optional replacement sampling
    - Produces a sampling frame report when decisions['return_sampling_report'] is True

    Questionnaire enhancements:
    - XLSForm-driven mode (preferred): decisions['questionnaire_xlsform'] produced by parse_xlsform + LLM mapping.
    - Legacy mode is still supported.
    """
    np.random.seed(random_seed)

    # Determine the symptomatic column based on scenario type
    scenario_id = decisions.get("scenario_id", "")
    if "lepto" in scenario_id.lower() or "rivergate" in scenario_id.lower():
        symptomatic_column = "symptomatic_lepto"
    else:
        symptomatic_column = "symptomatic_AES"

    # Ensure reported_to_hospital is available for clinic-control logic
    individuals_df = ensure_reported_to_hospital(individuals_df, random_seed=random_seed)

    # Determine case pool based on case definition (scenario-aware)
    case_criteria = {
        "scenario_id": decisions.get("scenario_id"),
        "case_definition_structured": decisions.get("case_definition_structured"),
        "lab_results": decisions.get("lab_results", []),
    }
    cases_pool = apply_case_definition(individuals_df, case_criteria)

    study_design = decisions.get("study_design", {"type": "case_control"})
    design_type = study_design.get("type", "case_control")

    sampling_plan = decisions.get("sampling_plan", {}) or {}
    nonresponse_rate = float(sampling_plan.get("nonresponse_rate", decisions.get("nonresponse_rate", 0.0) or 0.0))
    allow_replacement = bool(sampling_plan.get("allow_replacement", sampling_plan.get("replacement", False)))

    sampling_report: Dict[str, Any] = {"design": design_type, "random_seed": random_seed}

    # -------------------------
    # Select sample according to design
    # -------------------------
    if design_type == "case_control":
        # Targets
        n_cases_target = int(decisions.get("sample_size", {}).get("cases", sampling_plan.get("n_cases", 15)))
        controls_per_case = int(study_design.get("controls_per_case", sampling_plan.get("controls_per_case", 2)))
        control_target = None  # set after actual case count

        # Manual selections (preferred when present)
        selected_case_ids = decisions.get("selected_cases") or decisions.get("selected_case_ids") or []
        selected_control_ids = decisions.get("selected_controls") or decisions.get("selected_control_ids") or []

        if selected_case_ids:
            cases_selected = cases_pool[cases_pool["person_id"].isin(selected_case_ids)].copy()
        else:
            cases_selected = cases_pool.sample(n=min(n_cases_target, len(cases_pool)), random_state=random_seed).copy()

        # Determine control eligibility pool based on source
        control_source = (sampling_plan.get("control_source", "community") or "community")
        eligible_villages = sampling_plan.get("eligible_villages", None)
        include_symptomatic_noncase = bool(sampling_plan.get("include_symptomatic_noncase", False))
        control_age_range = sampling_plan.get("control_age_range", None)

        controls_pool = _eligible_controls_pool(
            individuals_df=individuals_df,
            cases_df=cases_selected,
            households_df=households_df,
            control_source=control_source,
            include_symptomatic_noncase=include_symptomatic_noncase,
            eligible_villages=eligible_villages,
            control_age_range=control_age_range,
            random_seed=random_seed,
        )

        # Compute required number of controls
        control_target = int(len(cases_selected) * controls_per_case)

        if selected_control_ids:
            controls_selected = controls_pool[controls_pool["person_id"].isin(selected_control_ids)].copy()
        else:
            # Auto-sample controls from pool (weighted if neighborhood)
            controls_selected = controls_pool.sample(n=min(control_target, len(controls_pool)), random_state=random_seed).copy()

        # Add match helpers
        cases_selected["age_group"] = cases_selected["age"].apply(_age_group)
        controls_selected["age_group"] = controls_selected["age"].apply(_age_group)

        # Apply nonresponse + replacement separately to cases and controls
        # Cases: replacements should also be cases (from cases_pool minus selected)
        cases_final, cases_rep = _apply_nonresponse_and_replacements(
            selected=cases_selected,
            pool=cases_pool,
            target_n=min(n_cases_target, len(cases_pool)) if not selected_case_ids else int(len(cases_selected)),
            nonresponse_rate=nonresponse_rate,
            allow_replacement=allow_replacement,
            match_keys=["village_id", "age_group"],
            random_seed=random_seed + 1,
        )

        # Controls: replacements from controls_pool
        controls_final, controls_rep = _apply_nonresponse_and_replacements(
            selected=controls_selected,
            pool=controls_pool,
            target_n=control_target if not selected_control_ids else int(len(controls_selected)),
            nonresponse_rate=nonresponse_rate,
            allow_replacement=allow_replacement,
            match_keys=["village_id", "age_group"],
            random_seed=random_seed + 2,
        )

        cases_final["case_status"] = 1
        controls_final["case_status"] = 0
        cases_final["sample_role"] = "case"
        controls_final["sample_role"] = "control"
        controls_final["sampling_source"] = control_source
        cases_final["sampling_source"] = sampling_plan.get("case_source", "cases_pool")

        study_df = pd.concat([cases_final, controls_final], ignore_index=True)

        sampling_report.update({
            "case_pool_n": int(len(cases_pool)),
            "control_pool_n": int(len(controls_pool)),
            "cases_target": int(n_cases_target),
            "controls_target": int(control_target),
            "cases_selected_n": int(len(cases_selected)),
            "controls_selected_n": int(len(controls_selected)),
            "cases_after_nonresponse_n": int(len(cases_final)),
            "controls_after_nonresponse_n": int(len(controls_final)),
            "cases_nonresponse": cases_rep,
            "controls_nonresponse": controls_rep,
        })

    elif design_type == "cohort":
        # Placeholder cohort sampling (unchanged) — can be upgraded later to allow manual selection.
        cohort = individuals_df[
            (individuals_df["age"] <= 15) &
            (individuals_df["village_id"].isin(["V1", "V2"]))
        ].copy()
        cohort["case_status"] = cohort[symptomatic_column].astype(int)
        cohort["sample_role"] = "cohort_member"
        cohort["sampling_source"] = "village_cohort"
        study_df = cohort
        sampling_report.update({"cohort_n": int(len(cohort))})

    else:
        sample_size = int(decisions.get("sample_size", {}).get("total", 100))
        study_df = individuals_df.sample(n=min(sample_size, len(individuals_df)), random_state=random_seed).copy()
        study_df["case_status"] = study_df[symptomatic_column].astype(int)
        study_df["sample_role"] = "sample"
        study_df["sampling_source"] = "simple_random"
        sampling_report.update({"sample_n": int(len(study_df))})

    # -------------------------
    # Add household-level and derived columns needed by canonical schema
    # -------------------------
    hh_lookup = households_df.set_index("hh_id").to_dict("index")

    study_df["pigs_near_home"] = study_df["hh_id"].apply(
        lambda hh: (hh_lookup.get(hh, {}).get("pigs_owned", 0) or 0) > 0 and
                   (hh_lookup.get(hh, {}).get("pig_pen_distance_m") or 100) < 30
    )
    study_df["uses_mosquito_nets"] = study_df["hh_id"].apply(
        lambda hh: bool(hh_lookup.get(hh, {}).get("uses_mosquito_nets", True))
    )
    study_df["rice_field_nearby"] = study_df["hh_id"].apply(
        lambda hh: (hh_lookup.get(hh, {}).get("rice_field_distance_m", 200) or 200) < 100
    )

    study_df["pigs_owned"] = study_df["hh_id"].apply(lambda hh: hh_lookup.get(hh, {}).get("pigs_owned", np.nan))
    study_df["pig_pen_distance_m"] = study_df["hh_id"].apply(lambda hh: hh_lookup.get(hh, {}).get("pig_pen_distance_m", np.nan))
    study_df["rice_field_distance_m"] = study_df["hh_id"].apply(lambda hh: hh_lookup.get(hh, {}).get("rice_field_distance_m", np.nan))
    study_df["JE_vaccination_children"] = study_df["hh_id"].apply(lambda hh: hh_lookup.get(hh, {}).get("JE_vaccination_children", np.nan))

    # -------------------------
    # XLSForm-driven questionnaire rendering (preferred)
    # -------------------------
    questionnaire = decisions.get("questionnaire_xlsform")
    if isinstance(questionnaire, dict) and questionnaire.get("questions"):
        # unlocked_domains is no longer used for gating questionnaire elements, but kept for backward compatibility
        unlocked = set(decisions.get("unlocked_domains", []) or [])
        questionnaire = prepare_question_render_plan(questionnaire)
        df_out = render_dataset_from_xlsform(study_df, questionnaire, unlocked_domains=unlocked, random_seed=random_seed)

        if decisions.get("return_sampling_report"):
            return df_out, sampling_report
        return df_out

    # -------------------------
    # Legacy questionnaire mode (keyword mapping)
    # -------------------------
    mapped_cols = decisions.get("mapped_columns", [])
    col_mapping = {
        "age": "age",
        "sex": "sex",
        "village": "village_id",
        "vaccin": "JE_vaccinated",
        "dusk": "evening_outdoor_exposure",
        "evening": "evening_outdoor_exposure",
        "outdoor": "evening_outdoor_exposure",
        "pig": "pigs_near_home",
        "net": "uses_mosquito_nets",
        "rice": "rice_field_nearby",
        "aes": "symptomatic_AES",
        "onset": "onset_date",
        "occup": "occupation",
        "outcome": "outcome",
    }

    base_cols = ["person_id", "hh_id", "village_id", "case_status", "sample_role", "sampling_source"]
    available_cols = base_cols.copy()

    for col in mapped_cols:
        col_lower = str(col).lower()
        if col in study_df.columns:
            available_cols.append(col)
            continue
        for key, mapped in col_mapping.items():
            if key in col_lower and mapped in study_df.columns:
                available_cols.append(mapped)
                break

    available_cols = list(dict.fromkeys([c for c in available_cols if c in study_df.columns]))
    final_df = study_df[available_cols].copy()
    final_df = inject_data_noise(final_df)

    if decisions.get("return_sampling_report"):
        return final_df, sampling_report
    return final_df

def inject_data_noise(df, missing_rate=0.08, error_rate=0.02, random_seed=42):
    """
    Inject realistic data quality issues:
    - Random missing values (5-10%)
    - Occasional coding errors
    - Inconsistent formatting
    """
    np.random.seed(random_seed)
    df = df.copy()
    
    n_rows = len(df)
    
    for col in df.columns:
        if col in ['person_id', 'case_status']:  # Don't corrupt key fields
            continue
        
        # Random missingness
        n_missing = int(n_rows * missing_rate)
        missing_idx = np.random.choice(df.index, size=n_missing, replace=False)
        df.loc[missing_idx, col] = np.nan
        
        # For boolean columns, occasionally flip values
        if df[col].dtype == bool:
            n_errors = int(n_rows * error_rate)
            error_idx = np.random.choice(df.index, size=n_errors, replace=False)
            df.loc[error_idx, col] = ~df.loc[error_idx, col]
    
    return df



# ============================================================================
# XLSFORM QUESTIONNAIRE PIPELINE (Upload → Parse → LLM Mapping → Type-Aware Rendering)
# ============================================================================

def _looks_like_kobo_data_export(df: pd.DataFrame) -> bool:
    """Heuristic: Kobo/ODK submission exports usually include metadata fields like _uuid."""
    cols = {c.strip() for c in df.columns.astype(str)}
    meta_markers = {"_uuid", "_id", "_submission_time", "_submitted_by", "_index", "_parent_index"}
    return len(cols.intersection(meta_markers)) >= 2


def parse_xlsform_from_bytes(xlsx_bytes: bytes) -> Dict[str, Any]:
    """
    Parse an XLSForm (form definition) exported from Kobo/ODK into a normalized dict.

    Raises ValueError if the workbook appears to be a data export (submissions) rather than a form definition.
    """
    if not isinstance(xlsx_bytes, (bytes, bytearray)):
        raise ValueError("Expected XLSForm bytes.")

    try:
        xls = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    except Exception as e:
        raise ValueError(f"Unable to read Excel workbook: {e}")

    sheet_names = {s.lower(): s for s in xls.sheet_names}

    if "survey" not in sheet_names:
        # Try to detect if this is a submissions export (common user mistake)
        first_sheet = xls.sheet_names[0]
        df0 = pd.read_excel(xls, sheet_name=first_sheet)
        if _looks_like_kobo_data_export(df0):
            raise ValueError(
                "This file looks like a Kobo/ODK DATA EXPORT (submissions). "
                "Please upload the XLSForm (form definition) with a 'survey' sheet."
            )
        raise ValueError(
            "This workbook does not appear to be an XLSForm definition (missing 'survey' sheet)."
        )

    survey_df = pd.read_excel(xls, sheet_name=sheet_names["survey"]).fillna("")
    choices_df = pd.read_excel(xls, sheet_name=sheet_names["choices"]).fillna("") if "choices" in sheet_names else pd.DataFrame()

    # Basic required columns
    survey_cols = {c.lower(): c for c in survey_df.columns.astype(str)}
    if "type" not in survey_cols or "name" not in survey_cols:
        raise ValueError("XLSForm 'survey' sheet must include at least 'type' and 'name' columns.")

    def norm(s: Any) -> str:
        return str(s).strip()

    # Build choices lookup: list_name -> [{name,label}, ...]
    choices_lookup: Dict[str, List[Dict[str, str]]] = {}
    if not choices_df.empty:
        ccols = {c.lower(): c for c in choices_df.columns.astype(str)}
        if "list_name" in ccols and "name" in ccols:
            for _, r in choices_df.iterrows():
                list_name = norm(r.get(ccols["list_name"], ""))
                if not list_name:
                    continue
                item = {
                    "name": norm(r.get(ccols["name"], "")),
                    "label": norm(r.get(ccols.get("label", ccols.get("label::english", "")), "")) if ("label" in ccols or "label::english" in ccols) else ""
                }
                if item["name"] == "":
                    continue
                choices_lookup.setdefault(list_name, []).append(item)

    q_list: List[Dict[str, Any]] = []
    tcol = survey_cols["type"]; ncol = survey_cols["name"]
    lcol = survey_cols.get("label") or survey_cols.get("label::english")

    for _, r in survey_df.iterrows():
        raw_type = norm(r.get(tcol, ""))
        name = norm(r.get(ncol, ""))
        label = norm(r.get(lcol, "")) if lcol else ""

        if not raw_type or not name:
            continue

        # Skip structural rows
        low_type = raw_type.lower()
        if low_type.startswith("begin ") or low_type.startswith("end ") or low_type in {"note", "calculate"}:
            continue

        # Determine base type and list name
        base_type = None
        list_name = None
        if low_type.startswith("select_one"):
            base_type = "select_one"
            parts = low_type.split()
            list_name = parts[1] if len(parts) >= 2 else None
        elif low_type.startswith("select_multiple"):
            base_type = "select_multiple"
            parts = low_type.split()
            list_name = parts[1] if len(parts) >= 2 else None
        else:
            # normalize a few common variants
            if low_type in {"integer", "int"}:
                base_type = "integer"
            elif low_type in {"decimal"}:
                base_type = "decimal"
            elif low_type in {"text", "string"}:
                base_type = "text"
            elif low_type in {"date"}:
                base_type = "date"
            else:
                # unsupported question type
                continue

        if base_type not in SUPPORTED_XLSFORM_BASE_TYPES:
            continue

        q = {
            "name": name,
            "label": label or name,
            "raw_type": raw_type,
            "base_type": base_type,
            "list_name": list_name,
            "choices": choices_lookup.get(list_name, []) if list_name else [],
            # mapping/render fields filled later
            "mapped_var": None,
            "confidence": None,
            "domain": None,
            "rationale": None,
            "render": {}
        }
        q_list.append(q)

    # Validate uniqueness of names
    names = [q["name"] for q in q_list]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"Duplicate question 'name' values detected in survey: {sorted(list(dupes))[:10]}")

    return {
        "meta": {"parsed_at": datetime.utcnow().isoformat(), "n_questions": len(q_list)},
        "questions": q_list,
    }


def llm_map_xlsform_questions(questionnaire: Dict[str, Any], api_key: str, model: str = "claude-3-5-sonnet-20241022") -> Dict[str, Any]:
    """
    Map XLSForm questions to canonical truth variables in CANONICAL_SCHEMA.

    Returns questionnaire with per-question fields:
      mapped_var, confidence (0-1), domain, rationale
    """
    if not api_key:
        raise ValueError("Missing LLM API key for mapping.")

    try:
        import anthropic  # type: ignore
    except Exception as e:
        raise ImportError(f"anthropic package not available: {e}")

    schema = []
    for k, v in CANONICAL_SCHEMA.items():
        schema.append({
            "canonical_variable": k,
            "domain": v.get("domain"),
            "value_type": v.get("value_type"),
            "description": v.get("description"),
            "categories": v.get("categories", None)
        })

    q_payload = []
    for q in questionnaire.get("questions", []):
        q_payload.append({
            "name": q["name"],
            "label": q.get("label", ""),
            "base_type": q.get("base_type"),
            "choices": [c.get("label") or c.get("name") for c in (q.get("choices") or [])][:40]
        })

    prompt = {
        "task": "Map each XLSForm question to the best matching canonical variable, or null if none match.",
        "instructions": [
            "Use question label + choices to infer meaning.",
            "Prefer exact epidemiologic meaning over superficial word similarity.",
            "Return a JSON list with one object per question: {name, mapped_var, confidence, domain, rationale}.",
            "confidence is 0-1. Use <0.5 if ambiguous.",
            "domain should be one of: demographics, clinical, vaccination, behavior, vector, animals, environment, other.",
            "If question asks something not in schema, set mapped_var=null."
        ],
        "canonical_schema": schema,
        "questions": q_payload
    }

    client = anthropic.Anthropic(api_key=api_key)

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=1600,
            temperature=0.2,
            messages=[{"role": "user", "content": json.dumps(prompt)}],
        )
    except Exception as e:
        raise RuntimeError(f"Failed to call Anthropic API for question mapping: {str(e)}") from e

    # Extract JSON from response
    text_out = ""
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            text_out += block.text

    # Try to find JSON array
    m = re.search(r"(\[.*\])", text_out, flags=re.DOTALL)
    if not m:
        raise ValueError("LLM mapping did not return a JSON array. Response may be malformed.")

    try:
        parsed = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from LLM mapping response: {str(e)}") from e

    by_name = {r["name"]: r for r in parsed if isinstance(r, dict) and "name" in r}
    for q in questionnaire.get("questions", []):
        r = by_name.get(q["name"])
        if not r:
            continue
        q["mapped_var"] = r.get("mapped_var")
        q["confidence"] = r.get("confidence")
        q["domain"] = r.get("domain")
        q["rationale"] = r.get("rationale")

    return questionnaire


def llm_build_select_one_choice_maps(questionnaire: Dict[str, Any], api_key: str, model: str = "claude-3-5-sonnet-20241022",
                                    min_confidence_to_apply: float = 0.50) -> Dict[str, Any]:
    """
    For mapped categorical select_one questions, build a mapping from truth categories -> trainee choice 'name'.
    Stored at q['render']['choice_map'].
    """
    if not api_key:
        raise ValueError("Missing LLM API key for remapping.")

    try:
        import anthropic  # type: ignore
    except Exception as e:
        raise ImportError(f"anthropic package not available: {e}")

    work = []
    for q in questionnaire.get("questions", []):
        if q.get("base_type") != "select_one":
            continue
        mv = q.get("mapped_var")
        conf = q.get("confidence") or 0.0
        if (not mv) or (conf < min_confidence_to_apply):
            continue
        schema = CANONICAL_SCHEMA.get(mv)
        if not schema or schema.get("value_type") != "category":
            continue
        choices = q.get("choices") or []
        if not choices:
            continue
        work.append({
            "question_name": q["name"],
            "question_label": q.get("label", ""),
            "canonical_variable": mv,
            "truth_categories": schema.get("categories", []),
            "choices": [{"name": c.get("name"), "label": c.get("label") or c.get("name")} for c in choices]
        })

    if not work:
        return questionnaire

    prompt = {
        "task": "For each question, map each truth category to the single best choice name. Use 'other' if present when needed.",
        "instructions": [
            "Return JSON object: {question_name: {truth_category: choice_name, ...}, ...}.",
            "Choice_name MUST be one of the provided choices[].name.",
            "If there is an 'other' option, use it when truth category doesn't fit.",
            "Do not invent new choice names."
        ],
        "items": work
    }

    client = anthropic.Anthropic(api_key=api_key)

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=1400,
            temperature=0.2,
            messages=[{"role": "user", "content": json.dumps(prompt)}],
        )
    except Exception as e:
        raise RuntimeError(f"Failed to call Anthropic API for choice mapping: {str(e)}") from e

    text_out = ""
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            text_out += block.text

    m = re.search(r"({.*})", text_out, flags=re.DOTALL)
    if not m:
        raise ValueError("LLM remapper did not return a JSON object. Response may be malformed.")

    try:
        maps = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from LLM choice mapping response: {str(e)}") from e

    for q in questionnaire.get("questions", []):
        qmap = maps.get(q["name"])
        if isinstance(qmap, dict):
            q.setdefault("render", {})["choice_map"] = qmap

    return questionnaire


def llm_build_unmapped_answer_generators(
    questionnaire: Dict[str, Any],
    api_key: str,
    model: str = "claude-3-5-sonnet-20241022",
    batch_size: int = 12,
) -> Dict[str, Any]:
    """
    For questions with mapped_var == None, ask the LLM to return a compact generator spec.
    Generator specs may optionally include group-specific overrides by village_id and/or case_status.

    Stored at q['render']['unmapped_spec'].
    """
    if not api_key:
        raise ValueError("Missing LLM API key for unmapped generator.")

    try:
        import anthropic  # type: ignore
    except Exception as e:
        raise ImportError(f"anthropic package not available: {e}")

    unmapped = []
    for q in questionnaire.get("questions", []):
        if q.get("mapped_var") is None:
            unmapped.append({
                "name": q["name"],
                "label": q.get("label", ""),
                "base_type": q.get("base_type"),
                "choices": [{"name": c.get("name"), "label": c.get("label") or c.get("name")} for c in (q.get("choices") or [])][:40]
            })

    if not unmapped:
        return questionnaire

    client = anthropic.Anthropic(api_key=api_key)

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    all_specs: Dict[str, Any] = {}

    for batch in chunks(unmapped, batch_size):
        prompt = {
            "task": "Create compact synthetic-data generator specs for unmapped survey questions in an outbreak investigation questionnaire.",
            "context": {
                "villages": ["V1", "V2", "V3"],
                "case_status": {"1": "case", "0": "control"}
            },
            "instructions": [
                "Return a JSON object keyed by question name.",
                "Each value must be: {missing_rate, base, optional_overrides}.",
                "missing_rate is 0-0.6.",
                "base is required and depends on base_type.",
                "optional_overrides MAY include distributions by village and/or case_status if it makes epidemiologic sense.",
                "Do NOT require per-row generation. Provide reusable parameters, variants lists, and weights."
            ],
            "spec_schemas": {
                "text": {
                    "base": {"variants": ["..."], "weights": [0.2, 0.1, "..."], "messy_rate": 0.2},
                    "overrides": {
                        "by_village": {"V1": {"variants": ["..."], "weights": [...]}, "V2": {...}},
                        "by_case_status": {"case": {"variants": ["..."], "weights": [...]}, "control": {...}},
                        "by_case_village": {"case|V1": {"variants": ["..."], "weights": [...]}}
                    }
                },
                "integer_or_decimal": {
                    "base": {"dist": "normal|uniform|poisson", "mean": 10, "sd": 3, "min": 0, "max": 100, "round_to": 1, "heap_ends": [0,5]},
                    "overrides": {"by_village": {"V1": {...}}, "by_case_status": {"case": {...}}, "by_case_village": {"case|V1": {...}}}
                },
                "date": {
                    "base": {"start": "2025-05-01", "end": "2025-07-01"},
                    "overrides": {"by_village": {"V1": {"start": "...", "end": "..."}}}
                },
                "select_one": {
                    "base": {"choice_weights": {"<choice_name>": 0.2, "...": 0.1}, "by_case_status": {"case": {"<choice_name>": 0.3}}}
                },
                "select_multiple": {
                    "base": {"choice_probs": {"<choice_name>": 0.2, "...": 0.1}, "max_select": 3, "by_case_status": {"case": {"<choice_name>": 0.4}}}
                }
            },
            "questions": batch
        }

        try:
            msg = client.messages.create(
                model=model,
                max_tokens=1800,
                temperature=0.4,
                messages=[{"role": "user", "content": json.dumps(prompt)}],
            )

            text_out = ""
            for block in msg.content:
                if getattr(block, "type", None) == "text":
                    text_out += block.text

            m = re.search(r"({.*})", text_out, flags=re.DOTALL)
            if not m:
                # Log warning but continue with other batches
                import warnings
                warnings.warn(f"LLM unmapped generator batch did not return a JSON object. Skipping batch.")
                continue

            specs = json.loads(m.group(1))
            if isinstance(specs, dict):
                all_specs.update(specs)
        except json.JSONDecodeError as e:
            # Log warning but continue with other batches
            import warnings
            warnings.warn(f"Failed to parse JSON from unmapped generator batch: {str(e)}. Skipping batch.")
            continue
        except Exception as e:
            # Log warning but continue with other batches
            import warnings
            warnings.warn(f"Failed to process unmapped generator batch: {str(e)}. Skipping batch.")
            continue

    for q in questionnaire.get("questions", []):
        spec = all_specs.get(q["name"])
        if isinstance(spec, dict):
            q.setdefault("render", {})["unmapped_spec"] = spec

    return questionnaire


def _pick_override_spec(spec_obj: Dict[str, Any], case_status: Optional[str], village_id: Optional[str]) -> Dict[str, Any]:
    """Pick the most specific override spec available."""
    overrides = spec_obj.get("optional_overrides") or spec_obj.get("overrides") or {}
    # case_status expected as 'case'/'control'
    key_cv = f"{case_status}|{village_id}" if case_status and village_id else None
    by_case_village = overrides.get("by_case_village") or {}
    if key_cv and key_cv in by_case_village:
        return by_case_village[key_cv]
    by_case = overrides.get("by_case_status") or {}
    if case_status and case_status in by_case:
        return by_case[case_status]
    by_village = overrides.get("by_village") or {}
    if village_id and village_id in by_village:
        return by_village[village_id]
    return spec_obj.get("base") or {}


def _generate_unmapped_column(df: pd.DataFrame, q: Dict[str, Any], random_seed: int = 42) -> pd.Series:
    """
    Generate a column for an unmapped question using its stored generator spec.
    Supports optional group-specific overrides by village and/or case status.
    """
    np.random.seed(random_seed)
    spec_obj = (q.get("render") or {}).get("unmapped_spec") or {}
    missing_rate = float(spec_obj.get("missing_rate", 0.12))

    base_type = q.get("base_type")
    choices = q.get("choices") or []

    # Determine per-row groups
    def row_case_status(row) -> Optional[str]:
        if "case_status" in row:
            return "case" if int(row["case_status"]) == 1 else "control"
        if "is_case" in row:
            return "case" if bool(row["is_case"]) else "control"
        return None

    out = []
    for _, row in df.iterrows():
        cs = row_case_status(row)
        vid = row.get("village_id") if "village_id" in df.columns else None

        # Allow missing_rate overrides too
        ov = spec_obj.get("optional_overrides") or spec_obj.get("overrides") or {}
        mr = missing_rate
        if cs and vid:
            mr = ov.get("missing_rate_by_case_village", {}).get(f"{cs}|{vid}", mr)
        if cs:
            mr = ov.get("missing_rate_by_case_status", {}).get(cs, mr)
        if vid:
            mr = ov.get("missing_rate_by_village", {}).get(vid, mr)

        if np.random.random() < mr:
            out.append(np.nan)
            continue

        spec = _pick_override_spec(spec_obj, cs, vid)

        if base_type == "text":
            variants = spec.get("variants") or ["unknown"]
            weights = spec.get("weights")
            messy_rate = float(spec.get("messy_rate", 0.2))
            val = np.random.choice(variants, p=_normalize_weights(weights, len(variants)))
            if np.random.random() < messy_rate:
                val = _messify_text(str(val))
            out.append(val)

        elif base_type in {"integer", "decimal"}:
            dist = (spec.get("dist") or "normal").lower()
            min_v = spec.get("min", None); max_v = spec.get("max", None)
            round_to = spec.get("round_to", 1 if base_type == "integer" else 0.1)
            heap_ends = spec.get("heap_ends", [])

            if dist == "uniform":
                a = float(spec.get("min", 0)); b = float(spec.get("max", a+10))
                x = np.random.uniform(a, b)
            elif dist == "poisson":
                lam = float(spec.get("mean", 5))
                x = np.random.poisson(lam)
            else:
                mean = float(spec.get("mean", 10)); sd = float(spec.get("sd", 3))
                x = np.random.normal(mean, sd)

            if min_v is not None:
                x = max(float(min_v), float(x))
            if max_v is not None:
                x = min(float(max_v), float(x))

            x = _apply_rounding_and_heaping(x, round_to=round_to, heap_ends=heap_ends)

            if base_type == "integer":
                out.append(int(round(float(x))))
            else:
                out.append(float(x))

        elif base_type == "date":
            start = spec.get("start") or "2025-05-01"
            end = spec.get("end") or "2025-07-01"
            out.append(_sample_date(start, end))

        elif base_type == "select_one":
            # Build weights for provided choice names
            weight_map = (spec.get("choice_weights") or {}).copy()
            # Allow case-status override weights (already supported conceptually)
            if isinstance(spec.get("by_case_status"), dict):
                cs_map = spec["by_case_status"].get(cs) if cs else None
                if isinstance(cs_map, dict):
                    weight_map = {**weight_map, **cs_map}

            choice_names = [c.get("name") for c in choices if c.get("name")]
            if not choice_names:
                out.append(np.nan); continue

            weights = [float(weight_map.get(n, 0.0)) for n in choice_names]
            if sum(weights) <= 0:
                weights = None
            out.append(np.random.choice(choice_names, p=_normalize_weights(weights, len(choice_names))))

        elif base_type == "select_multiple":
            prob_map = (spec.get("choice_probs") or {}).copy()
            if isinstance(spec.get("by_case_status"), dict):
                cs_map = spec["by_case_status"].get(cs) if cs else None
                if isinstance(cs_map, dict):
                    prob_map = {**prob_map, **cs_map}

            choice_names = [c.get("name") for c in choices if c.get("name")]
            if not choice_names:
                out.append(np.nan); continue

            max_select = int(spec.get("max_select", 3))
            selected = []
            for n in choice_names:
                p = float(prob_map.get(n, 0.0))
                if np.random.random() < min(max(p, 0.0), 1.0):
                    selected.append(n)
            if len(selected) > max_select:
                selected = list(np.random.choice(selected, size=max_select, replace=False))
            out.append(" ".join(selected) if selected else "")

        else:
            out.append(np.nan)

    return pd.Series(out, index=df.index)


def _normalize_weights(weights: Optional[List[float]], n: int) -> np.ndarray:
    if weights is None:
        return np.ones(n) / n
    w = np.array([float(x) for x in weights], dtype=float)
    if w.size != n:
        w = np.ones(n)
    w[w < 0] = 0
    s = w.sum()
    if s <= 0:
        return np.ones(n) / n
    return w / s


def _messify_text(s: str) -> str:
    # Mild, realistic messiness (no silly corruption)
    s2 = s.strip()
    if not s2:
        return s2
    # random casing
    r = np.random.random()
    if r < 0.2:
        s2 = s2.lower()
    elif r < 0.35:
        s2 = s2.upper()
    # occasional extra whitespace/punctuation
    if np.random.random() < 0.15:
        s2 = s2.replace(" ", "  ")
    if np.random.random() < 0.10:
        s2 = s2 + np.random.choice([".", ",", ""])
    return s2


def _apply_rounding_and_heaping(x: float, round_to: float = 1.0, heap_ends: Optional[List[int]] = None) -> float:
    try:
        rt = float(round_to)
    except Exception:
        rt = 1.0
    if rt <= 0:
        rt = 1.0
    y = round(float(x) / rt) * rt
    if heap_ends:
        # occasional heaping to nearest 0/5 etc.
        if np.random.random() < 0.25:
            end = int(np.random.choice(heap_ends))
            y = (int(y) // 10) * 10 + end
    return y


def _sample_date(start_ymd: str, end_ymd: str) -> str:
    try:
        s = datetime.strptime(start_ymd, "%Y-%m-%d")
        e = datetime.strptime(end_ymd, "%Y-%m-%d")
    except Exception:
        s = datetime(2025, 5, 1); e = datetime(2025, 7, 1)
    if e <= s:
        e = s + timedelta(days=1)
    delta = (e - s).days
    d = s + timedelta(days=int(np.random.randint(0, delta + 1)))
    return d.strftime("%Y-%m-%d")


# ============================================================================
# LABORATORY SIMULATION
# ============================================================================


LAB_TESTS = {
    # Human (arbovirus)
    "JE_IgM_CSF": {"sensitivity": 0.85, "specificity": 0.98, "cost": 2, "days": 3, "inconclusive_rate": 0.06,
                   "sensitivity_by_days": [(0, 4, 0.4), (5, 999, 0.9)]},
    "JE_IgM_serum": {"sensitivity": 0.80, "specificity": 0.95, "cost": 1, "days": 3, "inconclusive_rate": 0.08,
                     "sensitivity_by_days": [(0, 4, 0.35), (5, 999, 0.85)]},
    "JE_PCR_CSF": {"sensitivity": 0.40, "specificity": 0.99, "cost": 3, "days": 4, "inconclusive_rate": 0.10,
                   "sensitivity_by_days": [(0, 3, 0.65), (4, 7, 0.45), (8, 999, 0.2)]},

    # Vector / animal (arbovirus)
    "JE_PCR_mosquito": {"sensitivity": 0.95, "specificity": 0.98, "cost": 2, "days": 5, "inconclusive_rate": 0.12},
    "JE_IgG_pig": {"sensitivity": 0.90, "specificity": 0.95, "cost": 1, "days": 4, "inconclusive_rate": 0.08},

    # Leptospirosis human tests
    "LEPTO_ELISA_IGM": {"sensitivity": 0.75, "specificity": 0.94, "cost": 1, "days": 3, "inconclusive_rate": 0.07,
                        "sensitivity_by_days": [(0, 4, 0.35), (5, 10, 0.75), (11, 999, 0.85)]},
    "LEPTO_PCR_BLOOD": {"sensitivity": 0.80, "specificity": 0.98, "cost": 2, "days": 3, "inconclusive_rate": 0.06,
                        "sensitivity_by_days": [(0, 5, 0.85), (6, 10, 0.55), (11, 999, 0.3)]},
    "LEPTO_PCR_URINE": {"sensitivity": 0.70, "specificity": 0.98, "cost": 2, "days": 3, "inconclusive_rate": 0.06,
                        "sensitivity_by_days": [(0, 4, 0.3), (5, 10, 0.65), (11, 999, 0.8)]},
    "LEPTO_MAT": {"sensitivity": 0.85, "specificity": 0.99, "cost": 3, "days": 4, "inconclusive_rate": 0.08,
                  "sensitivity_by_days": [(0, 7, 0.2), (8, 999, 0.9)]},

    # Environmental / animal (lepto)
    "LEPTO_ENV_WATER_PCR": {"sensitivity": 0.65, "specificity": 0.9, "cost": 1, "days": 4, "inconclusive_rate": 0.12},
    "RODENT_PCR": {"sensitivity": 0.8, "specificity": 0.9, "cost": 2, "days": 4, "inconclusive_rate": 0.1},

    # Differential / rule-out
    "MALARIA_RDT": {"sensitivity": 0.95, "specificity": 0.95, "cost": 1, "days": 1, "inconclusive_rate": 0.02, "min_ready_day": 1},
    "DENGUE_NS1": {"sensitivity": 0.8, "specificity": 0.95, "cost": 1, "days": 2, "inconclusive_rate": 0.05, "min_ready_day": 2},
    "BACTERIAL_MENINGITIS_CSF": {"sensitivity": 0.85, "specificity": 0.98, "cost": 2, "days": 2, "inconclusive_rate": 0.08, "min_ready_day": 2},

    # Aliases (UI-friendly labels that map to canonical tests)
    "JE_Ab_pig": {"alias_for": "JE_IgG_pig"},
    "JE_PCR_mosquito_pool": {"alias_for": "JE_PCR_mosquito"},
}

def _resolve_lab_test(test_name: str) -> Tuple[str, Dict[str, Any]]:
    """Return (canonical_test_name, params) resolving aliases."""
    if not test_name:
        return test_name, {}
    params = LAB_TESTS.get(test_name, {}) or {}
    if isinstance(params, dict) and params.get("alias_for"):
        canonical = str(params["alias_for"])
        return canonical, (LAB_TESTS.get(canonical, {}) or {})
    return test_name, params

def _resolve_sensitivity_by_day(test_params: Dict[str, Any], days_since_onset: Optional[int]) -> float:
    base = float(test_params.get("sensitivity", 0.8))
    if days_since_onset is None:
        return base
    for start, end, sens in test_params.get("sensitivity_by_days", []):
        if int(start) <= days_since_onset <= int(end):
            return float(sens)
    return base


def process_lab_order(order, lab_samples_truth, random_seed=None):
    """Create a lab order record with realistic delay + imperfect tests.

    This function is intentionally **non-interactive**:
    - It computes the hidden final result immediately (using truth + Se/Sp + an inconclusive rate),
      but returns it as **PENDING** until the simulated day reaches ready_day.
    - This allows the UI to show a queue of pending tests without re-calling the LLM or
      doing per-row generation.

    Expected order keys (extras are ignored):
        sample_type: str (e.g., 'human_CSF')
        village_id: str (e.g., 'V1')
        test: str (e.g., 'JE_IgM_CSF' or alias like 'JE_Ab_pig')
        source_description: str
        placed_day: int (optional; default 1)
        queue_delay_days: int (optional; default 0; used to model backlog)
    """
    if random_seed is not None:
        np.random.seed(int(random_seed))

    placed_day = int(order.get("placed_day", 1) or 1)
    queue_delay = int(order.get("queue_delay_days", 0) or 0)
    patient_id = order.get("patient_id")
    onset_date = order.get("onset_date")
    days_since_onset = order.get("days_since_onset")
    if days_since_onset is None and onset_date:
        try:
            onset_dt = pd.to_datetime(onset_date)
            collection_dt = pd.to_datetime(order.get("collection_date")) if order.get("collection_date") else None
            if collection_dt is not None:
                days_since_onset = max(0, (collection_dt - onset_dt).days)
        except Exception:
            days_since_onset = None

    canonical_test, test_params = _resolve_lab_test(order.get("test", ""))
    if not test_params:
        test_params = {"sensitivity": 0.80, "specificity": 0.95, "cost": 1, "days": 3, "inconclusive_rate": 0.10}

    # Truth linkage (village + sample type)
    matching = lab_samples_truth[
        (lab_samples_truth["sample_type"] == order.get("sample_type")) &
        (lab_samples_truth["linked_village_id"] == order.get("village_id"))
    ]

    if len(matching) > 0:
        truth_col = None
        for col in ["true_JEV_positive", "true_lepto_positive"]:
            if col in matching.columns:
                truth_col = col
                break
        true_positive = bool(matching.iloc[0][truth_col]) if truth_col else False
    else:
        # Default based on sample type + village
        if order.get("village_id") in ["V1", "V2"]:
            true_positive = order.get("sample_type") in [
                "human_CSF", "human_serum", "pig_serum", "mosquito_pool",
                "blood", "urine", "environmental_water", "rodent_kidney", "animal_serum"
            ]
        else:
            true_positive = False

    # Apply test performance (time since onset dependent)
    sens = _resolve_sensitivity_by_day(test_params, None if days_since_onset is None else int(days_since_onset))
    spec = float(test_params.get("specificity", 0.95))
    if true_positive:
        result_positive = np.random.random() < sens
    else:
        result_positive = np.random.random() > spec

    base_result = "POSITIVE" if result_positive else "NEGATIVE"

    # Inconclusive / QNS / contamination
    inconc = float(test_params.get("inconclusive_rate", 0.10))
    qns_rate = float(test_params.get("qns_rate", 0.0))
    contaminated = bool(order.get("contaminated", False))
    volume_ok = bool(order.get("volume_ok", True))
    if str(order.get("sample_type", "")).lower() in {"mosquito_pool", "pig_serum"}:
        inconc = min(0.25, inconc + 0.05)
    if contaminated:
        final_result = "CONTAMINATED"
    elif not volume_ok and np.random.random() < max(0.4, qns_rate):
        final_result = "QNS"
    elif np.random.random() < inconc:
        final_result = "INCONCLUSIVE"
    else:
        final_result = base_result

    days_to_result = int(test_params.get("days", 3) or 3)
    # Inclusive day counting: a 3-day test ordered on Day 2 returns on Day 4 (2 + 3 - 1)
    min_ready_day = int(test_params.get("min_ready_day", 3) or 0)
    ready_day = placed_day + max(days_to_result - 1, 0) + queue_delay
    if min_ready_day:
        ready_day = max(ready_day, min_ready_day)

    return {
        "sample_id": f"LAB-{np.random.randint(1000, 9999)}",
        "sample_type": order.get("sample_type"),
        "village_id": order.get("village_id"),
        "test": canonical_test,
        "test_requested": order.get("test"),
        "source_description": order.get("source_description", "Unspecified source"),
        "patient_id": patient_id,
        "onset_date": onset_date,
        "days_since_onset": days_since_onset,
        "placed_day": placed_day,
        "ready_day": int(ready_day),
        "result": "PENDING",
        "final_result_hidden": final_result,   # not shown until ready_day
        "true_status_hidden": bool(true_positive),  # not shown to trainees
        "cost": int(test_params.get("cost", 1) or 1),
        "days_to_result": days_to_result,
        "queue_delay_days": queue_delay,
    }
# ============================================================================
# CONSEQUENCE ENGINE
# ============================================================================


def evaluate_interventions(decisions, interview_history):
    """Consequence engine with legible 'because' links and light counterfactuals.

    Backwards compatible with the earlier signature, but can consume additional
    context if provided inside `decisions`:

        decisions['_decision_log']           -> list of decision events
        decisions['_lab_orders']             -> list of lab order records (pending/final)
        decisions['_environment_findings']   -> list of environmental inspections/findings

    Returns:
        {status, narrative, score, max_score, new_cases, outcomes, because, counterfactuals}
    """
    decision_log = decisions.get("_decision_log", []) or []
    lab_orders = decisions.get("_lab_orders", decisions.get("lab_orders", [])) or []
    env_findings = decisions.get("_environment_findings", []) or []

    # Helper: first day a named event occurred
    def first_day(event_type: str) -> Optional[int]:
        for ev in decision_log:
            day_val = ev.get("game_day", ev.get("day"))
            if ev.get("type") == event_type and day_val is not None:
                try:
                    return int(day_val)
                except Exception:
                    return None
        return None

    # Helper: check if any event contains keyword
    def any_note_contains(kw: str) -> bool:
        kw = kw.lower()
        for ev in decision_log:
            txt = json.dumps(ev, default=str).lower()
            if kw in txt:
                return True
        return False

    score = 0
    outcomes = []
    because = []
    counterfactuals = []

    # -------------------------
    # Diagnosis (scenario-specific)
    # -------------------------
    scenario_id = decisions.get("scenario_id")
    scenario_config = decisions.get("scenario_config") or (load_scenario_config(scenario_id) if scenario_id else {})
    scoring_cfg = scenario_config.get("scoring", {}) if scenario_config else {}
    diagnosis_synonyms = [s.lower() for s in scoring_cfg.get("diagnosis_synonyms", [])]
    disease_name = scenario_config.get("disease_name", "the target disease")

    diagnosis = (decisions.get("final_diagnosis") or "").strip()
    if diagnosis and diagnosis.lower() in diagnosis_synonyms:
        score += 25
        outcomes.append(f"✅ Correct diagnosis: {disease_name}")
    elif diagnosis:
        score -= 10
        outcomes.append(f"❌ Incorrect diagnosis: {diagnosis}")
        counterfactuals.append(
            f"If {disease_name} had been suspected earlier, you could have prioritized scenario-appropriate sampling and control messaging sooner."
        )
    else:
        score -= 5
        outcomes.append("⚠️ No final diagnosis recorded")

    # -------------------------
    # One Health engagement (via interviews and/or field findings)
    # -------------------------
    one_health_contacts = set(scenario_config.get("one_health_contacts", []))
    if one_health_contacts and one_health_contacts.intersection(set((interview_history or {}).keys())):
        score += 10
        outcomes.append("✅ Consulted One Health counterpart")
        because.append("Because you engaged One Health partners, your team integrated animal/environmental signals earlier.")
    else:
        outcomes.append("⚠️ Veterinary perspective not documented")

    if "mr_osei" in (interview_history or {}):
        score += 6
        outcomes.append("✅ Environmental assessment consulted")
    if env_findings:
        score += 4
        outcomes.append("✅ Completed at least one environmental site inspection")

    # -------------------------
    # Questionnaire: mapping coverage + signal content
    # -------------------------
    q = decisions.get("questionnaire_xlsform") or {}
    mapped_vars = []
    unmapped_n = 0
    if isinstance(q, dict):
        for qq in (q.get("questions") or []):
            mv = (qq.get("render") or {}).get("mapped_var") or qq.get("mapped_var")
            if mv and mv not in {"unmapped", ""}:
                mapped_vars.append(str(mv))
            else:
                unmapped_n += 1

    # Reward: key domains present (regardless of variable names)
    key_markers = [m.get("key") for m in scenario_config.get("epi_link_fields", []) if m.get("key")]
    key_hits = len({k for k in key_markers if k in set(mapped_vars)})
    if key_hits >= 4:
        score += 15
        outcomes.append("✅ Questionnaire captured key risk-factor domains")
    elif key_hits >= 2:
        score += 8
        outcomes.append("⚡ Questionnaire captured some key domains")
    else:
        score -= 5
        outcomes.append("❌ Questionnaire missed multiple key risk-factor domains")

    if unmapped_n > 0:
        outcomes.append(f"ℹ️ {unmapped_n} unmapped question(s) were synthesized with the scenario generator")
        score += 2

    if decisions.get("data_quality_flag"):
        score -= 5
        outcomes.append("⚠️ Data quality issues in Day 1 line list likely reduced case-finding accuracy")
        because.append("Because your clinic log abstraction had gaps, early case counts were less reliable.")

    q_day = first_day("questionnaire_submitted")
    if q_day is not None and q_day <= 2:
        score += 4
        because.append(f"Because you finalized the questionnaire on Day {q_day}, you had time to collect/clean data before analysis.")
    elif q_day is not None:
        score += 1

    # -------------------------
    # Lab & environment realism: timing + breadth + backlog consequences
    # -------------------------
    def _ready_by_day5(o: Dict[str, Any]) -> bool:
        try:
            return int(o.get("ready_day", 99)) <= 5
        except Exception:
            return False

    # breadth
    sample_types = [str(o.get("sample_type", "")) for o in lab_orders]
    human_samples = {"human_csf", "human_serum", "blood", "urine"}
    one_health_samples = {s.lower() for s in scenario_config.get("one_health_samples", [])}
    has_human = any(s.lower() in human_samples for s in sample_types)
    has_one_health = any(s.lower() in one_health_samples for s in sample_types) if one_health_samples else False

    if has_human and has_one_health:
        score += 12
        outcomes.append("✅ Human + One Health sampling coverage")
    elif has_human:
        score += 4
        outcomes.append("⚠️ Human samples only")
    elif lab_orders:
        score += 1
        outcomes.append("⚠️ Non-human samples only")
    else:
        outcomes.append("⚠️ No lab orders placed")

    # timing: reward early orders that return by Day 5
    if lab_orders:
        early = [o for o in lab_orders if int(o.get("placed_day", 9)) <= 2]
        ready = [o for o in lab_orders if _ready_by_day5(o)]
        if early and ready:
            score += 6
            because.append("Because you placed key lab orders early, at least some results returned within the exercise timeframe.")
        elif early:
            score += 3
        else:
            outcomes.append("⚠️ Lab ordering started late (turnaround limited what you learned in time)")
            counterfactuals.append("If samples had been sent earlier, you would have had confirmatory evidence before final recommendations.")

        # backlog penalty if queue_delay used
        if any(int(o.get("queue_delay_days", 0) or 0) > 0 for o in lab_orders):
            score -= 2
            outcomes.append("⚠️ Lab backlog delayed some results (resource/throughput realism)")

    # -------------------------
    # Analysis completion (Day 3)
    # -------------------------
    analysis_day = first_day("analysis_confirmed")
    if analysis_day is not None:
        score += 4
        because.append(f"Because you completed analysis on Day {analysis_day}, you could justify interventions with data rather than hunches.")
    else:
        outcomes.append("⚠️ Analysis completion not documented")

    # -------------------------
    # Recommendations: content + timing
    # -------------------------
    recommendations_text = " ".join(decisions.get("recommendations", []) or []).lower()

    rec_scores = {
        "vaccination": any(w in recommendations_text for w in ["vaccin", "immuniz"]),
        "vector_control": any(w in recommendations_text for w in ["bed net", "bednet", "mosquito net", "larvicid", "spray", "vector"]),
        "animal_management": any(w in recommendations_text for w in ["pig", "livestock", "rodent", "rat control", "animal pen"]),
        "water_sanitation": any(w in recommendations_text for w in ["chlorin", "borehole", "water treatment", "boil water"]),
        "surveillance": any(w in recommendations_text for w in ["surveill", "monitor", "reporting"]),
        "education": any(w in recommendations_text for w in ["educat", "awareness", "risk communication", "ppe"]),
    }
    recs_count = sum(rec_scores.values())
    if recs_count >= 4:
        score += 18
        outcomes.append("✅ Comprehensive intervention package")
    elif recs_count >= 2:
        score += 10
        outcomes.append("⚡ Partial interventions recommended")
    elif recommendations_text:
        score -= 8
        outcomes.append("❌ Weak interventions")
    else:
        score -= 5
        outcomes.append("⚠️ No recommendations recorded")

    # Timing of final briefing
    rec_day = first_day("recommendations_submitted") or 5

    if rec_scores["vaccination"] and rec_day <= 4:
        score += 4
    if rec_scores["vaccination"] and rec_day == 5:
        counterfactuals.append("Earlier preventive messaging would likely reduce exposure risk.")

    avoid_terms = scoring_cfg.get("avoid_interventions", [])
    if avoid_terms and any(term in recommendations_text for term in avoid_terms):
        score -= 4
        outcomes.append("⚠️ Some recommendations were not aligned with the suspected transmission route")

    # -------------------------
    # Convert score → projected new cases (simple outcome model)
    # -------------------------
    base_new_cases = 10
    effect = 0.0

    # Interventions reduce onward risk; earlier action is stronger
    if rec_scores["vaccination"]:
        effect += 0.35 if rec_day <= 4 else 0.2
    if rec_scores["vector_control"]:
        effect += 0.25 if rec_day <= 4 else 0.15
    if rec_scores["animal_management"]:
        effect += 0.15 if rec_day <= 4 else 0.1
    if rec_scores["water_sanitation"]:
        effect += 0.2 if rec_day <= 4 else 0.12

    # Evidence strength boosts effectiveness (better targeting/credibility)
    if key_hits >= 4:
        effect += 0.05
    if has_human and has_one_health and any(_ready_by_day5(o) for o in lab_orders):
        effect += 0.05
    if analysis_day is not None:
        effect += 0.03

    effect = min(max(effect, 0.0), 0.85)
    new_cases = int(round(base_new_cases * (1.0 - effect)))
    if new_cases < 0:
        new_cases = 0

    # -------------------------
    # Status + narrative (legible)
    # -------------------------
    if score >= 70 and new_cases <= 1:
        status = "SUCCESS"
        headline = "**OUTBREAK CONTROLLED**"
    elif score >= 45 and new_cases <= 4:
        status = "PARTIAL SUCCESS"
        headline = "**OUTBREAK PARTIALLY CONTROLLED**"
    else:
        status = "OUTBREAK CONTINUES"
        headline = "**OUTBREAK CONTINUES**"

    # Curate because statements (max 5)
    because = because[:5]

    # Curate counterfactuals (max 3)
    counterfactuals = counterfactuals[:3]

    narrative_lines = [
        headline,
        "",
        "What happened next (simulation):",
        f"- **Projected new cases (next 2 weeks): {new_cases}**",
        "",
        "Key evidence-to-action links:",
    ]
    if because:
        narrative_lines += [f"- {b}" for b in because]
    else:
        narrative_lines.append("- (No decision links recorded; add decision logging to strengthen this view.)")

    if counterfactuals:
        narrative_lines += ["", "Brief counterfactuals (for learning):"] + [f"- {c}" for c in counterfactuals]

    narrative = "\n".join(narrative_lines)

    return {
        "status": status,
        "narrative": narrative,
        "score": int(score),
        "max_score": 100,
        "new_cases": int(new_cases),
        "outcomes": outcomes,
        "because": because,
        "counterfactuals": counterfactuals,
    }
# ============================================================================
# DAY PREREQUISITES
# ============================================================================


# ============================================================================
# PEDAGOGICAL CONTRACT (Phase 1)
# ============================================================================

DAY_SPECS: Dict[int, Dict[str, Any]] = {
    1: {
        "required_outputs": [
            "Working case definition saved",
            "At least one hypothesis documented",
            "At least 2 hypothesis-generating interviews completed",
        ],
        "optional_actions": [
            "Review clinic records for additional cases",
            "Describe cases by person/place/time",
        ],
        "good_enough": [
            "Case definition includes clinical + person + place + time elements (draft is fine)",
            "At least 1 plausible hypothesis stated (can be wrong)",
            "Interviews show purposeful questioning (not just 'tell me everything')",
        ],
        "if_missing": [
            "You cannot advance: downstream steps depend on a case definition and an initial hypothesis.",
        ],
    },
    2: {
        "required_outputs": [
            "Study design selected (case-control or cohort) with a sampling plan",
            "Questionnaire (XLSForm) uploaded and processed",
            "Simulated dataset generated and exported for analysis",
        ],
        "optional_actions": [
            "Document data dictionary / variable list",
            "Note anticipated biases and how you will minimize them",
        ],
        "good_enough": [
            "Study design matches your hypothesis (even if imperfect)",
            "Questionnaire includes core exposure domains (animals, vector, vaccination, environment)",
            "Dataset exports successfully and has usable columns",
        ],
        "if_missing": [
            "You cannot advance: Day 3 assumes you have a dataset to analyze.",
        ],
    },
    3: {
        "required_outputs": [
            "Analysis completed outside the simulation and confirmed in-app",
            "Key results summarized (at least 2–3 sentences or bullets)",
        ],
        "optional_actions": [
            "Upload analysis outputs (optional)",
            "Record key limitations",
        ],
        "good_enough": [
            "You can state the main exposure(s) associated with being a case (direction + rough magnitude)",
        ],
        "if_missing": [
            "You cannot advance: Day 4 decisions should be guided by your analysis.",
        ],
    },
    4: {
        "required_outputs": [
            "At least one lab order placed (with awareness of turnaround time)",
            "At least one environmental action recorded (inspection or vector-related evidence)",
            "Draft intervention ideas recorded (can be preliminary)",
        ],
        "optional_actions": [
            "Order additional tests to rule out differential diagnoses",
            "Re-check case definition and line list for missed cases",
        ],
        "good_enough": [
            "You can explain what each sample/test is meant to confirm or rule out",
            "You can articulate a coherent 'triangulation' story (epi + lab/env)",
        ],
        "if_missing": [
            "You cannot advance: Day 5 briefing requires some evidence trail and a draft plan.",
        ],
    },
    5: {
        "required_outputs": [
            "Final diagnosis stated",
            "Recommendations submitted to MOH director",
        ],
        "optional_actions": [
            "Risk communication plan",
            "Surveillance strengthening plan",
        ],
        "good_enough": [
            "Recommendations are feasible and aligned to the transmission route",
        ],
        "if_missing": [
            "End-of-exercise outcome may be indeterminate.",
        ],
    },
}

def get_day_spec(day: int) -> Dict[str, Any]:
    return DAY_SPECS.get(int(day), {})

# ============================================================================
# DAY PREREQUISITES (gates Day advancement)
# ============================================================================

def check_day_prerequisites(current_day, session_state):
    """Check if prerequisites are met to advance to the next day.

    Returns:
        (can_advance: bool, missing: list[str])
    """
    missing: List[str] = []

    # Helper to safely get values from either dict or streamlit session_state
    def get_val(key, default=None):
        if hasattr(session_state, 'get'):
            return session_state.get(key, default)
        return getattr(session_state, key, default)

    day = int(current_day)

    # Common references
    decisions = get_val("decisions", {}) or {}

    if day == 1:
        if not get_val("case_definition_written", False):
            missing.append("prereq.day1.case_definition")
        if not get_val("hypotheses_documented", False):
            missing.append("prereq.day1.hypothesis")
        interview_history = get_val("interview_history", {}) or {}
        if len(interview_history) < 2:
            missing.append("prereq.day1.interviews")

    elif day == 2:
        if not decisions.get("study_design"):
            missing.append("prereq.day2.study_design")
        else:
            scenario_config = decisions.get("scenario_config") or load_scenario_config(decisions.get("scenario_id")) if decisions.get("scenario_id") else {}
            ok, missing_items = validate_study_design_requirements(decisions, scenario_config) if "validate_study_design_requirements" in globals() else (True, [])
            if not ok:
                missing.append("prereq.day2.study_design")
        if not get_val("questionnaire_submitted", False):
            missing.append("prereq.day2.questionnaire")
        if get_val("generated_dataset", None) is None:
            missing.append("prereq.day2.dataset")

    elif day == 3:
        if not get_val("analysis_confirmed", False):
            missing.append("prereq.day3.analysis")

    elif day == 4:
        # Require at least one lab order (can be pending)
        lab_orders = get_val("lab_orders", []) or []
        if len(lab_orders) < 1:
            missing.append("prereq.day4.lab_order")

        env_findings = get_val("environment_findings", []) or []
        if len(env_findings) < 1:
            missing.append("prereq.day4.environment")

        draft = decisions.get("draft_interventions") or []
        if not draft:
            missing.append("prereq.day4.draft_interventions")

    return (len(missing) == 0), missing


def validate_study_design_requirements(decisions: Dict[str, Any], scenario_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate that study design selection includes justification and sampling frame."""
    missing: List[str] = []
    study_design = decisions.get("study_design", {}) or {}
    if not study_design.get("type"):
        missing.append("study_design")
    if not decisions.get("study_design_justification"):
        missing.append("justification")
    if not decisions.get("study_design_sampling_frame"):
        missing.append("sampling_frame")
    if not decisions.get("study_design_bias_notes"):
        missing.append("bias_notes")

    recommended = scenario_config.get("study_design", {}).get("recommended")
    if recommended and study_design.get("type") and study_design.get("type") != recommended:
        missing.append("recommended_design_mismatch")

    return len(missing) == 0, missing


# ============================================================================
# GAME STATE MANAGEMENT
# ============================================================================

def init_game_state(session_state):
    """
    Initialize game state for the Serious Mode opening.

    Game states:
    - 'INTRO': Dr. Tran phone call overlay
    - 'DASHBOARD': Main map view with restricted locations
    - 'HOSPITAL': Specific hospital view

    Args:
        session_state: Streamlit session state object
    """
    if not hasattr(session_state, 'game_state'):
        session_state.game_state = 'INTRO'

    if not hasattr(session_state, 'locations_unlocked'):
        # On Day 1, only District Hospital is unlocked
        session_state.locations_unlocked = ['District Hospital']

    if not hasattr(session_state, 'notebook_content'):
        session_state.notebook_content = []


def is_location_unlocked(location_name: str, session_state) -> bool:
    """
    Check if a location is unlocked for the player.

    Args:
        location_name: Name of the location (e.g., "District Hospital", "Nalu Village")
        session_state: Streamlit session state object

    Returns:
        True if location is unlocked, False otherwise
    """
    if not hasattr(session_state, 'locations_unlocked'):
        init_game_state(session_state)

    return location_name in session_state.locations_unlocked


def unlock_location(location_name: str, session_state):
    """
    Unlock a location for the player.

    Args:
        location_name: Name of the location to unlock
        session_state: Streamlit session state object
    """
    if not hasattr(session_state, 'locations_unlocked'):
        init_game_state(session_state)

    if location_name not in session_state.locations_unlocked:
        session_state.locations_unlocked.append(location_name)


def set_game_state(state: str, session_state):
    """
    Set the current game state.

    Args:
        state: One of 'INTRO', 'DASHBOARD', 'HOSPITAL'
        session_state: Streamlit session state object
    """
    valid_states = ['INTRO', 'DASHBOARD', 'HOSPITAL']
    if state not in valid_states:
        raise ValueError(f"Invalid game state: {state}. Must be one of {valid_states}")

    session_state.game_state = state


# =======================
# DISTRICT HOSPITAL LOGIC
# =======================

def generate_ward_registry(num_days: int = 30, random_seed: int = 42) -> pd.DataFrame:
    """
    Generate a realistic 30-day ward registry with 60 admissions.

    Signal: 9 entries with neuro/fever complaints:
        - 5 "False Alarms" (Malaria, Trauma, Dysentery)
        - 4 "Hidden" JES cases (Fever + Altered Mental Status)

    Noise: 51 standard hospital burden cases

    Args:
        num_days: Number of days to generate (default 30)
        random_seed: Random seed for reproducibility

    Returns:
        DataFrame with ward registry entries
    """
    import random
    import datetime

    random.seed(random_seed)
    np.random.seed(random_seed)

    # Define the end date (today) and start date
    end_date = datetime.date(2025, 6, 12)  # Day 1 of investigation
    start_date = end_date - datetime.timedelta(days=num_days - 1)

    # The 2 known cases (already in medical records)
    known_case_ids = ['WARD-001', 'WARD-002']

    # The 5 False Alarm cases
    false_alarms = [
        {'id': 'WARD-017', 'age': '8y', 'sex': 'M', 'complaint': 'Fever, chills, sweating', 'diagnosis': 'Malaria - Positive smear', 'outcome': 'Recovered', 'is_signal': True, 'is_je': False},
        {'id': 'WARD-023', 'age': '12y', 'sex': 'F', 'complaint': 'High fever, rigors', 'diagnosis': 'Malaria - Positive RDT', 'outcome': 'Recovered', 'is_signal': True, 'is_je': False},
        {'id': 'WARD-031', 'age': '34y', 'sex': 'M', 'complaint': 'Leg pain, swelling', 'diagnosis': 'Fracture - Tibia (motorbike)', 'outcome': 'Recovered', 'is_signal': True, 'is_je': False},
        {'id': 'WARD-042', 'age': '4y', 'sex': 'F', 'complaint': 'Bloody diarrhea, abdominal pain', 'diagnosis': 'Dysentery', 'outcome': 'Recovered', 'is_signal': True, 'is_je': False},
        {'id': 'WARD-051', 'age': '6y', 'sex': 'M', 'complaint': 'Watery diarrhea, fever', 'diagnosis': 'Acute gastroenteritis', 'outcome': 'Recovered', 'is_signal': True, 'is_je': False},
    ]

    # The 4 Hidden JES cases
    hidden_jes = [
        {'id': 'WARD-013', 'age': '5y', 'sex': 'F', 'complaint': 'Fever, altered mental status, stiff neck', 'diagnosis': 'Fever - under observation', 'outcome': 'Admitted', 'is_signal': True, 'is_je': True},
        {'id': 'WARD-028', 'age': '7y', 'sex': 'M', 'complaint': 'High fever, confusion, headache', 'diagnosis': 'Fever - cause unknown', 'outcome': 'Recovered', 'is_signal': True, 'is_je': True},
        {'id': 'WARD-037', 'age': '6y', 'sex': 'F', 'complaint': 'Fever, drowsiness, vomiting', 'diagnosis': 'Febrile illness - unspecified', 'outcome': 'Recovered', 'is_signal': True, 'is_je': True},
        {'id': 'WARD-046', 'age': '9y', 'sex': 'M', 'complaint': 'Fever, lethargy, neck stiffness', 'diagnosis': 'Fever - neurological signs', 'outcome': 'Admitted', 'is_signal': True, 'is_je': True},
    ]

    # Noise cases (standard hospital burden)
    noise_templates = [
        ('Pneumonia', 'Cough, fever, difficulty breathing', 'Pneumonia', 'Recovered'),
        ('Pneumonia', 'Chest pain, productive cough', 'Pneumonia', 'Recovered'),
        ('Birth', 'Labor pains', 'Normal vaginal delivery', 'Discharged'),
        ('Birth', 'Contractions', 'Cesarean section', 'Discharged'),
        ('Injury', 'Laceration - right arm', 'Wound repair', 'Recovered'),
        ('Injury', 'Burn - hot water', 'Burn treatment', 'Recovered'),
        ('Malaria', 'Fever, headache', 'Malaria - treated', 'Recovered'),
        ('Malaria', 'Chills, body aches', 'Malaria - treated', 'Recovered'),
        ('Diarrhea', 'Watery diarrhea', 'Acute gastroenteritis', 'Recovered'),
        ('Diarrhea', 'Vomiting, diarrhea', 'Dehydration', 'Recovered'),
        ('Asthma', 'Wheezing, shortness of breath', 'Asthma exacerbation', 'Recovered'),
        ('Diabetes', 'High blood sugar', 'Diabetes management', 'Discharged'),
        ('Hypertension', 'Severe headache, high BP', 'Hypertensive crisis', 'Recovered'),
        ('Appendicitis', 'Right lower abdominal pain', 'Appendectomy', 'Recovered'),
        ('UTI', 'Painful urination', 'Urinary tract infection', 'Recovered'),
    ]

    # Build the registry
    registry = []

    # Add known cases
    for idx, case_id in enumerate(known_case_ids):
        admission_date = start_date + datetime.timedelta(days=random.randint(0, num_days - 5))
        registry.append({
            'Patient_ID': case_id,
            'Admission_Date': admission_date.strftime('%Y-%m-%d'),
            'Age': ['6y', '7y'][idx],
            'Sex': ['M', 'F'][idx],
            'Chief_Complaint': 'High fever, seizures, altered consciousness',
            'Diagnosis': 'Acute Encephalitis Syndrome',
            'Outcome': ['Admitted', 'Deceased'][idx],
            'is_signal': True,
            'is_je': True
        })

    # Add false alarms
    for case in false_alarms:
        admission_date = start_date + datetime.timedelta(days=random.randint(0, num_days - 1))
        registry.append({
            'Patient_ID': case['id'],
            'Admission_Date': admission_date.strftime('%Y-%m-%d'),
            'Age': case['age'],
            'Sex': case['sex'],
            'Chief_Complaint': case['complaint'],
            'Diagnosis': case['diagnosis'],
            'Outcome': case['outcome'],
            'is_signal': case['is_signal'],
            'is_je': case['is_je']
        })

    # Add hidden JES cases
    for case in hidden_jes:
        admission_date = start_date + datetime.timedelta(days=random.randint(0, num_days - 1))
        registry.append({
            'Patient_ID': case['id'],
            'Admission_Date': admission_date.strftime('%Y-%m-%d'),
            'Age': case['age'],
            'Sex': case['sex'],
            'Chief_Complaint': case['complaint'],
            'Diagnosis': case['diagnosis'],
            'Outcome': case['outcome'],
            'is_signal': case['is_signal'],
            'is_je': case['is_je']
        })

    # Add noise cases to reach ~60 total
    current_count = len(registry)
    needed_noise = 60 - current_count

    patient_id_counter = 60
    for i in range(needed_noise):
        template = random.choice(noise_templates)
        category, complaint, diagnosis, outcome = template

        # Generate random demographics
        age = f"{random.randint(1, 65)}y" if random.random() > 0.2 else f"{random.randint(1, 24)}m"
        sex = random.choice(['M', 'F'])

        admission_date = start_date + datetime.timedelta(days=random.randint(0, num_days - 1))

        registry.append({
            'Patient_ID': f'WARD-{patient_id_counter:03d}',
            'Admission_Date': admission_date.strftime('%Y-%m-%d'),
            'Age': age,
            'Sex': sex,
            'Chief_Complaint': complaint,
            'Diagnosis': diagnosis,
            'Outcome': outcome,
            'is_signal': False,
            'is_je': False
        })
        patient_id_counter += 1

    # Convert to DataFrame and sort by date
    df = pd.DataFrame(registry)
    df = df.sort_values('Admission_Date', ascending=False).reset_index(drop=True)

    return df


def get_paper_chart_text(patient_id: str) -> str:
    """
    Generate realistic paper chart text for a patient.

    CRITICAL: NO RISK FACTORS mentioned (no pigs, rice fields, mosquitoes, nets).
    Only clinical data and demographics.

    Args:
        patient_id: Patient ID (e.g., 'WARD-001', 'WARD-013')

    Returns:
        Formatted chart text in handwritten style
    """
    # Define chart templates
    charts = {
        # The 2 known JES cases
        'WARD-001': {
            'name': 'Kwame A.',
            'age': '6y',
            'sex': 'M',
            'village': 'Nalu',
            'date': 'June 3, 2025',
            'temp': '39.5°C',
            'hr': '128',
            'symptoms': 'High fever × 2d, multiple seizures, confusion',
            'exam': 'Neck stiffness +, Brudzinski sign +, GCS 11/15',
            'labs': 'WBC 18,200 (elevated), CSF: clear, lymphocytes 45',
            'diagnosis': 'Acute viral encephalitis - presumed',
            'notes': 'Started on IV fluids, diazepam for seizures. Monitor closely.'
        },
        'WARD-002': {
            'name': 'Esi M.',
            'age': '7y',
            'sex': 'F',
            'village': 'Nalu',
            'date': 'June 9, 2025',
            'temp': '40.1°C',
            'hr': '145',
            'symptoms': 'Fever × 3d, severe headache, vomiting, now unresponsive',
            'exam': 'GCS 6/15, pupils sluggish, decorticate posturing',
            'labs': 'WBC 16,400, CSF: protein elevated, glucose normal',
            'diagnosis': 'Severe encephalitis with raised ICP',
            'notes': 'Critical condition. Family at bedside. Supportive care only.'
        },

        # The 5 False Alarms
        'WARD-017': {
            'name': 'John K.',
            'age': '8y',
            'sex': 'M',
            'village': 'Kabwe',
            'date': 'May 25, 2025',
            'temp': '38.9°C',
            'hr': '115',
            'symptoms': 'Fever × 2d, chills, sweating episodes',
            'exam': 'Alert, oriented. Spleen palpable. No neck stiffness.',
            'labs': 'Malaria smear: POSITIVE for P. falciparum',
            'diagnosis': 'Uncomplicated malaria',
            'notes': 'Started ACT. Improving on Day 2.'
        },
        'WARD-023': {
            'name': 'Grace N.',
            'age': '12y',
            'sex': 'F',
            'village': 'Nalu',
            'date': 'May 30, 2025',
            'temp': '39.2°C',
            'hr': '108',
            'symptoms': 'High fever, rigors, body aches',
            'exam': 'Conscious, mild hepatomegaly. Neuro: normal',
            'labs': 'Malaria RDT: POSITIVE',
            'diagnosis': 'Malaria',
            'notes': 'ACT given. Discharged Day 3.'
        },
        'WARD-031': {
            'name': 'Peter O.',
            'age': '34y',
            'sex': 'M',
            'village': 'Mining Area',
            'date': 'June 2, 2025',
            'temp': '36.8°C',
            'hr': '88',
            'symptoms': 'Right leg pain, swelling after motorbike accident',
            'exam': 'AFEBRILE. Alert. Obvious deformity right tibia.',
            'labs': 'X-ray: Tibial fracture - mid-shaft',
            'diagnosis': 'Closed tibial fracture',
            'notes': 'Ortho consult. Cast applied. Pain controlled.'
        },
        'WARD-042': {
            'name': 'Sarah L.',
            'age': '4y',
            'sex': 'F',
            'village': 'Kabwe',
            'date': 'June 7, 2025',
            'temp': '37.8°C',
            'hr': '102',
            'symptoms': 'Bloody diarrhea × 3d, cramping abdominal pain',
            'exam': 'Mild dehydration. Abdomen tender. NO fever. Neuro: intact',
            'labs': 'Stool: WBC ++, RBC +++',
            'diagnosis': 'Dysentery - bacterial',
            'notes': 'IV fluids, ciprofloxacin. Improving.'
        },
        'WARD-051': {
            'name': 'David M.',
            'age': '6y',
            'sex': 'M',
            'village': 'Nalu',
            'date': 'June 10, 2025',
            'temp': '37.9°C',
            'hr': '98',
            'symptoms': 'Watery diarrhea × 2d, low-grade fever, vomiting',
            'exam': 'Mildly dehydrated. Alert. Abdomen soft. Neuro: normal',
            'labs': 'Stool: watery, no blood',
            'diagnosis': 'Acute gastroenteritis',
            'notes': 'ORS, zinc. Discharged next day.'
        },

        # The 4 Hidden JES cases
        'WARD-013': {
            'name': 'Fatima H.',
            'age': '5y',
            'sex': 'F',
            'village': 'Nalu',
            'date': 'May 28, 2025',
            'temp': '39.1°C',
            'hr': '125',
            'symptoms': 'Fever × 2d, stiff neck, altered mental status',
            'exam': 'Drowsy but arousable. Neck stiffness +. Kernig sign +',
            'labs': 'WBC 15,200. CSF: clear, mild pleocytosis',
            'diagnosis': 'Fever - under observation',
            'notes': 'Infection likely. Started broad-spectrum ABx. Improving slowly.'
        },
        'WARD-028': {
            'name': 'Michael T.',
            'age': '7y',
            'sex': 'M',
            'village': 'Kabwe',
            'date': 'June 1, 2025',
            'temp': '39.8°C',
            'hr': '132',
            'symptoms': 'High fever, confusion, severe headache',
            'exam': 'Confused, agitated. Fundi normal. No focal deficits',
            'labs': 'WBC 17,100. Malaria: negative',
            'diagnosis': 'Fever - cause unknown',
            'notes': 'Treated empirically. Fever resolved Day 4. Discharged.'
        },
        'WARD-037': {
            'name': 'Rose K.',
            'age': '6y',
            'sex': 'F',
            'village': 'Nalu',
            'date': 'June 5, 2025',
            'temp': '38.7°C',
            'hr': '118',
            'symptoms': 'Fever, drowsiness, vomiting × 3 episodes',
            'exam': 'Lethargic. Responds to voice. Neck supple. Neuro: no clear deficit',
            'labs': 'WBC 14,800. Blood culture: pending',
            'diagnosis': 'Febrile illness - unspecified',
            'notes': 'Supportive care. Gradual improvement. Discharged Day 5.'
        },
        'WARD-046': {
            'name': 'James P.',
            'age': '9y',
            'sex': 'M',
            'village': 'Kabwe',
            'date': 'June 8, 2025',
            'temp': '39.4°C',
            'hr': '128',
            'symptoms': 'Fever, lethargy, neck stiffness, photophobia',
            'exam': 'Drowsy. Neck stiff. Brudzinski +. GCS 13/15',
            'labs': 'WBC 16,900. CSF: lymphocytic pleocytosis',
            'diagnosis': 'Fever - neurological signs',
            'notes': 'Likely viral CNS infection. Supportive management.'
        },
    }

    # Get chart data
    chart = charts.get(patient_id)

    if not chart:
        return f"Chart for {patient_id} not available."

    # Format in realistic handwritten style
    formatted = f"""
╔══════════════════════════════════════════════════════════════╗
║  DISTRICT HOSPITAL - MEDICAL CHART                          ║
╚══════════════════════════════════════════════════════════════╝

Patient ID: {patient_id}
Name: {chart['name']}
Age/Sex: {chart['age']} / {chart['sex']}
Village: {chart['village']}
Admission Date: {chart['date']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VITAL SIGNS:
  Temperature: {chart['temp']}
  Heart Rate: {chart['hr']} bpm

CHIEF COMPLAINT:
  {chart['symptoms']}

PHYSICAL EXAMINATION:
  {chart['exam']}

LABORATORY:
  {chart['labs']}

DIAGNOSIS:
  {chart['diagnosis']}

CLINICAL NOTES:
  {chart['notes']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Physician: Dr. Somchai / Dr. Niran
    """

    return formatted.strip()


def get_lab_volume_requirements() -> dict:
    """
    Define lab test volume requirements and available sample volumes.

    Returns:
        Dictionary with test requirements and sample volumes
    """
    return {
        'sample_volumes': {
            'Serum': 5.0,  # 5 ml - enough for everything
            'CSF': 0.5,    # 0.5 ml - critical constraint
            'Urine': 10.0  # 10 ml
        },
        'test_requirements': {
            # Basic tests (fast, low volume)
            'CBC': {'volume': 0.5, 'matrix': ['Serum'], 'turnaround': 'Same day'},
            'Malaria_Smear': {'volume': 0.1, 'matrix': ['Serum'], 'turnaround': '2 hours'},
            'Blood_Culture': {'volume': 1.0, 'matrix': ['Serum'], 'turnaround': '3-5 days'},

            # CSF tests
            'CSF_Cell_Count': {'volume': 0.1, 'matrix': ['CSF'], 'turnaround': 'Same day'},
            'CSF_Protein_Glucose': {'volume': 0.1, 'matrix': ['CSF'], 'turnaround': 'Same day'},
            'CSF_Culture': {'volume': 0.2, 'matrix': ['CSF'], 'turnaround': '3-5 days'},

            # Advanced tests (slow, high volume)
            'JE_IgM': {'volume': 0.5, 'matrix': ['Serum', 'CSF'], 'turnaround': 'Day 4'},
            'Nipah_PCR': {'volume': 0.5, 'matrix': ['Serum', 'CSF'], 'turnaround': 'Day 4'},
            'Enterovirus_PCR': {'volume': 0.3, 'matrix': ['Serum', 'CSF'], 'turnaround': 'Day 4'},

            # Urine tests
            'Urinalysis': {'volume': 5.0, 'matrix': ['Urine'], 'turnaround': 'Same day'},
        }
    }


def validate_lab_order(tests: list, matrix: str) -> dict:
    """
    Validate a lab order against volume constraints.

    Args:
        tests: List of test names
        matrix: Sample matrix ('Serum', 'CSF', 'Urine')

    Returns:
        Dictionary with validation results:
            - valid: Boolean
            - total_volume: Required volume
            - available_volume: Available volume
            - message: User message
    """
    requirements = get_lab_volume_requirements()

    available_volume = requirements['sample_volumes'].get(matrix, 0)
    test_reqs = requirements['test_requirements']

    total_required = 0
    invalid_tests = []

    for test in tests:
        if test not in test_reqs:
            invalid_tests.append(test)
            continue

        test_info = test_reqs[test]

        # Check if test is valid for this matrix
        if matrix not in test_info['matrix']:
            invalid_tests.append(f"{test} (not available for {matrix})")
            continue

        total_required += test_info['volume']

    # Build result
    result = {
        'valid': len(invalid_tests) == 0 and total_required <= available_volume,
        'total_volume': total_required,
        'available_volume': available_volume,
        'tests': tests,
        'matrix': matrix
    }

    # Generate message
    if invalid_tests:
        result['message'] = f"❌ Invalid tests: {', '.join(invalid_tests)}"
    elif total_required > available_volume:
        result['message'] = f"⚠️ Order accepted, but insufficient volume ({total_required:.1f}ml required, {available_volume:.1f}ml available). Results will show QNS (Quantity Not Sufficient) on Day 4."
        result['qns'] = True  # Mark as quantity not sufficient
    else:
        result['message'] = f"✅ Order accepted. Required: {total_required:.1f}ml / Available: {available_volume:.1f}ml"
        result['qns'] = False

    return result
