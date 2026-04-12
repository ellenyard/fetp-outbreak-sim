"""Time and budget resource management for the outbreak simulation.

Tracks daily time allowances (hours) and budget (currency), providing
helpers to spend, check, and format resource costs.
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Cost tables
# ---------------------------------------------------------------------------

# Time costs in hours for various activities
TIME_COSTS = {
    # Interviews - primarily time cost
    "interview_initial": 1.0,      # First interview with an NPC
    "interview_followup": 0.5,     # Follow-up questions with same NPC

    # Case finding
    "clinic_records_review": 2.0,  # Reviewing clinic records

    # Data collection
    "questionnaire_development": 1.5,  # Developing questionnaire
    "questionnaire_admin_per_10": 2.0, # Administering questionnaire (per 10 respondents)

    # Analysis
    "descriptive_analysis": 1.0,   # Running descriptive analyses
    "data_cleaning": 1.5,          # Cleaning dataset

    # Lab and environment
    "sample_collection": 1.0,      # Per sample collection trip
    "environmental_inspection": 2.0,  # Site inspection

    # Travel
    "travel_to_village": 0.5,      # Travel time to a village
    "travel_between_villages": 0.5,  # Travel between villages
}

# Budget costs (some activities cost money, not just time)
BUDGET_COSTS = {
    "questionnaire_printing": 50,   # Printing questionnaires
    "lab_sample_human": 25,         # Human sample collection supplies
    "lab_sample_animal": 35,        # Animal sample collection
    "lab_sample_mosquito": 40,      # Mosquito trap setup
    "transport_per_trip": 20,       # Vehicle/fuel costs
}

# ---------------------------------------------------------------------------
# Resource helpers
# ---------------------------------------------------------------------------


def spend_time(hours: float, activity: str = "") -> bool:
    """
    Deduct time from daily allowance.
    Returns True if time was available, False if going into overtime.
    Time can go negative (overtime), but this is tracked and may affect scoring.
    """
    was_positive = st.session_state.time_remaining > 0
    st.session_state.time_remaining -= hours

    if st.session_state.time_remaining < 0:
        # Track overtime/time debt
        st.session_state.time_debt = abs(st.session_state.time_remaining)
        st.session_state.setdefault("overtime_used", 0)
        if was_positive:
            # Just went into overtime
            st.session_state.overtime_used += abs(st.session_state.time_remaining)
        else:
            # Already in overtime, add more
            st.session_state.overtime_used += hours

    # Return True if had time, False if using overtime (still allows action)
    return was_positive


def spend_budget(amount: float, activity: str = "") -> bool:
    """
    Deduct from budget.
    Returns True if successful, False if not enough budget.
    """
    if st.session_state.budget >= amount:
        st.session_state.budget -= amount
        return True
    return False


def check_resources(time_needed: float = 0, budget_needed: float = 0) -> tuple:
    """
    Check if enough resources are available.
    Returns (can_proceed: bool, message: str)
    """
    messages = []
    can_proceed = True

    if time_needed > 0 and st.session_state.time_remaining < time_needed:
        can_proceed = False
        messages.append(f"Not enough time (need {time_needed}h, have {st.session_state.time_remaining}h)")

    if budget_needed > 0 and st.session_state.budget < budget_needed:
        can_proceed = False
        messages.append(f"Not enough budget (need ${budget_needed}, have ${st.session_state.budget})")

    return can_proceed, "; ".join(messages) if messages else "OK"


def format_resource_cost(time_cost: float = 0, budget_cost: float = 0) -> str:
    """Format a resource cost string for display."""
    parts = []
    if time_cost > 0:
        parts.append(f"⏱️ {time_cost}h")
    if budget_cost > 0:
        parts.append(f"💰 ${budget_cost}")
    return " | ".join(parts) if parts else "Free"


def resource_preview(time_cost: float = 0, budget_cost: float = 0) -> str:
    """Show what an action will cost and what remains after.

    Returns a formatted string like:
    "Cost: 1h | $25 -- Remaining: 5h, $475"
    """
    cost_str = format_resource_cost(time_cost, budget_cost)
    remaining_time = st.session_state.time_remaining - time_cost
    remaining_budget = st.session_state.budget - budget_cost
    return f"{cost_str} -- Remaining: {remaining_time}h, ${remaining_budget}"
