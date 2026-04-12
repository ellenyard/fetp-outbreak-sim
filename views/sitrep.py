"""Situation report (SITREP) views for day transitions.

Contains the day transition banner, yesterday recap, daily briefing text,
task list, and the blocking SITREP view shown when advancing days.
"""

import base64
from pathlib import Path

import pandas as pd
import streamlit as st

import achievements
from config.scenarios import load_scenario_content, load_storyline_excerpt
from i18n.translate import t


# ── Day theme configuration ──

DAY_THEMES = {
    1: {
        "title": "Situation Assessment",
        "subtitle": "Arrive on scene. Interview key contacts. Establish your case definition.",
        "color": "#1e3a5f",
        "scene": "scene_investigation_team_working.png",
    },
    2: {
        "title": "Study Design",
        "subtitle": "Design your epidemiological study and prepare your questionnaire.",
        "color": "#2d4a22",
        "scene": "scene_epi_curve_whiteboard.png",
    },
    3: {
        "title": "Data Collection",
        "subtitle": "Collect and analyze data. Follow leads from the field.",
        "color": "#4a3522",
        "scene": "scene_cleanup_crews_barefoot.png",
    },
    4: {
        "title": "Lab & Environment",
        "subtitle": "Order diagnostic tests. Investigate environmental sources.",
        "color": "#3d2252",
        "scene": "scene_lab_sample_collection.png",
    },
    5: {
        "title": "Recommendations",
        "subtitle": "Present your findings and recommend interventions.",
        "color": "#52221e",
        "scene": "scene_community_meeting_concern.png",
    },
}


def day_briefing_text(day: int) -> str:
    """Load scenario-specific day briefing."""
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    briefing_content = load_scenario_content(scenario_id, f"day{day}_briefing")

    # Fallback to translation system if content file not found
    if briefing_content.startswith("\u26a0\ufe0f"):
        return t(f"day{day}_briefing")

    return briefing_content


def day_task_list(day: int):
    """Show tasks and key outputs side by side."""

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"### {t('key_tasks')}")
        if day == 1:
            st.markdown("- Abstract clinic register into a clean line list")
            st.markdown("- Build a tiered working case definition")
            st.markdown("- Conduct case finding and debrief results")
            st.markdown("- Review case cards and hospital charts")
            st.markdown("- Complete descriptive epi worksheet")
            st.markdown("- Review Day 1 lab brief and triangulation checkpoint")
        elif day == 2:
            st.markdown("- Choose a study design")
            st.markdown("- Develop questionnaire")
            st.markdown("- Plan data collection")
        elif day == 3:
            st.markdown("- Administer questionnaire")
            st.markdown("- Enter and clean data")
            st.markdown("- Begin analysis")
        elif day == 4:
            st.markdown("- Complete data analysis")
            st.markdown("- Collect laboratory samples")
            st.markdown("- Conduct environmental assessment")
        else:
            st.markdown("- Finalize diagnosis")
            st.markdown("- Prepare recommendations")
            st.markdown("- Brief leadership")

    with col2:
        st.markdown(f"### {t('key_outputs')}")
        if day == 1:
            # Checkboxes for Day 1 outputs
            st.checkbox("Clinic log line list saved", value=st.session_state.clinic_abstraction_submitted, disabled=True)
            st.checkbox("Working case definition (tiered)", value=st.session_state.case_definition_written, disabled=True)
            st.checkbox("Case-finding debrief recorded", value=bool(st.session_state.case_finding_debrief), disabled=True)
            st.checkbox("Case cards reviewed", value=st.session_state.case_cards_reviewed, disabled=True)
            st.checkbox("Descriptive worksheet completed", value=bool(st.session_state.day1_worksheet), disabled=True)
            st.checkbox("Triangulation checkpoint", value=st.session_state.triangulation_completed, disabled=True)
        elif day == 2:
            study_done = st.session_state.decisions.get("study_design") is not None
            st.checkbox("Study protocol", value=study_done, disabled=True)

            quest_done = st.session_state.questionnaire_submitted
            st.checkbox("Finalized questionnaire", value=quest_done, disabled=True)

            st.checkbox("Sample size calculation", value=False, disabled=True)
        elif day == 3:
            dataset_done = st.session_state.generated_dataset is not None
            st.checkbox("Clean dataset", value=dataset_done, disabled=True)

            st.checkbox("Preliminary descriptive stats", value=st.session_state.descriptive_analysis_done, disabled=True)
        elif day == 4:
            st.checkbox("Analytical results (OR, 95% CI)", value=False, disabled=True)

            lab_done = len(st.session_state.lab_samples_submitted) > 0
            st.checkbox("Laboratory confirmation", value=lab_done, disabled=True)

            st.checkbox("Environmental findings", value=False, disabled=True)
        else:
            final_dx = bool(st.session_state.decisions.get("final_diagnosis"))
            st.checkbox("Final diagnosis", value=final_dx, disabled=True)

            recs_done = bool(st.session_state.decisions.get("recommendations"))
            st.checkbox("Recommendations report", value=recs_done, disabled=True)

            st.checkbox("Briefing presentation", value=False, disabled=True)


