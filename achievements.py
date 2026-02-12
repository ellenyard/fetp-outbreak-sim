"""
Achievement / Badge system for the FETP Outbreak Simulation.

Provides achievement definitions, checking logic, and rendering helpers.
Achievements are evaluated against Streamlit session_state and awarded
via st.toast() notifications when newly unlocked.
"""

import streamlit as st


# ── Achievement Definitions ──────────────────────────────────────────────────
# Each achievement has:
#   id        - unique key
#   name      - display name
#   emoji     - badge icon
#   description - short text shown under the badge
#   check     - callable(session_state) -> bool

ACHIEVEMENTS = [
    {
        "id": "first_contact",
        "name": "First Contact",
        "emoji": "\U0001f4ac",  # 💬
        "description": "Conducted your first NPC interview",
        "check": lambda ss: len(ss.get("interview_history", {})) >= 1,
    },
    {
        "id": "sharp_eye",
        "name": "Sharp Eye",
        "emoji": "\U0001f50d",  # 🔍
        "description": "Found all true cases in clinic records",
        "check": lambda ss: (
            ss.get("case_finding_score") is not None
            and ss.get("case_finding_score", {}).get("true_positives", 0)
            == ss.get("case_finding_score", {}).get("total_true", 0)
            and ss.get("case_finding_score", {}).get("total_true", 0) > 0
        ),
    },
    {
        "id": "diplomat",
        "name": "Diplomat",
        "emoji": "\U0001f91d",  # 🤝
        "description": "Got 3+ NPCs to cooperative state",
        "check": lambda ss: sum(
            1
            for v in ss.get("npc_state", {}).values()
            if v.get("emotion") == "cooperative"
        )
        >= 3,
    },
    {
        "id": "one_health_champion",
        "name": "One Health Champion",
        "emoji": "\U0001f30d",  # 🌍
        "description": "Engaged veterinary and environmental NPCs",
        "check": lambda ss: ss.get("vet_unlocked", False)
        or ss.get("env_officer_unlocked", False),
    },
    {
        "id": "early_bird",
        "name": "Early Bird",
        "emoji": "\U0001f305",  # 🌅
        "description": "Ordered lab tests on Day 1",
        "check": lambda ss: any(
            int(o.get("placed_day", 99)) <= 1 for o in ss.get("lab_orders", [])
        ),
    },
    {
        "id": "budget_hawk",
        "name": "Budget Hawk",
        "emoji": "\U0001f4b0",  # 💰
        "description": "Finished the investigation with budget to spare",
        "check": lambda ss: ss.get("budget", 0) >= 300
        and ss.get("current_day", 1) >= 5,
    },
    {
        "id": "thorough_investigator",
        "name": "Thorough Investigator",
        "emoji": "\U0001f4cb",  # 📋
        "description": "Visited all map locations",
        "check": lambda ss: len(ss.get("visited_locations", set())) >= 6,
    },
    {
        "id": "case_def_master",
        "name": "Case Definition Master",
        "emoji": "\U0001f3c6",  # 🏆
        "description": "Built a case definition with all WHO tiers",
        "check": lambda ss: bool(
            ss.get("case_definition_builder", {})
            .get("tiers", {})
            .get("suspected", {})
            .get("required_any")
        )
        and bool(
            ss.get("case_definition_builder", {})
            .get("tiers", {})
            .get("probable", {})
            .get("required_any")
        )
        and ss.get("case_definition_builder", {})
        .get("tiers", {})
        .get("confirmed", {})
        .get("lab_required", False),
    },
    {
        "id": "speed_runner",
        "name": "Speed Runner",
        "emoji": "\u26a1",  # ⚡
        "description": "Advanced to Day 2 with time to spare",
        "check": lambda ss: ss.get("current_day", 1) >= 2
        and ss.get("time_remaining", 0) >= 3,
    },
    {
        "id": "evidence_hunter",
        "name": "Evidence Hunter",
        "emoji": "\U0001f9e9",  # 🧩
        "description": "Collected 5+ pieces of evidence on the board",
        "check": lambda ss: len(ss.get("evidence_board", [])) >= 5,
    },
]


def check_achievements(session_state) -> list[dict]:
    """Evaluate all achievements against current session state.

    Returns a list of newly-earned achievement dicts (may be empty).
    Mutates session_state to record earned achievements.
    """
    earned_list = session_state.get("achievements", [])
    earned_ids = {a["id"] for a in earned_list}
    newly_earned = []

    for ach in ACHIEVEMENTS:
        if ach["id"] in earned_ids:
            continue
        try:
            if ach["check"](session_state):
                record = {
                    "id": ach["id"],
                    "name": ach["name"],
                    "emoji": ach["emoji"],
                    "description": ach["description"],
                    "day_earned": session_state.get("current_day", 1),
                }
                earned_list.append(record)
                earned_ids.add(ach["id"])
                newly_earned.append(record)
        except Exception:
            # Silently skip achievements whose checks fail due to
            # missing keys or unexpected state shapes.
            pass

    session_state["achievements"] = earned_list
    return newly_earned


def show_achievement_toasts(newly_earned: list[dict]):
    """Display st.toast() notifications for each newly-earned badge."""
    for ach in newly_earned:
        st.toast(
            f"{ach['emoji']} Achievement Unlocked: **{ach['name']}**",
            icon="\U0001f3c5",  # 🏅
        )


def render_badge_grid(session_state):
    """Render the full achievement grid showing earned and locked badges."""
    earned_ids = {a["id"] for a in session_state.get("achievements", [])}
    earned_map = {a["id"]: a for a in session_state.get("achievements", [])}

    html_parts = ['<div class="badge-grid">']
    for ach in ACHIEVEMENTS:
        is_earned = ach["id"] in earned_ids
        css_class = "badge-item" if is_earned else "badge-item locked"
        emoji = ach["emoji"] if is_earned else "\U0001f512"  # 🔒
        name = ach["name"] if is_earned else "???"
        desc = ach["description"] if is_earned else "Keep investigating..."
        day_text = ""
        if is_earned:
            day = earned_map[ach["id"]].get("day_earned", "?")
            day_text = f'<div style="font-size:0.7em;color:#92400e;margin-top:2px;">Day {day}</div>'

        html_parts.append(f"""
        <div class="{css_class}">
            <span class="badge-emoji">{emoji}</span>
            <div class="badge-name">{name}</div>
            <div class="badge-desc">{desc}</div>
            {day_text}
        </div>
        """)
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_sidebar_badge_count(session_state):
    """Return a short string for the sidebar showing earned / total badges."""
    earned = len(session_state.get("achievements", []))
    total = len(ACHIEVEMENTS)
    return f"\U0001f3c5 Badges: {earned}/{total}"
