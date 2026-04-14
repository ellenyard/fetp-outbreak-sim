"""Adventure mode sidebar for the investigation interface.

Provides the sidebar with language selection, resource display, progress
tracking, session management, notebook, and day advancement controls.
"""

import streamlit as st

import persistence
import achievements
from i18n.translate import t
from npc.engine import refresh_lab_queue_for_day
from state.progress import get_day_tasks, get_completion_summary


def _scenario_config_label(scenario_type: str) -> str:
    """Return a human-readable label for the scenario type.

    This is a local helper; the canonical version lives in app.py
    (scenario_config_label).  Imported here to avoid pulling in the
    entire app module.
    """
    # Lazy import to avoid circular dependency
    from data_utils.case_definition import scenario_config_label
    return scenario_config_label(scenario_type)


def _check_day_prerequisites(current_day, session_state):
    """Proxy for outbreak_logic.check_day_prerequisites."""
    import outbreak_logic as jl
    return jl.check_day_prerequisites(current_day, session_state)


def adventure_sidebar():
    """Minimal sidebar for adventure mode with resources and tools."""
    # Language selector
    st.sidebar.markdown(f"### {t('language_header')}")
    lang_options = {"en": "English", "es": "Español", "fr": "Français", "pt": "Português"}
    selected_lang = st.sidebar.selectbox(
        t("language_select"),
        options=list(lang_options.keys()),
        format_func=lambda x: lang_options.get(x, x),
        index=list(lang_options.keys()).index(st.session_state.get("language", "en") if st.session_state.get("language", "en") in lang_options else "en"),
        key="lang_selector"
    )
    if selected_lang != st.session_state.language:
        st.session_state.language = selected_lang
        st.rerun()

    st.sidebar.markdown("---")
    # Use the setting name (e.g. "Rivergate Municipality") instead of the
    # disease name so the sidebar does not spoil the diagnosis for trainees.
    scenario_cfg = st.session_state.get("scenario_config", {}) or {}
    setting = scenario_cfg.get("setting_name", "Outbreak")
    st.sidebar.title(f"{setting} Investigation")

    if not st.session_state.alert_acknowledged:
        st.sidebar.info("Review the alert to begin.")
        return

    # Resources with warning colors
    time_val = st.session_state.time_remaining
    budget_val = st.session_state.budget
    time_pct = time_val / 8 if time_val > 0 else 0
    budget_pct = budget_val / 800 if budget_val > 0 else 0

    if time_val < 0:
        time_display = f":red[{time_val}h (overtime)]"
    elif time_pct <= 0.10:
        time_display = f":red[{time_val}h]"
    elif time_pct <= 0.25:
        time_display = f":orange[{time_val}h]"
    else:
        time_display = f"{time_val}h"

    if budget_pct <= 0.10:
        budget_display = f":red[${budget_val}]"
    elif budget_pct <= 0.25:
        budget_display = f":orange[${budget_val}]"
    else:
        budget_display = f"${budget_val}"

    st.sidebar.markdown(f"""
    **{t('day')}:** {st.session_state.current_day} / 5
    **{t('time_remaining')}:** {time_display}
    **{t('budget')}:** {budget_display}
    **{t('lab_credits')}:** {st.session_state.lab_credits}
    """)

    # Resource forecast
    avg_interview_time = 1.0
    interviews_possible = max(0, int(time_val / avg_interview_time)) if time_val > 0 else 0
    labs_remaining = st.session_state.lab_credits
    st.sidebar.caption(f"~{interviews_possible} interviews, {labs_remaining} lab tests remaining")

    # Progress tracker
    st.sidebar.markdown("---")
    current_day = st.session_state.current_day
    summary = get_completion_summary(current_day)
    st.sidebar.markdown(f"### Day {current_day} Progress")
    st.sidebar.progress(summary["pct"] / 100)
    st.sidebar.caption(f"{summary['completed']}/{summary['total']} tasks complete")

    tasks = get_day_tasks(current_day)
    for task in tasks:
        icon = "✅" if task["done"] else "⬜"
        label = task["label"]
        suffix = "" if task["required"] else " *(optional)*"
        if not task["done"] and task.get("view_link"):
            if st.sidebar.button(
                f"{icon} {label}{suffix}",
                key=f"progress_{task['id']}",
                use_container_width=True,
            ):
                st.session_state.current_view = task["view_link"]
                st.rerun()
        else:
            st.sidebar.markdown(f"{icon} {label}{suffix}")

    # Day overview
    st.sidebar.markdown("")
    for day in range(1, 6):
        if day < current_day:
            st.sidebar.markdown(f"[✓] Day {day}")
        elif day == current_day:
            st.sidebar.markdown(f"**[●] Day {day}**")
        else:
            st.sidebar.markdown(f"[ ] Day {day}")

    # Achievements & Journal
    st.sidebar.markdown("---")
    badge_text = achievements.render_sidebar_badge_count(st.session_state)
    st.sidebar.markdown(f"**{badge_text}**")
    if st.sidebar.button("\U0001f4d4 Investigation Journal", key="sidebar_journal", use_container_width=True):
        st.session_state.current_view = "journal"
        st.rerun()
    hints_on = st.sidebar.checkbox(
        "\U0001f4fb Show hints from HQ",
        value=st.session_state.get("hints_enabled", True),
        key="hints_toggle",
    )
    st.session_state["hints_enabled"] = hints_on

    # Session Management
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Session")
    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("Save", use_container_width=True, key="save_session"):
            try:
                save_data = persistence.create_save_file(st.session_state)
                filename = persistence.get_save_filename(st.session_state)
                st.sidebar.download_button(
                    label="⬇️ Download",
                    data=save_data,
                    file_name=filename,
                    mime="application/json",
                    use_container_width=True,
                    key="download_save"
                )
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

    with col2:
        uploaded = st.file_uploader(
            "📂",
            type=["json"],
            key="load_session",
            label_visibility="collapsed"
        )
        if uploaded is not None:
            success, message = persistence.load_save_file(uploaded, st.session_state)
            if success:
                st.sidebar.success(message)
                st.rerun()
            else:
                st.sidebar.error(message)

    # Investigation Notebook
    st.sidebar.markdown("---")
    with st.sidebar.expander(f"📓 {t('notebook')}"):
        st.caption("Record observations and insights.")

        new_note = st.text_area("Add note:", height=60, key="new_note")
        if st.button("Save Note", key="save_note"):
            if new_note.strip():
                from datetime import datetime
                entry = {
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "day": st.session_state.current_day,
                    "note": new_note.strip()
                }
                st.session_state.notebook_entries.append(entry)
                st.success("Saved!")
                st.rerun()

        if st.session_state.notebook_entries:
            st.markdown("**Your Notes:**")
            for entry in reversed(st.session_state.notebook_entries[-5:]):
                st.markdown(f"*Day {entry['day']} @ {entry['timestamp']}*")
                st.markdown(f"> {entry['note']}")
                st.markdown("---")

    # Advance day button
    st.sidebar.markdown("---")
    if st.session_state.current_day < 5:
        if st.sidebar.button(f"{t('advance_day')} {st.session_state.current_day + 1}", use_container_width=True):
            can_advance, missing = _check_day_prerequisites(st.session_state.current_day, st.session_state)
            if can_advance:
                # Check achievements before advancing
                newly_earned = achievements.check_achievements(st.session_state)
                achievements.show_achievement_toasts(newly_earned)

                st.session_state.current_day += 1
                st.session_state.time_remaining = 8
                refresh_lab_queue_for_day(int(st.session_state.current_day))
                st.session_state.advance_missing_tasks = []
                # Show SITREP view for new day
                st.session_state.current_view = "sitrep"
                st.session_state.sitrep_viewed = False
                st.rerun()
            else:
                st.session_state.advance_missing_tasks = missing
                # Show styled day gate checklist
                st.sidebar.markdown("---")
                day_summary = get_completion_summary(st.session_state.current_day)
                required_done = day_summary["required_completed"]
                required_total = day_summary["required_total"]
                st.sidebar.warning(
                    f"**{required_done}/{required_total} required tasks complete.** "
                    f"Finish the remaining tasks to advance."
                )
                day_tasks = get_day_tasks(st.session_state.current_day)
                for task in day_tasks:
                    if not task["required"]:
                        continue
                    icon = "✅" if task["done"] else "❌"
                    if not task["done"] and task.get("view_link"):
                        col1, col2 = st.sidebar.columns([4, 1])
                        with col1:
                            st.markdown(f"{icon} {task['label']}")
                        with col2:
                            if st.button("Go", key=f"gate_{task['id']}"):
                                st.session_state.current_view = task["view_link"]
                                st.rerun()
                    else:
                        st.sidebar.markdown(f"{icon} {task['label']}")
    else:
        st.sidebar.success("📋 Final Day!")
