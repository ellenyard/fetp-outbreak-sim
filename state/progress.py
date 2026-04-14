"""Day task progress tracking.

Provides get_day_tasks() which returns the completion status of each task
for a given day, linking each task to its relevant view for navigation.
"""

import streamlit as st


# Task definitions per day: (id, label, check_fn, view_link, required)
# check_fn takes session_state and returns bool

def _get_val(ss, key, default=None):
    """Safely get a value from session state."""
    if hasattr(ss, 'get'):
        return ss.get(key, default)
    return getattr(ss, key, default)


def _count_real_interviews(ss) -> int:
    """Count NPCs with at least one actual message exchange.

    Empty entries (created when opening the interview panel but not yet
    chatting) should not count toward progress.
    """
    history = _get_val(ss, "interview_history", {}) or {}
    return sum(1 for msgs in history.values() if msgs)


def get_day_tasks(day: int, session_state=None) -> list:
    """Return task dicts for the given day with completion status.

    Each dict has keys:
        id: str — unique task identifier
        label: str — human-readable task description
        done: bool — whether the task is complete
        view_link: str — view name to navigate to
        required: bool — whether the task is required to advance
    """
    ss = session_state or st.session_state
    decisions = _get_val(ss, "decisions", {}) or {}
    tasks = []

    if day == 1:
        tasks = [
            {
                "id": "case_definition",
                "label": "Write a working case definition",
                "done": bool(_get_val(ss, "case_definition_written", False)),
                "view_link": "overview",
                "required": True,
            },
            {
                "id": "hypotheses",
                "label": "Document initial hypotheses",
                "done": bool(_get_val(ss, "hypotheses_documented", False)),
                "view_link": "overview",
                "required": True,
            },
            {
                "id": "interviews",
                "label": "Interview at least 2 NPCs",
                "done": _count_real_interviews(ss) >= 2,
                "view_link": "interviews",
                "required": True,
            },
            {
                "id": "clinic_abstraction",
                "label": "Abstract clinic log entries",
                "done": bool(_get_val(ss, "clinic_abstraction_submitted", False)),
                "view_link": "clinic_log_abstraction",
                "required": False,
            },
            {
                "id": "descriptive_epi",
                "label": "Review descriptive epidemiology",
                "done": bool(_get_val(ss, "descriptive_epi_reviewed", False)),
                "view_link": "descriptive",
                "required": False,
            },
        ]

    elif day == 2:
        tasks = [
            {
                "id": "study_design",
                "label": "Select a study design",
                "done": bool(decisions.get("study_design")),
                "view_link": "study",
                "required": True,
            },
            {
                "id": "questionnaire",
                "label": "Upload and save questionnaire",
                "done": bool(_get_val(ss, "questionnaire_submitted", False)),
                "view_link": "study",
                "required": True,
            },
            {
                "id": "dataset",
                "label": "Generate simulated dataset",
                "done": _get_val(ss, "generated_dataset", None) is not None,
                "view_link": "study",
                "required": True,
            },
        ]

    elif day == 3:
        tasks = [
            {
                "id": "analysis",
                "label": "Complete analysis and summarize results",
                "done": bool(_get_val(ss, "analysis_confirmed", False)),
                "view_link": "descriptive",
                "required": True,
            },
            {
                "id": "additional_interviews",
                "label": "Conduct follow-up interviews",
                "done": _count_real_interviews(ss) >= 4,
                "view_link": "interviews",
                "required": False,
            },
        ]

    elif day == 4:
        tasks = [
            {
                "id": "lab_order",
                "label": "Place at least one lab order",
                "done": len(_get_val(ss, "lab_orders", []) or []) >= 1,
                "view_link": "lab",
                "required": True,
            },
            {
                "id": "environment",
                "label": "Record environmental findings",
                "done": len(_get_val(ss, "environment_findings", []) or []) >= 1,
                "view_link": "lab",
                "required": True,
            },
            {
                "id": "draft_interventions",
                "label": "Draft preliminary interventions",
                "done": bool(decisions.get("draft_interventions")),
                "view_link": "outcome",
                "required": True,
            },
        ]

    elif day == 5:
        tasks = [
            {
                "id": "final_diagnosis",
                "label": "Submit final diagnosis",
                "done": bool(decisions.get("final_diagnosis")),
                "view_link": "outcome",
                "required": True,
            },
            {
                "id": "recommendations",
                "label": "Submit recommendations",
                "done": bool(decisions.get("recommendations")),
                "view_link": "outcome",
                "required": True,
            },
        ]

    return tasks


def get_completion_summary(day: int, session_state=None) -> dict:
    """Return a summary of task completion for the given day.

    Returns dict with keys: total, completed, required_total, required_completed, pct
    """
    tasks = get_day_tasks(day, session_state)
    completed = sum(1 for t in tasks if t["done"])
    total = len(tasks)
    required = [t for t in tasks if t["required"]]
    required_completed = sum(1 for t in required if t["done"])

    return {
        "total": total,
        "completed": completed,
        "required_total": len(required),
        "required_completed": required_completed,
        "pct": int(100 * completed / total) if total > 0 else 100,
    }
