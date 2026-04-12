"""View routing for the investigation interface.

Routes session_state.current_view to the appropriate view function.
"""

import streamlit as st

from ui.components import render_view_with_return_button

# View imports
from views.overview import view_overview
from views.case_finding import (
    view_case_finding, view_case_finding_debrief,
    view_day1_lab_brief, view_triangulation_checkpoint,
    view_clinic_register_scan, view_nalu_child_register,
)
from views.descriptive_epi import view_descriptive_epi, view_spot_map
from views.village_profiles import view_village_profiles
from views.medical_records import view_interviews, view_medical_records, view_clinic_log_abstraction
from views.study_design import view_study_design
from views.lab import view_lab_and_environment
from views.outcome import view_interventions_and_outcome
from views.journal import view_investigation_journal
from views.analysis import view_quick_analysis
from views.sitrep import view_sitrep
from views.map import view_travel_map, view_area_visual, view_location


# Views that need a "Return to Map" button
VIEWS_WITH_RETURN_BUTTON = {
    "overview": view_overview,
    "casefinding": view_case_finding,
    "descriptive": view_descriptive_epi,
    "villages": view_village_profiles,
    "interviews": view_interviews,
    "spotmap": view_spot_map,
    "study": view_study_design,
    "lab": view_lab_and_environment,
    "outcome": view_interventions_and_outcome,
    "journal": view_investigation_journal,
    "analysis": view_quick_analysis,
}

# Views rendered directly without return button
VIEWS_DIRECT = {
    "medical_records": view_medical_records,
    "clinic_log_abstraction": view_clinic_log_abstraction,
    "case_finding_debrief": view_case_finding_debrief,
    "day1_lab_brief": view_day1_lab_brief,
    "triangulation_checkpoint": view_triangulation_checkpoint,
    "clinic_register": view_clinic_register_scan,
    "nalu_child_register": view_nalu_child_register,
}


def route_to_view(view: str):
    """Route to the appropriate view based on view name.

    Args:
        view: The view name from session state

    Returns:
        True if the caller should return early (e.g., sitrep blocking view)
    """
    # SITREP is blocking - requires acknowledgment before continuing
    if view == "sitrep":
        view_sitrep()
        return True

    # Map view (default)
    if view == "map" or view is None:
        view_travel_map()
        return False

    # Area view - needs session state check for current_area
    if view == "area":
        area = st.session_state.get("current_area")
        if area:
            view_area_visual(area)
        else:
            view_travel_map()
        return False

    # Location view - needs session state check for current_location
    if view == "location":
        loc_key = st.session_state.get("current_location")
        if loc_key:
            view_location(loc_key)
        else:
            view_travel_map()
        return False

    # Check views that need return button
    if view in VIEWS_WITH_RETURN_BUTTON:
        render_view_with_return_button(VIEWS_WITH_RETURN_BUTTON[view], view)
        return False

    # Check direct views (no return button needed)
    if view in VIEWS_DIRECT:
        VIEWS_DIRECT[view]()
        return False

    # Default fallback to map
    view_travel_map()
    return False
