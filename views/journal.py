"""Investigation journal and evidence board views.

Provides a visual timeline of investigation actions and an evidence board
for tracking clues and hypotheses.
"""

import streamlit as st

from i18n.translate import t


# Re-export DAY_THEMES so the journal can label day sections.
# Avoids importing the full sitrep module at module level.
_DAY_THEMES = None


def _get_day_themes():
    """Lazy-load DAY_THEMES from sitrep to avoid circular imports."""
    global _DAY_THEMES
    if _DAY_THEMES is None:
        from views.sitrep import DAY_THEMES
        _DAY_THEMES = DAY_THEMES
    return _DAY_THEMES


EVENT_TYPE_CONFIG = {
    "interview":              {"color": "#f59e0b", "icon": "\U0001f4ac", "label": "Interview"},
    "travel":                 {"color": "#3b82f6", "icon": "\U0001f6b6", "label": "Travel"},
    "lab_test":               {"color": "#8b5cf6", "icon": "\U0001f9ea", "label": "Lab Order"},
    "case_finding":           {"color": "#10b981", "icon": "\U0001f50d", "label": "Case Finding"},
    "environment_inspection": {"color": "#06b6d4", "icon": "\U0001f33f", "label": "Environmental"},
    "site_inspection":        {"color": "#06b6d4", "icon": "\U0001f3d8\ufe0f", "label": "Site Visit"},
    "questionnaire_submitted":{"color": "#ec4899", "icon": "\U0001f4dd", "label": "Questionnaire"},
    "analysis_confirmed":     {"color": "#14b8a6", "icon": "\U0001f4ca", "label": "Analysis"},
    "case_definition_saved":  {"color": "#f97316", "icon": "\U0001f4cb", "label": "Case Definition"},
    "recommendations_submitted":{"color": "#ef4444", "icon": "\U0001f4e2", "label": "Recommendations"},
}


