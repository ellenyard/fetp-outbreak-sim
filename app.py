"""FETP Outbreak Investigation Simulation — Main Entry Point.

This is the Streamlit application entry point. All logic has been modularized
into the following packages:

    config/      — Locations, scenarios, constants
    ui/          — Theme, sidebar, routing, shared components
    views/       — All view functions (overview, map, interviews, etc.)
    npc/         — NPC response engine, emotions, context building
    state/       — Session state initialization, resource management
    data_utils/  — Clinic records, charts, case definition helpers
    i18n/        — Translation system
"""

import streamlit as st
import time
from pathlib import Path

# Core game modules
import outbreak_logic as jl

# Modular imports
from state.init import init_session_state, check_autosave
from ui.theme import inject_investigation_theme
from ui.sidebar import adventure_sidebar
from ui.routing import route_to_view
from views.intro import view_intro, view_alert
from config.scenarios import load_truth_and_population
from config.locations import SCENARIO_INITIAL_NPCS

# Re-export load_scenario_config for use by other modules
load_scenario_config = jl.load_scenario_config


def main():
    st.set_page_config(
        page_title="FETP Outbreak Simulation",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    init_session_state()
    inject_investigation_theme()

    # Scenario selector in sidebar
    with st.sidebar:
        st.title("📋 Scenario Selection")

        scenario_options = [
            ("lepto_rivergate", "🌊 Rivergate After the Storm")
        ]

        # Find current selection index
        current_idx = 0
        if st.session_state.current_scenario:
            for i, (sid, _) in enumerate(scenario_options):
                if sid == st.session_state.current_scenario:
                    current_idx = i
                    break

        # Disable the selector once the investigation has started so
        # the trainee can't accidentally wipe their progress.
        game_started = st.session_state.get("alert_acknowledged", False)
        scenario_choice = st.selectbox(
            "Select outbreak scenario:",
            options=scenario_options,
            format_func=lambda x: x[1],
            key="scenario_selector",
            index=current_idx,
            help="Choose which outbreak scenario to investigate",
            disabled=game_started,
        )

        scenario_id = scenario_choice[0]
        scenario_name = scenario_choice[1]

        if st.session_state.current_scenario:
            st.caption(f"**Active:** {st.session_state.current_scenario_name}")
        st.markdown("---")

    scenario_config = load_scenario_config(scenario_id)
    scenario_type = scenario_config.get("scenario_type") or ("lepto" if "lepto" in scenario_id else "je")
    scenario_root = Path(f"scenarios/{scenario_id}")
    data_dir = str(scenario_root / "data") if (scenario_root / "data").exists() else str(scenario_root)

    # Check if we need to load or reload data
    need_reload = (
        "truth" not in st.session_state or
        st.session_state.get("current_scenario") != scenario_id
    )

    if need_reload:
        with st.spinner(f"Loading {scenario_name}..."):
            st.session_state.current_scenario = scenario_id
            st.session_state.current_scenario_name = scenario_config.get("display_name") or scenario_name
            st.session_state.current_scenario_type = scenario_type
            st.session_state.data_dir = data_dir
            st.session_state.scenario_config = scenario_config

            # Load truth data for selected scenario
            try:
                st.session_state.truth = load_truth_and_population(
                    data_dir=data_dir,
                    scenario_type=scenario_type
                )
            except FileNotFoundError as exc:
                st.error(str(exc))
                st.stop()
            except Exception as exc:
                st.error(f"Failed to load scenario data: {exc}")
                st.stop()

            # Reset investigation progress when switching scenarios
            st.session_state.current_day = 1
            st.session_state.current_view = "alert"
            st.session_state.alert_acknowledged = False
            st.session_state.decisions = {}
            if 'interview_history' in st.session_state:
                st.session_state.interview_history = {}
            if 'game_state' in st.session_state:
                st.session_state.game_state = 'INTRO'

            # Reset and set scenario-specific NPCs (prefer JSON config, fall back to hardcoded)
            scenario_cfg = st.session_state.get("scenario_config", {})
            initial_npcs = scenario_cfg.get("initial_npcs") or SCENARIO_INITIAL_NPCS.get(scenario_id, [])
            st.session_state.npcs_unlocked = list(initial_npcs)
            st.session_state.one_health_triggered = False
            st.session_state.vet_unlocked = False
            st.session_state.env_officer_unlocked = False

        st.success(f"✅ Loaded: {scenario_name}")
        time.sleep(0.5)
        st.rerun()

    # Check game state
    game_state = st.session_state.get('game_state', 'INTRO')

    # INTRO state: Show Dr. Tran phone call
    if game_state == 'INTRO' and not st.session_state.alert_acknowledged:
        view_intro()
        return

    # Autosave check (best-effort, every 5 min)
    check_autosave()

    # Sidebar (persistent across all states)
    adventure_sidebar()

    # If alert hasn't been acknowledged yet (legacy), show alert screen
    if not st.session_state.alert_acknowledged:
        view_alert()
        return

    # Route to appropriate view
    view = st.session_state.current_view
    if route_to_view(view):
        return


if __name__ == "__main__":
    main()
