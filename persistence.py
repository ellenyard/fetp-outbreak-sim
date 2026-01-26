"""
Session Persistence Module for FETP Outbreak Simulation
========================================================

This module handles saving and loading game state, allowing users to:
- Save their investigation progress at any point
- Resume from where they left off in a later session
- Export their progress as a portable JSON file

The module converts complex Python objects (DataFrames, sets, nested dicts)
into JSON-compatible formats and back again.

Key concepts:
- Serialization: Converting Python objects to JSON-storable format
- Deserialization: Converting JSON back to Python objects
- Session state: Streamlit's mechanism for storing data between page reruns
"""

import json
import logging
import pandas as pd
from datetime import datetime
from typing import Any, Dict, Tuple

import streamlit as st

# Configure logging for this module
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Version identifier for save file format
# Increment this when making breaking changes to the save format
SAVE_FILE_VERSION = "1.0.0"

# Keys that should NEVER be saved (security-sensitive or regenerated at runtime)
EXCLUDED_KEYS = {
    'truth',           # Large dataset regenerated from CSV files on load
    'facilitator_mode',  # Security flag - should never persist between sessions
}

# Keys that represent the core game state to preserve
# Organized by category for maintainability
PERSISTENT_KEYS = {
    # === Core Game Progression ===
    'current_day',           # Which day of the investigation (1-5)
    'alert_acknowledged',    # Has user seen the initial outbreak alert?
    'current_view',          # Current UI view/screen
    'game_state',            # Overall game state machine position

    # === Player Resources ===
    'budget',                # Remaining investigation budget
    'time_remaining',        # Hours left in current day
    'lab_credits',           # Available lab test credits
    'language',              # User's language preference (en/es/fr/pt)

    # === Locations & NPCs ===
    'locations_unlocked',    # Which map locations are accessible
    'npcs_unlocked',         # Which NPCs can be interviewed
    'npc_state',             # Current state/mood of each NPC
    'current_npc',           # NPC currently being interviewed

    # === Investigation Data ===
    'decisions',             # All player decisions (case definitions, hypotheses, etc.)
    'generated_dataset',     # The working dataset of cases
    'lab_results',           # Results from submitted lab tests
    'lab_orders',            # Pending lab test orders
    'lab_samples_submitted', # Samples that have been sent to lab
    'environment_findings',  # Environmental investigation results

    # === Interview System ===
    'interview_history',     # Full conversation logs with each NPC
    'revealed_clues',        # Clues that NPCs have shared
    'questions_asked_about', # Topics already discussed (prevents repetition)

    # === Progress Tracking Flags ===
    # These boolean flags track tutorial/milestone completion
    'case_definition_written',    # Has user written initial case definition?
    'questionnaire_submitted',    # Has user submitted the questionnaire?
    'descriptive_analysis_done',  # Has user completed descriptive analysis?
    'line_list_viewed',           # Has user viewed the line list?
    'clinic_records_reviewed',    # Has user reviewed clinic records?
    'found_cases_added',          # Has user added found cases?
    'hypotheses_documented',      # Has user documented hypotheses?
    'analysis_confirmed',         # Has user confirmed their analysis?
    'etiology_revealed',          # Has the cause been revealed?
    'one_health_triggered',       # Has One Health approach been triggered?
    'vet_unlocked',               # Is veterinarian NPC available?
    'env_officer_unlocked',       # Is environmental officer NPC available?
    'descriptive_epi_viewed',     # Has user viewed descriptive epi?

    # === Investigation Artifacts ===
    'selected_clinic_cases',      # Cases selected from clinic records
    'case_finding_score',         # Score from case finding activity
    'initial_hypotheses',         # User's initial hypotheses
    'notebook_content',           # Field notebook text content
    'notebook_entries',           # Structured notebook entries
    'unlock_flags',               # Feature unlock tracking
    'advance_missing_tasks',      # Tasks needed before advancing

    # === Case Data ===
    'found_case_individuals',     # Individual case records found
    'found_case_households',      # Household data for cases
    'clinic_records',             # Raw clinic record data

    # === Day 1 Workflow State ===
    'line_list_cols',             # Columns selected for line list
    'my_case_def',                # User's working case definition
    'manual_cases',               # Manually entered cases
    'clinic_line_list',           # Line list from clinic data
    'clinic_abstraction_submitted',  # Has clinic abstraction been done?
    'clinic_abstraction_feedback',   # Feedback on abstraction
    'case_definition_versions',   # History of case definition revisions
    'case_definition_builder',    # Current case definition in progress
    'case_finding_debrief',       # Debrief notes from case finding
    'case_cards_reviewed',        # Which case cards have been seen
    'case_card_labels',           # Labels assigned to case cards
    'medical_chart_reviews',      # Medical chart review status
    'day1_worksheet',             # Day 1 worksheet data
    'day1_lab_brief_viewed',      # Has lab briefing been viewed?
    'day1_lab_brief_notes',       # Notes from lab briefing
    'triangulation_checkpoint',   # Triangulation exercise checkpoint
    'triangulation_completed',    # Has triangulation been completed?

    # === Evidence Board ===
    'evidence_board',             # Visual evidence board state
    'evidence_event_ids',         # IDs of evidence items
}