def view_investigation_journal():
    """Visual timeline of all investigation actions from the decision log."""
    st.title("\U0001f4d4 Investigation Journal")
    st.caption("A chronological record of your investigation activities.")

    decision_log = st.session_state.get("_decision_log", [])
    if not decision_log:
        st.info("No actions recorded yet. Start investigating to see your timeline here!")
        return

    # Resource summary
    total_time = sum(e.get("cost_time", 0) for e in decision_log)
    total_budget = sum(e.get("cost_budget", 0) for e in decision_log)
    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("Total Actions", len(decision_log))
    with summary_cols[1]:
        st.metric("Time Spent", f"{total_time}h")
    with summary_cols[2]:
        st.metric("Budget Spent", f"${total_budget}")
    with summary_cols[3]:
        st.metric("Budget Remaining", f"${st.session_state.get('budget', 0)}")

    st.markdown("---")

    DAY_THEMES = _get_day_themes()

    # Group events by day
    max_day = st.session_state.get("current_day", 1)
    for day in range(1, max_day + 1):
        day_events = [e for e in decision_log if e.get("game_day") == day]
        if not day_events:
            continue

        theme = DAY_THEMES.get(day, {})
        day_title = theme.get("title", f"Day {day}")
        st.markdown(f"### Day {day}: {day_title}")

        for event in day_events:
            event_type = event.get("type", "unknown")
            config = EVENT_TYPE_CONFIG.get(
                event_type,
                {"color": "#6b7280", "icon": "\U0001f4dd", "label": event_type.replace("_", " ").title()},
            )

            # Extract detail text from payload
            payload = event.get("payload", event.get("details", {})) or {}
            detail_text = (
                payload.get("npc_name", "")
                or payload.get("to", "")
                or payload.get("test", "")
                or payload.get("location", "")
                or payload.get("sample_type", "")
                or ""
            )

            cost_parts = []
            if event.get("cost_time"):
                cost_parts.append(f"\u23f1\ufe0f {event['cost_time']}h")
            if event.get("cost_budget"):
                cost_parts.append(f"\U0001f4b0 ${event['cost_budget']}")
            cost_display = " \u00b7 ".join(cost_parts)

            html = f"""
            <div class="timeline-event">
                <div class="timeline-bar" style="background: {config['color']};"></div>
                <div class="timeline-content">
                    <div class="timeline-title">{config['icon']} {config['label']}{': ' + detail_text if detail_text else ''}</div>
                    <div class="timeline-detail">{cost_display}</div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

        # Day subtotals
        day_time = sum(e.get("cost_time", 0) for e in day_events)
        day_budget = sum(e.get("cost_budget", 0) for e in day_events)
        st.caption(f"Day {day}: {len(day_events)} actions \u00b7 {day_time}h \u00b7 ${day_budget}")
        st.markdown("---")


def init_evidence_board():
    """Initialize evidence board with 3 starting clues."""
    if "evidence_board" not in st.session_state:
        st.session_state.evidence_board = [
            {
                "clue": "Pig abortions (Viral)",
                "type": "hypothesis",
                "day_added": 1,
                "source": "Initial observation"
            },
            {
                "clue": "Dragon Fire rumor (Toxin)",
                "type": "hypothesis",
                "day_added": 1,
                "source": "Community reports"
            },
            {
                "clue": "High Fever (Weakens Toxin)",
                "type": "clinical",
                "day_added": 1,
                "source": "Hospital records"
            }
        ]


def sync_evidence_board_from_log():
    """Sync the evidence board with new entries from the decision log."""
    decision_log = st.session_state.decisions.get("_decision_log", []) or []
    st.session_state.setdefault("evidence_event_ids", set())

    for event in decision_log:
        event_id = event.get("event_id")
        if not event_id or event_id in st.session_state.evidence_event_ids:
            continue

        clue = None
        clue_type = "epidemiological"
        source = "Investigation log"
        if event.get("type") == "interview":
            npc_name = event.get("details", {}).get("npc_name", "NPC interview")
            clue = f"Interviewed {npc_name}"
        elif event.get("type") == "case_finding":
            tp = event.get("details", {}).get("true_positives", 0)
            clue = f"Case finding identified {tp} likely cases"
            clue_type = "clinical"
        elif event.get("type") == "lab_test":
            test = event.get("details", {}).get("test", "Lab test")
            clue = f"Lab order placed: {test}"
            clue_type = "clinical"
        elif event.get("type") == "environment_inspection":
            site = event.get("details", {}).get("site", "Environmental site")
            clue = f"Inspected {site}"
            clue_type = "environmental"
        elif event.get("type") == "travel":
            to_loc = event.get("details", {}).get("to")
            if to_loc:
                clue = f"Visited {to_loc}"

        if clue:
            st.session_state.evidence_board.append({
                "clue": clue,
                "type": clue_type,
                "day_added": event.get("game_day", st.session_state.current_day),
                "source": source,
            })
            st.session_state.evidence_event_ids.add(event_id)


def view_evidence_board():
    """Display the evidence board."""
    st.markdown("### 🔍 Evidence Board")
    st.markdown("Track key clues and hypotheses as you investigate.")

    if not st.session_state.get("evidence_board"):
        init_evidence_board()

    sync_evidence_board_from_log()

    for i, evidence in enumerate(st.session_state.evidence_board):
        with st.expander(f"**{evidence['clue']}** (Day {evidence['day_added']})", expanded=(i < 3)):
            st.markdown(f"**Type:** {evidence['type'].title()}")
            st.markdown(f"**Source:** {evidence['source']}")

    # Add new evidence
    st.markdown("---")
    with st.form("add_evidence"):
        new_clue = st.text_input("New clue or hypothesis")
        clue_type = st.selectbox("Type", ["hypothesis", "clinical", "environmental", "epidemiological"])
        clue_source = st.text_input("Source (optional)")

        if st.form_submit_button("Add to Evidence Board"):
            if new_clue:
                st.session_state.evidence_board.append({
                    "clue": new_clue,
                    "type": clue_type,
                    "day_added": st.session_state.current_day,
                    "source": clue_source or "Investigation team"
                })
                st.success("Added to evidence board!")
                st.rerun()
