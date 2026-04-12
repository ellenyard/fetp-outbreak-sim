"""Intro and alert views for the investigation.

Contains the initial phone-call intro screen and the Day 0 alert view
that players see before beginning the investigation.
"""

import streamlit as st

from config.scenarios import load_scenario_content
from i18n.translate import t


def view_intro():
    """Phone call intro screen with scenario-specific content."""
    # Load scenario-specific alert content
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    alert_content = load_scenario_content(scenario_id, "alert")

    # Extract doctor name from alert content for subtitle
    doctor_name = "District Hospital"
    for line in alert_content.split('\n'):
        if line.startswith('**From:**'):
            # Extract just the doctor name part (before comma if present)
            from_text = line.replace('**From:**', '').strip()
            doctor_name = from_text.split(',')[0] if ',' in from_text else from_text
            break

    # Display phone call header
    st.markdown("# 📞 Incoming Call")
    st.markdown(f"### {doctor_name}")
    st.markdown("---")

    # Display scenario-specific alert content
    st.markdown(alert_content)

    st.markdown("---")

    # Accept assignment button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("✅ Accept Assignment", type="primary", use_container_width=True):
            # Lazy import to avoid circular dependency with app.py
            from views.map import unlock_day1_locations
            import outbreak_logic as jl
            set_game_state = getattr(jl, "set_game_state", None)
            if set_game_state:
                set_game_state('DASHBOARD', st.session_state)
            st.session_state.alert_acknowledged = True
            unlock_day1_locations()
            st.session_state.current_view = "map"
            st.rerun()


def view_alert():
    """Day 0: Alert call intro screen."""
    # Load scenario-specific alert content
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    alert_content = load_scenario_content(scenario_id, "alert")

    st.title("📞 Outbreak Alert")
    st.markdown(alert_content)

    st.info(
        "When you're ready, begin the investigation. You'll move through the steps of an outbreak investigation over five simulated days."
    )

    if st.button(t("begin_investigation")):
        # Lazy import to avoid circular dependency with app.py
        from views.map import unlock_day1_locations
        st.session_state.alert_acknowledged = True
        st.session_state.current_day = 1
        unlock_day1_locations()
        st.session_state.current_view = "overview"
        st.rerun()