# =============================================================================
# SERIALIZATION FUNCTIONS
# =============================================================================

def serialize_value(value: Any) -> Any:
    """
    Convert a Python value to a JSON-compatible format.

    This function handles special types that JSON doesn't natively support:
    - pandas DataFrames -> dict with type marker and JSON string
    - Python sets -> dict with type marker and list
    - Nested dicts/lists -> recursively serialized

    Args:
        value: Any Python value to serialize

    Returns:
        A JSON-compatible representation (dict, list, str, int, float, bool, or None)

    Example:
        >>> serialize_value({1, 2, 3})
        {'__type__': 'set', 'data': [1, 2, 3]}
    """
    # None passes through unchanged
    if value is None:
        return None

    # DataFrames: Convert to JSON string with type marker for reconstruction
    if isinstance(value, pd.DataFrame):
        return {
            '__type__': 'DataFrame',
            'data': value.to_json(orient='split', date_format='iso')
        }

    # Sets: Convert to list with type marker (JSON has no set type)
    if isinstance(value, set):
        return {
            '__type__': 'set',
            'data': list(value)
        }

    # Dicts: Recursively serialize all values
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}

    # Lists: Recursively serialize all items
    if isinstance(value, list):
        return [serialize_value(item) for item in value]

    # Primitive types pass through unchanged
    if isinstance(value, (int, float, str, bool)):
        return value

    # Fallback: Convert unknown types to string with a warning
    # This prevents crashes but may lose type information
    logger.warning(f"Converting unknown type {type(value).__name__} to string")
    try:
        return str(value)
    except Exception:
        return None


def deserialize_value(value: Any) -> Any:
    """
    Restore a Python value from its JSON-serialized format.

    Recognizes special type markers (__type__) and reconstructs:
    - DataFrames from JSON strings
    - Sets from lists

    Args:
        value: A JSON-compatible value (possibly with type markers)

    Returns:
        The original Python value with proper types restored

    Example:
        >>> deserialize_value({'__type__': 'set', 'data': [1, 2, 3]})
        {1, 2, 3}
    """
    # None passes through unchanged
    if value is None:
        return None

    # Check for special type markers
    if isinstance(value, dict) and '__type__' in value:
        type_marker = value['__type__']
        data = value['data']

        # Reconstruct DataFrame from JSON string
        if type_marker == 'DataFrame':
            try:
                return pd.read_json(data, orient='split')
            except Exception as e:
                logger.error(f"Failed to deserialize DataFrame: {e}")
                return None

        # Reconstruct set from list
        elif type_marker == 'set':
            return set(data)

    # Dicts: Recursively deserialize all values
    if isinstance(value, dict):
        return {k: deserialize_value(v) for k, v in value.items()}

    # Lists: Recursively deserialize all items
    if isinstance(value, list):
        return [deserialize_value(item) for item in value]

    # Primitive types pass through unchanged
    return value


# =============================================================================
# SESSION STATE FUNCTIONS
# =============================================================================

