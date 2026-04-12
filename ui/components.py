"""Reusable UI components for the investigation interface.

Includes area description formatting, hint rendering, and view wrapper utilities.
"""

import streamlit as st

from npc.unlock import get_hospital_records_contact_name
from npc.context import redact_spoilers, investigation_stage


# ── Hint Rules ──
# Conditions are checked in order; only the first matching hint is shown per page load.

HINT_RULES = [
    {
        "id": "hint_first_interview",
        "condition": lambda ss: (
            ss.get("current_day", 1) == 1
            and len(ss.get("interview_history", {})) == 0
            and len(ss.get("visited_locations", set())) >= 1
        ),
        "hint": "You've traveled to a location but haven't interviewed anyone yet. Try talking to the hospital staff -- they often have the earliest observations about case patterns.",
    },
    {
        "id": "hint_one_health",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and not ss.get("vet_unlocked", False)
            and not ss.get("env_officer_unlocked", False)
            and len(ss.get("interview_history", {})) >= 2
        ),
        "hint": "Some outbreaks have animal or environmental connections. Try asking NPCs about livestock, rats, or flooding. A One Health approach could reveal hidden transmission pathways.",
    },
    {
        "id": "hint_case_definition",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and not ss.get("case_definition_written", False)
        ),
        "hint": "You should establish a working case definition before advancing further. Visit the Overview tab to build one using the WHO template.",
    },
    {
        "id": "hint_lab_orders",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and len(ss.get("lab_orders", [])) == 0
        ),
        "hint": "Laboratory confirmation strengthens your investigation. Consider ordering diagnostic tests at the hospital -- early orders mean results arrive sooner.",
    },
    {
        "id": "hint_environment",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 3
            and len(ss.get("environment_findings", [])) == 0
        ),
        "hint": "Environmental sampling can reveal contamination sources. Visit locations to look for water, soil, or animal reservoir testing opportunities.",
    },
    {
        "id": "hint_more_locations",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and len(ss.get("visited_locations", set())) <= 2
        ),
        "hint": "There are more locations to explore on the map. Each location has unique NPCs and data sources. Consider visiting wards with high case counts.",
    },
    {
        "id": "hint_evidence_board",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and len(ss.get("evidence_board", [])) <= 3
        ),
        "hint": "Don't forget to update your Evidence Board with clues you discover. Tracking evidence helps you connect the dots between interviews, lab results, and field observations.",
    },
    {
        "id": "hint_study_design",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 3
            and not ss.get("questionnaire_submitted", False)
        ),
        "hint": "Designing a study and questionnaire will let you systematically collect data from the affected population. Visit the Study Design tool to get started.",
    },
]


def format_area_description(description: str) -> str:
    """Format area description strings with dynamic fields and spoiler redaction."""
    if not description:
        return ""
    contact_name = get_hospital_records_contact_name()
    try:
        formatted = description.format(contact_name=contact_name)
    except (KeyError, ValueError):
        formatted = description.replace("{contact_name}", contact_name)
    return redact_spoilers(formatted, investigation_stage())


def render_view_with_return_button(view_func, view_name: str):
    """Render a view with a Return to Map button at the top."""
    if st.button("Return to Map", key=f"return_from_{view_name}"):
        st.session_state.current_view = "map"
        st.rerun()
    view_func()


def render_hint(hint_text: str):
    """Render a styled 'Radio Message from HQ' hint card."""
    html = f"""
    <div class="hint-card">
        <div class="hint-label">\U0001f4fb Radio Message from Regional HQ</div>
        <div class="hint-text">"{hint_text}"</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def check_and_show_hints():
    """Check hint conditions and display at most one relevant hint."""
    if not st.session_state.get("hints_enabled", True):
        return

    hints_shown = st.session_state.get("hints_shown", set())

    for rule in HINT_RULES:
        hint_id = rule["id"]
        if hint_id in hints_shown:
            continue
        try:
            if rule["condition"](st.session_state):
                render_hint(rule["hint"])
                hints_shown.add(hint_id)
                st.session_state["hints_shown"] = hints_shown
                return  # Show at most one hint per page load
        except Exception:
            pass
