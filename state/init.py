"""Session-state initialisation, autosave, and error-handling decorator.

``init_session_state()`` sets all default keys in ``st.session_state``
so that every downstream module can safely read them without ``KeyError``.

``check_autosave()`` periodically saves session state for recovery.

``handle_errors()`` is a decorator that wraps tab/page rendering
functions with user-friendly error messages.
"""

import logging
import time as _time
from functools import wraps

import streamlit as st
import pandas as pd
from datetime import date

# These are imported at module level so they are available when
# init_session_state() runs.  They are resolved from outbreak_logic
# (via app.py's top-level imports) at import time.
import outbreak_logic as jl

init_game_state = getattr(jl, "init_game_state", None)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error-handling decorator
# ---------------------------------------------------------------------------


def handle_errors(user_message: str = "An error occurred"):
    """Decorator for consistent error handling with user-friendly messages.

    Args:
        user_message: The message to display to users when an unexpected error occurs.

    Usage:
        @handle_errors("Could not generate dataset. Please check your case definition.")
        def generate_study_dataset(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FileNotFoundError as e:
                st.error(f"Required file not found. Please check scenario data is complete.")
                logger.error(f"File not found in {func.__name__}: {e}")
                return None
            except ValueError as e:
                st.error(f"Invalid value: {e}")
                logger.warning(f"Validation error in {func.__name__}: {e}")
                return None
            except KeyError as e:
                st.error(f"Missing data field: {e}")
                logger.warning(f"Key error in {func.__name__}: {e}")
                return None
            except Exception as e:
                st.error(user_message)
                logger.exception(f"Unexpected error in {func.__name__}")
                return None
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

# Late imports to avoid circular dependencies.  These are resolved the
# first time init_session_state() is called rather than at module import.
_init_evidence_board = None
_restore_found_cases_to_truth = None


def _resolve_lazy_imports():
    """Resolve late-bound references that live in app.py (or sibling modules)."""
    global _init_evidence_board, _restore_found_cases_to_truth
    if _init_evidence_board is None:
        # These functions are expected to be monkey-patched or passed in by the
        # main app module.  Fall back to no-ops so the module can be imported
        # and tested independently.
        import sys
        app = sys.modules.get("__main__")
        _init_evidence_board = getattr(app, "init_evidence_board", lambda: None)
        _restore_found_cases_to_truth = getattr(app, "restore_found_cases_to_truth", lambda t, s: None)


def init_session_state():
    _resolve_lazy_imports()

    # Scenario tracking
    if 'current_scenario' not in st.session_state:
        st.session_state.current_scenario = None
    if 'current_scenario_name' not in st.session_state:
        st.session_state.current_scenario_name = None
    if 'current_scenario_type' not in st.session_state:
        st.session_state.current_scenario_type = None

    # Note: truth data is now loaded in main() based on scenario selection

    # Game state initialization (Serious Mode)
    if init_game_state:
        init_game_state(st.session_state)

    # Alert page logic (Day 0)
    st.session_state.setdefault("alert_acknowledged", False)

    if "current_day" not in st.session_state:
        # 1-5 for the investigation days
        st.session_state.current_day = 1

    if "current_view" not in st.session_state:
        # Start on alert screen until acknowledged
        st.session_state.current_view = "alert"

    # Adventure mode: current_location (None = show map, string = show location view)
    st.session_state.setdefault("current_location", None)
    st.session_state.setdefault("current_area", None)  # For area-level navigation

    # If alert is not acknowledged, force the view to "alert"
    if not st.session_state.alert_acknowledged:
        st.session_state.current_view = "alert"
    else:
        # If alert already acknowledged but view is still "alert", move to map
        if st.session_state.current_view == "alert":
            st.session_state.current_view = "map"

    # Resources - budget AND time
    st.session_state.setdefault("budget", 800)
    st.session_state.setdefault("time_remaining", 8)  # hours per day
    st.session_state.setdefault("time_debt", 0)
    st.session_state.setdefault("lab_credits", 20)

    # Language setting
    st.session_state.setdefault("language", "en")

    # Decisions and artifacts
    if "decisions" not in st.session_state:
        st.session_state.decisions = {
            "case_definition": None,
            "case_definition_text": "",
            "case_definition_structured": {},
            "case_definition_history": [],
            "study_design": None,
            "study_design_justification": "",
            "study_design_sampling_frame": "",
            "study_design_bias_notes": "",
            "mapped_columns": [],
            "sample_size": {"cases": 15, "controls_per_case": 2},
            "lab_orders": [],
            "questionnaire_raw": [],
            "questionnaire_file": None,  # For uploaded XLS
            "final_diagnosis": "",
            "recommendations": [],
        }

    st.session_state.setdefault("generated_dataset", None)
    st.session_state.setdefault("lab_results", [])
    st.session_state.setdefault("lab_orders", [])
    st.session_state.setdefault("environment_findings", [])
    st.session_state.setdefault("analysis_confirmed", False)
    st.session_state.setdefault("etiology_revealed", False)
    st.session_state.setdefault("lab_samples_submitted", [])
    st.session_state.setdefault("interview_history", {})
    st.session_state.setdefault("revealed_clues", {})
    st.session_state.setdefault("current_npc", None)
    st.session_state.setdefault("interview_context_location", None)
    st.session_state.setdefault("visited_locations", set())
    st.session_state.setdefault("unlock_flags", {})

    # NPC emotional state & memory summary (per NPC)
    # structure: npc_state[npc_key] = {
    #   "emotion": "neutral" | "cooperative" | "wary" | "annoyed" | "offended",
    #   "interaction_count": int,
    #   "rude_count": int,
    #   "polite_count": int,
    # }
    st.session_state.setdefault("npc_state", {})
    st.session_state.setdefault("npc_trust", {})

    # Flags used for day progression
    st.session_state.setdefault("case_definition_written", False)
    st.session_state.setdefault("questionnaire_submitted", False)
    st.session_state.setdefault("descriptive_analysis_done", False)

    # Track whether user has opened the line list/epi view at least once (for Day 1)
    st.session_state.setdefault("line_list_viewed", False)

    # For messaging when advance-day fails
    st.session_state.setdefault("advance_missing_tasks", [])

    # Initial hypotheses (Day 1)
    st.session_state.setdefault("initial_hypotheses", [])
    st.session_state.setdefault("hypotheses_documented", False)

    # Investigation notebook
    st.session_state.setdefault("notebook_entries", [])

    # NPC unlocking system (One Health)
    # Note: Initial NPCs are now set when scenario is loaded (see main() scenario loading section)
    st.session_state.setdefault("npcs_unlocked", [])
    st.session_state.setdefault("one_health_triggered", False)
    st.session_state.setdefault("vet_unlocked", False)
    st.session_state.setdefault("env_officer_unlocked", False)

    # Achievements and hints
    st.session_state.setdefault("achievements", [])
    st.session_state.setdefault("hints_shown", set())
    st.session_state.setdefault("hints_enabled", True)

    # Case finding state
    st.session_state.setdefault("found_case_individuals", [])
    st.session_state.setdefault("found_case_households", [])

    # Nurse Joy rapport mechanic
    st.session_state.setdefault("nurse_rapport", 0)
    st.session_state.setdefault("nurse_initial_dialogue_shown", False)
    st.session_state.setdefault("nurse_pig_clue_shown", False)
    st.session_state.setdefault("nurse_animal_questions", 0)

    # Medical records navigation
    st.session_state.setdefault("current_chart", None)
    st.session_state.setdefault("unlocked_nalu_charts", [])

    # SITREP and Evidence Board
    st.session_state.setdefault("sitrep_viewed", True)  # Don't show SITREP on Day 1 start
    st.session_state.setdefault("evidence_board", [])
    _init_evidence_board()
    st.session_state.setdefault("questions_asked_about", set())

    # Clinic records and case finding (Day 1)
    st.session_state.setdefault("clinic_records_reviewed", False)
    st.session_state.setdefault("selected_clinic_cases", [])
    st.session_state.setdefault("case_finding_score", None)
    st.session_state.setdefault("found_cases_added", False)

    # Descriptive epidemiology
    st.session_state.setdefault("descriptive_epi_viewed", False)

    # Medical Records workflow (Day 1)
    st.session_state.setdefault("line_list_cols", [])
    st.session_state.setdefault("my_case_def", {})
    st.session_state.setdefault("manual_cases", [])
    st.session_state.setdefault("clinic_line_list", [])
    st.session_state.setdefault("clinic_abstraction_submitted", False)
    st.session_state.setdefault("clinic_abstraction_feedback", {})
    st.session_state.setdefault("case_definition_versions", [])
    st.session_state.setdefault("case_definition_builder", {})
    st.session_state.setdefault("case_finding_debrief", {})
    st.session_state.setdefault("case_cards_reviewed", False)
    st.session_state.setdefault("case_card_labels", {})
    st.session_state.setdefault("medical_chart_reviews", {})
    st.session_state.setdefault("day1_worksheet", {})
    st.session_state.setdefault("day1_lab_brief_viewed", False)
    st.session_state.setdefault("day1_lab_brief_notes", "")
    st.session_state.setdefault("triangulation_checkpoint", {})
    st.session_state.setdefault("triangulation_completed", False)

    if st.session_state.case_definition_builder and "case_def_onset_start" not in st.session_state:
        builder = st.session_state.case_definition_builder
        tw = builder.get("time_window", {})
        st.session_state.case_def_onset_start = pd.to_datetime(tw.get("start", date.today())).date()
        st.session_state.case_def_onset_end = pd.to_datetime(tw.get("end", date.today())).date()
        st.session_state.case_def_villages = builder.get("villages", [])
        st.session_state.case_def_exclusions = builder.get("exclusions", [])
        for tier_key in ["suspected", "probable", "confirmed"]:
            tier = builder.get("tiers", {}).get(tier_key, {})
            st.session_state[f"case_def_{tier_key}_required_any"] = tier.get("required_any", [])
            st.session_state[f"case_def_{tier_key}_optional"] = tier.get("optional_symptoms", [])
            st.session_state[f"case_def_{tier_key}_min_optional"] = tier.get("min_optional", 0)
            st.session_state[f"case_def_{tier_key}_epi_required"] = tier.get("epi_link_required", False)
            st.session_state[f"case_def_{tier_key}_lab_required"] = tier.get("lab_required", False)
            st.session_state[f"case_def_{tier_key}_lab_tests"] = tier.get("lab_tests", [])

    # Restore found cases from session persistence (if loading a saved session)
    # This is needed because truth is regenerated from CSV files, losing found cases
    if st.session_state.get('found_cases_added', False):
        found_individuals = st.session_state.get('found_case_individuals')
        if found_individuals is not None and len(found_individuals) > 0:
            # Check if found cases are already in truth
            truth = st.session_state.truth
            if 'found_via_case_finding' not in truth['individuals'].columns or \
               not truth['individuals']['found_via_case_finding'].any():
                _restore_found_cases_to_truth(truth, st.session_state)


# ---------------------------------------------------------------------------
# Autosave
# ---------------------------------------------------------------------------

AUTOSAVE_INTERVAL = 300  # seconds (5 minutes)


def check_autosave():
    """Periodically serialize session state for crash recovery.

    Called on each app rerun. If enough time has passed since the last
    autosave, creates a lightweight snapshot in session state.
    """
    import persistence

    last_save = st.session_state.get("_last_autosave", 0)
    now = _time.time()

    if now - last_save < AUTOSAVE_INTERVAL:
        return

    # Only autosave if the game has started
    if not st.session_state.get("alert_acknowledged", False):
        return

    try:
        save_data = persistence.create_save_file(st.session_state)
        st.session_state["_autosave_data"] = save_data
        st.session_state["_last_autosave"] = now
    except Exception:
        pass  # Autosave is best-effort


def offer_session_recovery():
    """Show a resume dialog if autosave data exists on startup."""
    autosave = st.session_state.get("_autosave_data")
    if not autosave:
        return False

    if st.session_state.get("_recovery_offered", False):
        return False

    st.session_state["_recovery_offered"] = True

    import persistence
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Resume Previous Session", type="primary", use_container_width=True):
            success, msg = persistence.load_save_file(
                autosave, st.session_state, from_bytes=True
            )
            if success:
                st.success("Session restored!")
                st.rerun()
            else:
                st.error(f"Could not restore: {msg}")
            return True
    with col2:
        if st.button("Start Fresh", use_container_width=True):
            st.session_state["_autosave_data"] = None
            st.rerun()
            return True

    return True