def serialize_session_state(session_state) -> Dict[str, Any]:
    """
    Create a complete save file dictionary from Streamlit session state.

    Only includes keys listed in PERSISTENT_KEYS to avoid saving:
    - Temporary UI state
    - Security-sensitive data
    - Large regeneratable datasets

    Args:
        session_state: Streamlit's st.session_state object

    Returns:
        Dictionary with version, timestamp, and serialized state
    """
    # Create save file structure with metadata
    serialized = {
        'version': SAVE_FILE_VERSION,
        'timestamp': datetime.now().isoformat(),
        'state': {}
    }

    # Iterate through allowed keys only
    for key in PERSISTENT_KEYS:
        if key in session_state:
            try:
                serialized['state'][key] = serialize_value(session_state[key])
            except Exception as e:
                logger.warning(f"Could not serialize '{key}': {e}")
                serialized['state'][key] = None

    return serialized


def deserialize_session_state(data: Dict[str, Any], session_state) -> bool:
    """
    Load a save file dictionary into Streamlit session state.

    Performs validation before loading:
    - Checks for required version field
    - Warns on version mismatch (but continues)
    - Handles individual key failures gracefully

    Args:
        data: Save file dictionary (from JSON)
        session_state: Streamlit's st.session_state object to populate

    Returns:
        True if load succeeded, False if critical error occurred
    """
    try:
        # Validate: version field required
        if 'version' not in data:
            logger.error("Save file missing version information")
            return False

        # Check version compatibility
        saved_version = data['version']
        if saved_version != SAVE_FILE_VERSION:
            logger.warning(
                f"Save file version ({saved_version}) differs from "
                f"current version ({SAVE_FILE_VERSION}). "
                "Attempting to load anyway."
            )

        # Validate: state field required
        if 'state' not in data:
            logger.error("Save file missing state data")
            return False

        # Load each key, continuing on individual failures
        state_data = data['state']
        for key, value in state_data.items():
            try:
                session_state[key] = deserialize_value(value)
            except Exception as e:
                logger.warning(f"Could not deserialize '{key}': {e}")
                # Continue with remaining keys

        return True

    except Exception as e:
        logger.error(f"Critical error deserializing session state: {e}")
        return False


# =============================================================================
# FILE I/O FUNCTIONS
# =============================================================================

def create_save_file(session_state) -> bytes:
    """
    Generate a downloadable save file from current game state.

    Creates a formatted JSON file that can be:
    - Downloaded via Streamlit's download button
    - Shared with others or backed up
    - Loaded later to resume progress

    Args:
        session_state: Streamlit's st.session_state object

    Returns:
        UTF-8 encoded bytes of the JSON save file
    """
    serialized = serialize_session_state(session_state)
    # Use indent=2 for human-readable output (easier debugging)
    json_str = json.dumps(serialized, indent=2)
    return json_str.encode('utf-8')


def load_save_file(uploaded_file, session_state) -> Tuple[bool, str]:
    """
    Process an uploaded save file and restore game state.

    Handles the complete load workflow:
    1. Read uploaded file content
    2. Parse JSON
    3. Deserialize into session state
    4. Return success/failure with user message

    Args:
        uploaded_file: Streamlit UploadedFile object from file_uploader
        session_state: Streamlit's st.session_state object to populate

    Returns:
        Tuple of (success: bool, message: str for display to user)
    """
    try:
        # Read raw bytes from uploaded file
        content = uploaded_file.read()

        # Parse JSON (may raise JSONDecodeError)
        data = json.loads(content)

        # Attempt to load into session state
        success = deserialize_session_state(data, session_state)

        if success:
            # Extract timestamp for confirmation message
            timestamp = data.get('timestamp', 'unknown time')
            return True, f"Session loaded successfully from {timestamp}"
        else:
            return False, "Failed to load session state. The save file may be corrupted."

    except json.JSONDecodeError as e:
        return False, f"Invalid save file format: {e}"
    except Exception as e:
        return False, f"Error loading save file: {e}"


def get_save_filename(session_state) -> str:
    """
    Generate a descriptive filename for save file downloads.

    Format: fetp_save_day{N}_{YYYYMMDD_HHMMSS}.json

    This makes it easy to:
    - Identify which day the save is from
    - Sort saves chronologically
    - Avoid filename collisions

    Args:
        session_state: Streamlit's st.session_state object

    Returns:
        Suggested filename string
    """
    current_day = session_state.get('current_day', 1)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"fetp_save_day{current_day}_{timestamp}.json"