def render_day_transition(day: int):
    """Render animated day transition banner with scene image background."""
    theme = DAY_THEMES.get(day, DAY_THEMES[1])
    progress_pct = day * 20

    # Try to load scene image as background
    scenario_id = st.session_state.get("current_scenario", "lepto_rivergate")
    scene_path = Path(f"scenarios/{scenario_id}/assets/{theme['scene']}")
    bg_style = f"background: linear-gradient(135deg, {theme['color']}ee, {theme['color']}bb);"
    if scene_path.exists():
        try:
            with scene_path.open("rb") as f:
                scene_b64 = base64.b64encode(f.read()).decode("utf-8")
            bg_style = (
                f"background: linear-gradient(135deg, {theme['color']}dd, {theme['color']}aa),"
                f" url('data:image/png;base64,{scene_b64}');"
                f" background-size: cover; background-position: center;"
            )
        except Exception:
            pass

    html = f"""
    <div class="day-banner" style="{bg_style}">
        <div class="day-number">DAY {day}</div>
        <div class="day-title">{theme['title']}</div>
        <div class="day-subtitle">{theme['subtitle']}</div>
        <div class="progress-track">
            <div class="progress-fill" style="--progress-width: {progress_pct}%; width: {progress_pct}%;"></div>
        </div>
        <div style="font-size: 0.8em; opacity: 0.7; margin-top: 6px;">Investigation Progress: {progress_pct}%</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_yesterday_recap(day: int):
    """Show accomplishments from the previous day using the decision log."""
    if day <= 1:
        return

    prev_day = day - 1
    decision_log = st.session_state.get("_decision_log", [])
    prev_events = [e for e in decision_log if e.get("game_day") == prev_day]

    if not prev_events:
        return

    interviews = [e for e in prev_events if e.get("type") == "interview"]
    travels = [e for e in prev_events if e.get("type") == "travel"]
    labs = [e for e in prev_events if e.get("type") == "lab_test"]
    other = [e for e in prev_events if e.get("type") not in ("interview", "travel", "lab_test")]

    time_spent = sum(e.get("cost_time", 0) for e in prev_events)
    budget_spent = sum(e.get("cost_budget", 0) for e in prev_events)

    st.markdown("### Yesterday's Accomplishments")

    cols = st.columns(4)
    with cols[0]:
        st.metric("\U0001f4ac Interviews", len(interviews))
    with cols[1]:
        st.metric("\U0001f6b6 Locations", len(travels))
    with cols[2]:
        st.metric("\U0001f9ea Lab Orders", len(labs))
    with cols[3]:
        st.metric("\u23f1\ufe0f Time Used", f"{time_spent}h")

    if budget_spent > 0:
        st.caption(f"Budget spent yesterday: ${budget_spent}")


def view_sitrep():
    """Daily situation report - blocking view before advancing to next day."""
    day = st.session_state.current_day

    # Animated day transition banner
    render_day_transition(day)

    # Yesterday's recap (for days 2+)
    render_yesterday_recap(day)

    # Story beat
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    storyline_excerpt = load_storyline_excerpt(scenario_id)
    if storyline_excerpt:
        st.markdown("---")
        st.markdown("### Story Beat")
        st.markdown(storyline_excerpt)

    # Today's objectives
    st.markdown("---")
    st.markdown("### Today's Objectives")
    day_task_list(day)

    # New admissions count
    st.markdown("---")
    st.markdown("### New Patient Admissions")
    truth = st.session_state.truth
    pop_df = truth.get("full_population", pd.DataFrame())
    if not pop_df.empty:
        new_cases = pop_df[pop_df["hospital_day"] == day]
        if len(new_cases) > 0:
            st.markdown(f"**{len(new_cases)} new patients** were admitted overnight.")
        else:
            st.markdown("*No new admissions recorded.*")
    else:
        st.markdown("*No new admissions recorded.*")

    # Check and display achievements earned so far
    newly_earned = achievements.check_achievements(st.session_state)
    achievements.show_achievement_toasts(newly_earned)

    # Continue button
    st.markdown("---")
    if st.button(
        f"\u2705 Continue to Day {day}",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.sitrep_viewed = True
        st.session_state.current_view = "map"
        st.rerun()
