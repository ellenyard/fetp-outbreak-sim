import streamlit as st
import logging
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from i18n.translate import t
from config.locations import get_current_scenario_id
from npc.engine import get_npc_response, stream_npc_response, get_npc_avatar, lab_test_label
from npc.emotions import get_npc_trust, update_npc_emotion, analyze_user_tone
from npc.unlock import check_npc_unlock_triggers, has_hospital_records_access
from state.resources import spend_time, spend_budget, format_resource_cost, resource_preview, TIME_COSTS, BUDGET_COSTS
import achievements
import outbreak_logic as jl


def _show_suggested_prompts(npc_key: str, npc: dict):
    """Show suggested question topics based on unasked conditional clues."""
    history = st.session_state.interview_history.get(npc_key, [])
    if len(history) < 4:
        return  # Don't show until a few exchanges have happened

    # Check conditional clues the player hasn't triggered yet
    conditional = npc.get("conditional_clues", {})
    if not conditional:
        return

    asked_text = " ".join(
        m["content"].lower() for m in history if m["role"] == "user"
    )

    suggestions = []
    for trigger_pattern, clue_info in conditional.items():
        keywords = [k.strip().lower() for k in trigger_pattern.split("|")]
        if not any(kw in asked_text for kw in keywords if len(kw) > 2):
            # Player hasn't asked about this topic
            hint_word = keywords[0] if keywords else trigger_pattern
            suggestions.append(hint_word)

    if suggestions:
        st.markdown("---")
        st.caption("Try asking about:")
        for s in suggestions[:3]:
            st.markdown(f"  *{s}*")


def _extract_revealed_clues(npc_key: str, npc: dict, response: str):
    """Track which clues have been revealed in conversation.

    A clue is only marked as revealed when the NPC's response contains
    enough distinctive words from the clue text, confirming the NPC
    actually communicated that information to the player.
    """
    if "revealed_clues" not in st.session_state:
        st.session_state["revealed_clues"] = {}
    if npc_key not in st.session_state["revealed_clues"]:
        st.session_state["revealed_clues"][npc_key] = []

    revealed = st.session_state["revealed_clues"][npc_key]
    response_lower = response.lower()

    def _clue_matches_response(clue_text: str) -> bool:
        """Check if enough distinctive words from the clue appear in the response.

        Uses words with 5+ characters to avoid matching on common short words.
        Requires at least 40% of distinctive words to match, with a minimum of 3.
        """
        words = [w.lower().strip(".,!?;:\"'()") for w in clue_text.split() if len(w) > 4]
        if len(words) < 2:
            # Very short clue — require exact substring match instead
            # Strip punctuation for comparison
            clean_clue = clue_text.lower().strip(".,!?;:\"'()")
            return clean_clue in response_lower
        threshold = max(3, int(len(words) * 0.4))
        matched = sum(1 for w in words if w in response_lower)
        return matched >= threshold

    # Check always_reveal items
    for clue in npc.get("always_reveal", []):
        if clue not in revealed and _clue_matches_response(clue):
            revealed.append(clue)

    # Check conditional clues
    for trigger, clue_info in npc.get("conditional_clues", {}).items():
        clue_text = clue_info if isinstance(clue_info, str) else clue_info.get("clue", "")
        if clue_text and clue_text not in revealed and _clue_matches_response(clue_text):
            revealed.append(clue_text)


def render_interview_modal():
    """Render interview modal for NPC conversations."""
    npc_key = st.session_state.get("current_npc")
    if not npc_key:
        st.session_state.action_modal = None
        st.rerun()
        return

    npc_truth = st.session_state.truth.get("npc_truth", {})
    if npc_key not in npc_truth:
        st.error("NPC not found!")
        st.session_state.action_modal = None
        st.session_state.current_npc = None
        st.rerun()
        return

    npc = npc_truth[npc_key]

    npc_image_path = npc.get("image_path")
    has_photo = npc_image_path and Path(npc_image_path).exists()

    # Auto-scroll the interview panel into view when it opens
    st.markdown(
        '<div id="interview-anchor"></div>'
        '<script>document.getElementById("interview-anchor")'
        ".scrollIntoView({behavior:'smooth',block:'start'});</script>",
        unsafe_allow_html=True,
    )

    # Modal header
    header_col, close_col = st.columns([6, 1])
    with header_col:
        st.markdown(f"### Interview: {npc.get('name', 'Unknown')}")
        st.caption(f"*{npc.get('role', '')}*")
    with close_col:
        if st.button("✖ Close", key="close_interview"):
            st.session_state.action_modal = None
            st.session_state.current_npc = None
            st.rerun()

    st.markdown("---")

    photo_col, chat_col = st.columns([1.5, 3], gap="large")
    with photo_col:
        if has_photo:
            st.image(npc_image_path, use_container_width=True)
        else:
            st.markdown(
                f"<div style='font-size:72px; text-align:center;'>{npc.get('avatar', '👤')}</div>",
                unsafe_allow_html=True,
            )
        # NPC info card
        st.markdown(f"**{npc.get('name', 'Unknown')}**")
        st.caption(f"{npc.get('role', '')}")
        if npc.get('location'):
            st.caption(f"Location: {npc.get('location')}")

        # Visual trust meter
        trust_level = get_npc_trust(npc_key)
        if npc_key != "nurse_joy":
            trust_normalized = max(0, min(100, ((trust_level + 3) / 8) * 100))
            trust_color = "#ef4444" if trust_normalized < 25 else "#f59e0b" if trust_normalized < 50 else "#10b981"
            st.markdown(f"""
            <div style="margin: 8px 0;">
                <div style="font-size: 0.8em; color: #6b7280; margin-bottom: 4px;">Trust Level</div>
                <div style="background: #e5e7eb; border-radius: 8px; height: 10px; overflow: hidden;">
                    <div style="background: {trust_color}; width: {trust_normalized}%; height: 100%; border-radius: 8px; transition: width 0.3s;"></div>
                </div>
                <div style="font-size: 0.75em; color: #9ca3af; margin-top: 2px;">{trust_level}/5</div>
            </div>
            """, unsafe_allow_html=True)

        # "What I've Learned" section
        revealed = st.session_state.get("revealed_clues", {}).get(npc_key, [])
        if revealed:
            with st.expander(f"What I've Learned ({len(revealed)})"):
                for clue in revealed:
                    st.markdown(f"- {clue}")

        # Suggested question prompts
        _show_suggested_prompts(npc_key, npc)

    with chat_col:
        st.markdown("#### Conversation")
        conversation_container = st.container(border=True)

    # Show conversation history
    history = st.session_state.interview_history.get(npc_key, [])

    with conversation_container:
        if not history:
            st.caption("No messages yet. Start the interview below.")
        for msg in history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["content"])
            else:
                with st.chat_message("assistant", avatar=get_npc_avatar(npc)):
                    st.write(msg["content"])

    # Special handling for Nurse Mai (nurse_joy) - Rapport mechanic
    if npc_key == "nurse_joy":
        # Import outbreak_logic for rapport functions
        from outbreak_logic import update_nurse_rapport, check_nurse_rapport

        # Initialize rapport and show current status
        if 'nurse_rapport' not in st.session_state:
            st.session_state['nurse_rapport'] = 0
        if 'nurse_initial_dialogue_shown' not in st.session_state:
            st.session_state['nurse_initial_dialogue_shown'] = False

        # Show rapport status
        rapport = st.session_state['nurse_rapport']
        animal_q = st.session_state.get('nurse_animal_questions', 0)

        with chat_col:
            st.info(f"**Nurse Rapport:** {rapport} | **Animal Questions Asked:** {animal_q}/3")

        # Show initial dialogue choices if first interaction
        if not st.session_state['nurse_initial_dialogue_shown'] and len(history) == 0:
            with chat_col:
                st.markdown("---")
                st.markdown("**Nurse Mai looks up from her paperwork, clearly stressed and overwhelmed.**")
                st.markdown('"Why are you here now? I have so many patients to see..."')
                st.markdown("---")
                st.markdown("**How do you respond?**")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚨 'Show me the records. Now.'", key="nurse_demand", use_container_width=True):
                        result = update_nurse_rapport('demand', st.session_state)
                        history.append({"role": "user", "content": "'Show me the records. Now.'"})
                        history.append({"role": "assistant", "content": result['message']})
                        st.session_state.interview_history[npc_key] = history
                        st.session_state['nurse_initial_dialogue_shown'] = True
                        st.rerun()

                with col2:
                    if st.button("💚 'It looks busy here. Thank you for your work.'", key="nurse_empathize", use_container_width=True):
                        result = update_nurse_rapport('empathize', st.session_state)
                        history.append({"role": "user", "content": "'It looks busy here. Thank you for your work.'"})
                        history.append({"role": "assistant", "content": result['message']})
                        st.session_state.interview_history[npc_key] = history
                        st.session_state['nurse_initial_dialogue_shown'] = True
                        st.rerun()

                st.markdown("---")
            return  # Don't show chat input yet

        # Show pig clue if unlocked
        if (rapport > 20 or animal_q >= 3) and 'nurse_pig_clue_shown' not in st.session_state:
            with chat_col:
                st.success("**🐷 Nurse Mai sighs:** 'Fine. A few pig litters had abortions recently. Young farmers are careless.'")
            st.session_state['nurse_pig_clue_shown'] = True

        # Show records access status
        if rapport > 10:
            with chat_col:
                st.success("✅ **Records Access Granted** - You may now review the child register.")
        else:
            with chat_col:
                st.warning("🔒 **Records Access Denied** - Improve your rapport to access clinic records.")

    # Chat input
    with chat_col:
        with st.form(key=f"npc_chat_form_{npc_key}", clear_on_submit=True):
            prompt_key = f"npc_prompt_{npc_key}"
            st.session_state.setdefault(prompt_key, "")
            user_q = st.text_input(
                f"Ask {npc.get('name', 'NPC')} a question...",
                key=prompt_key,
            )
            submitted = st.form_submit_button("Send")

    if submitted and user_q:
        # Check for NPC unlock triggers
        unlock_notification = check_npc_unlock_triggers(user_q)

        # Track animal questions for nurse_joy
        if npc_key == "nurse_joy":
            from outbreak_logic import update_nurse_rapport
            animal_keywords = ['pig', 'pigs', 'livestock', 'animal', 'animals', 'abortion', 'abortions', 'sow', 'sows', 'litter', 'litters']
            if any(keyword in user_q.lower() for keyword in animal_keywords):
                update_nurse_rapport('animals', st.session_state)

        history.append({"role": "user", "content": user_q})
        st.session_state.interview_history[npc_key] = history

        with conversation_container:
            with st.chat_message("user"):
                st.write(user_q)

            with st.chat_message("assistant", avatar=get_npc_avatar(npc)):
                # Use streaming for faster perceived response
                reply = st.write_stream(stream_npc_response(npc_key, user_q))

        history.append({"role": "assistant", "content": reply})
        st.session_state.interview_history[npc_key] = history

        # Track revealed clues
        _extract_revealed_clues(npc_key, npc, reply)

        # Show unlock notification
        if unlock_notification:
            with chat_col:
                st.success(unlock_notification)

        st.rerun()


def render_location_actions(loc_key: str, actions: list):
    """Render action buttons for a location."""
    from state.resources import check_resources

    action_configs = {
        "review_clinic_records": {
            "label": "Review Clinic Records",
            "cost_time": TIME_COSTS.get("clinic_records_review", 2.0),
            "cost_budget": 0,
            "handler": "case_finding",
        },
        "view_hospital_records": {
            "label": "View Hospital Records",
            "cost_time": 0.5,
            "cost_budget": 0,
            "handler": "hospital_records",
        },
        "collect_pig_sample": {
            "label": "Collect Pig Serum Sample",
            "cost_time": TIME_COSTS.get("sample_collection", 1.0),
            "cost_budget": BUDGET_COSTS.get("lab_sample_animal", 35),
            "handler": "lab_sample",
            "sample_type": "pig_serum",
        },
        "collect_mosquito_sample": {
            "label": "Set Mosquito Trap",
            "cost_time": TIME_COSTS.get("sample_collection", 1.0),
            "cost_budget": BUDGET_COSTS.get("lab_sample_mosquito", 40),
            "handler": "lab_sample",
            "sample_type": "mosquito_pool",
        },
        "collect_water_sample": {
            "label": "Collect Water Sample",
            "cost_time": 0.5,
            "cost_budget": 20,
            "handler": "lab_sample",
            "sample_type": "water",
        },
        "collect_household_water_sample": {
            "label": "Collect Water Sample from Household Jar",
            "cost_time": 0.5,
            "cost_budget": 20,
            "handler": "lab_sample",
            "sample_type": "household_water",
        },
        "inspect_environment": {
            "label": "Environmental Inspection",
            "cost_time": TIME_COSTS.get("environmental_inspection", 2.0),
            "cost_budget": 0,
            "handler": "environment",
        },
        "view_village_profile": {
            "label": "View Village Profile",
            "cost_time": 0,
            "cost_budget": 0,
            "handler": "village_profile",
        },
        "collect_csf_sample": {
            "label": "Request CSF Sample",
            "cost_time": 0.5,
            "cost_budget": BUDGET_COSTS.get("lab_sample_human", 25),
            "handler": "lab_sample",
            "sample_type": "csf",
        },
        "collect_serum_sample": {
            "label": "Request Patient Serum",
            "cost_time": 0.5,
            "cost_budget": BUDGET_COSTS.get("lab_sample_human", 25),
            "handler": "lab_sample",
            "sample_type": "human_serum",
        },
        "view_lab_results": {
            "label": "View Lab Results",
            "cost_time": 0,
            "cost_budget": 0,
            "handler": "lab_results",
        },
        "submit_lab_samples": {
            "label": "Submit Samples for Testing",
            "cost_time": 0.5,
            "cost_budget": 0,
            "handler": "lab_submit",
        },
        "request_data": {
            "label": "Request Official Data",
            "cost_time": 0.5,
            "cost_budget": 0,
            "handler": "request_data",
        },
        "plan_interventions": {
            "label": "📝 Plan Interventions",
            "cost_time": 0,
            "cost_budget": 0,
            "handler": "interventions",
        },
        "view_nalu_child_register": {
            "label": "Review Nalu Child Register",
            "cost_time": 1.0,
            "cost_budget": 0,
            "handler": "nalu_child_register",
        },
        "view_ward_registry": {
            "label": "📋 View Ward Registry (30 days)",
            "cost_time": 1.0,
            "cost_budget": 0,
            "handler": "ward_registry",
        },
        "review_hospital_records": {
            "label": "📄 Review Medical Charts",
            "cost_time": 0.5,
            "cost_budget": 0,
            "handler": "hospital_charts",
        },
        "view_deep_dive_charts": {
            "label": "📊 View Deep-Dive Charts",
            "cost_time": 0.5,
            "cost_budget": 0,
            "handler": "deep_dive_charts",
        },
        "review_attendance_records": {
            "label": "📚 Review Attendance Records",
            "cost_time": 1.0,
            "cost_budget": 0,
            "handler": "attendance",
        },
        "review_tamu_records": {
            "label": "📝 Review Tamu Records",
            "cost_time": 0.5,
            "cost_budget": 0,
            "handler": "tamu_records",
        },
    }

    for action in actions:
        config = action_configs.get(action, {})
        if not config:
            continue

        label = config.get("label", action)
        cost_time = config.get("cost_time", 0)
        cost_budget = config.get("cost_budget", 0)

        # Show cost
        cost_str = format_resource_cost(cost_time, cost_budget)

        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button(label, key=f"action_{action}_{loc_key}", use_container_width=True):
                # Pre-check permissions for gated actions BEFORE spending resources
                handler = config.get("handler", "")
                if handler in ("hospital_charts", "hospital_records", "ward_registry", "deep_dive_charts"):
                    from npc.unlock import has_hospital_records_access
                    if not has_hospital_records_access():
                        # Don't spend resources — just show the denied modal
                        execute_location_action(action, config, loc_key)
                        continue
                if handler == "nalu_child_register":
                    from outbreak_logic import check_nurse_rapport
                    if not check_nurse_rapport(st.session_state):
                        # Don't spend resources — just show the denied message
                        execute_location_action(action, config, loc_key)
                        continue

                # Check resources
                can_proceed, msg = check_resources(cost_time, cost_budget)
                if can_proceed:
                    if cost_time > 0:
                        spend_time(cost_time, label)
                    if cost_budget > 0:
                        spend_budget(cost_budget, label)

                    # Execute handler
                    execute_location_action(action, config, loc_key)
                else:
                    st.error(msg)
        with col2:
            if cost_time > 0 or cost_budget > 0:
                st.caption(resource_preview(cost_time, cost_budget))
            else:
                st.caption("Free")


def execute_location_action(action: str, config: dict, loc_key: str):
    """Execute a location action and show the appropriate UI."""
    handler = config.get("handler", "")

    if handler == "case_finding":
        st.session_state.current_view = "casefinding"
        st.rerun()
    elif handler == "hospital_records":
        st.session_state.action_modal = "hospital_records"
        st.rerun()
    elif handler == "lab_sample":
        sample_type = config.get("sample_type", "unknown")
        st.session_state.action_modal = f"lab_sample_{sample_type}"
        st.rerun()
    elif handler == "environment":
        st.session_state.action_modal = "environment_inspection"
        st.rerun()
    elif handler == "village_profile":
        st.session_state.current_view = "villages"
        st.rerun()
    elif handler == "lab_results":
        st.session_state.current_view = "lab"
        st.rerun()
    elif handler == "lab_submit":
        st.session_state.current_view = "lab"
        st.rerun()
    elif handler == "interventions":
        st.session_state.current_view = "outcome"
        st.rerun()
    elif handler == "request_data":
        st.session_state.current_view = "descriptive"
        st.rerun()
    elif handler == "nalu_child_register":
        # Check if nurse permits access
        from outbreak_logic import check_nurse_rapport
        if check_nurse_rapport(st.session_state):
            st.session_state.current_view = "nalu_child_register"
            st.rerun()
        else:
            st.error("🔒 The nurse refuses access. 'Build better rapport first - show some respect for my time.'")
            st.rerun()
    elif handler == "ward_registry":
        st.session_state.action_modal = "ward_registry"
        st.rerun()
    elif handler == "hospital_charts":
        st.session_state.action_modal = "hospital_charts"
        st.rerun()
    elif handler == "deep_dive_charts":
        st.session_state.action_modal = "deep_dive_charts"
        st.rerun()
    elif handler == "attendance":
        st.session_state.action_modal = "attendance"
        st.rerun()
    elif handler == "tamu_records":
        st.session_state.action_modal = "tamu_records"
        st.rerun()


MOOD_CONFIG = {
    "cooperative": {"color": "#10b981", "border": "#059669", "label": "Friendly", "emoji": "\U0001f60a", "glow": "0 0 15px rgba(16,185,129,0.4)"},
    "neutral":     {"color": "#6b7280", "border": "#4b5563", "label": "Neutral",  "emoji": "\U0001f610", "glow": "none"},
    "wary":        {"color": "#f59e0b", "border": "#d97706", "label": "Cautious", "emoji": "\U0001f928", "glow": "0 0 15px rgba(245,158,11,0.3)"},
    "annoyed":     {"color": "#ef4444", "border": "#dc2626", "label": "Irritated","emoji": "\U0001f624", "glow": "0 0 15px rgba(239,68,68,0.3)"},
    "offended":    {"color": "#991b1b", "border": "#7f1d1d", "label": "Offended", "emoji": "\U0001f620", "glow": "0 0 20px rgba(153,27,27,0.4)"},
}


def render_npc_portrait_card(npc_key: str, npc: dict):
    """Render a styled NPC portrait card with mood indicator and trust bar."""
    npc_image_path = npc.get("image_path")
    emotion = st.session_state.npc_state.get(npc_key, {}).get("emotion", "neutral")
    trust = get_npc_trust(npc_key)
    mood = MOOD_CONFIG.get(emotion, MOOD_CONFIG["neutral"])

    # Normalize trust from [-3, 5] to [0, 100]
    trust_pct = max(0, min(100, ((trust + 3) / 8) * 100))

    # Show portrait image if available
    if npc_image_path and Path(npc_image_path).exists():
        st.image(npc_image_path, use_container_width=True)

    # Mood card HTML
    html = f"""
    <div class="npc-portrait-card" style="border: 3px solid {mood['border']}; box-shadow: {mood['glow']};">
        <div style="font-weight: 700; font-size: 1.1em;">{npc['name']}</div>
        <div style="font-size: 0.85em; color: #6b7280; margin-bottom: 6px;">{npc.get('role', '')}</div>
        <span class="mood-badge" style="background: {mood['color']};">{mood['emoji']} {mood['label']}</span>
        <div class="trust-bar-track">
            <div class="trust-bar-fill" style="width: {trust_pct}%; background: {mood['color']};"></div>
        </div>
        <div style="font-size: 0.75em; color: #9ca3af; margin-top: 4px;">Trust: {trust}/5</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_npc_chat(npc_key: str, npc: dict):
    """Render chat interface for an NPC at current location."""

    # Layout: portrait card on left, chat on right
    portrait_col, chat_col = st.columns([1, 3])

    with portrait_col:
        render_npc_portrait_card(npc_key, npc)
        # End conversation button under portrait
        if st.button("End Conversation", key="end_chat", use_container_width=True):
            st.session_state.current_npc = None
            st.rerun()

    with chat_col:
        default_avatar = "\U0001f9d1"
        st.markdown(f"### {npc.get('avatar', default_avatar)} {npc['name']}")
        st.caption(f"*{npc['role']}*")

    # Show conversation history
    history = st.session_state.interview_history.get(npc_key, [])

    for msg in history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant", avatar=get_npc_avatar(npc)):
                st.write(msg["content"])

    # Special handling for Nurse Mai (nurse_joy) - Rapport mechanic
    if npc_key == "nurse_joy":
        # Import outbreak_logic for rapport functions
        from outbreak_logic import update_nurse_rapport, check_nurse_rapport

        # Initialize rapport and show current status
        if 'nurse_rapport' not in st.session_state:
            st.session_state['nurse_rapport'] = 0
        if 'nurse_initial_dialogue_shown' not in st.session_state:
            st.session_state['nurse_initial_dialogue_shown'] = False

        # Show rapport status
        rapport = st.session_state['nurse_rapport']
        animal_q = st.session_state.get('nurse_animal_questions', 0)

        st.info(f"**Nurse Rapport:** {rapport} | **Animal Questions Asked:** {animal_q}/3")

        # Show initial dialogue choices if first interaction
        if not st.session_state['nurse_initial_dialogue_shown'] and len(history) == 0:
            st.markdown("---")
            st.markdown("**Nurse Mai looks up from her paperwork, clearly stressed and overwhelmed.**")
            st.markdown('"Why are you here now? I have so many patients to see..."')
            st.markdown("---")
            st.markdown("**How do you respond?**")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚨 'Show me the records. Now.'", key="nurse_demand", use_container_width=True):
                    result = update_nurse_rapport('demand', st.session_state)
                    history.append({"role": "user", "content": "'Show me the records. Now.'"})
                    history.append({"role": "assistant", "content": result['message']})
                    st.session_state.interview_history[npc_key] = history
                    st.session_state['nurse_initial_dialogue_shown'] = True
                    st.rerun()

            with col2:
                if st.button("💚 'It looks busy here. Thank you for your work.'", key="nurse_empathize", use_container_width=True):
                    result = update_nurse_rapport('empathize', st.session_state)
                    history.append({"role": "user", "content": "'It looks busy here. Thank you for your work.'"})
                    history.append({"role": "assistant", "content": result['message']})
                    st.session_state.interview_history[npc_key] = history
                    st.session_state['nurse_initial_dialogue_shown'] = True
                    st.rerun()

            st.markdown("---")
            return  # Don't show chat input yet

        # Show pig clue if unlocked
        if (rapport > 20 or animal_q >= 3) and 'nurse_pig_clue_shown' not in st.session_state:
            st.success("**🐷 Nurse Mai sighs:** 'Fine. A few pig litters had abortions recently. Young farmers are careless.'")
            st.session_state['nurse_pig_clue_shown'] = True

        # Show records access status
        if rapport > 10:
            st.success("✅ **Records Access Granted** - You may now review the child register.")
        else:
            st.warning("🔒 **Records Access Denied** - Improve your rapport to access clinic records.")

    # Trust indicator for non-nurse NPCs (portrait card already shows mood;
    # this is a compact inline reminder visible near the chat input)
    if npc_key != "nurse_joy":
        emotion = st.session_state.npc_state.get(npc_key, {}).get("emotion", "neutral")
        mood = MOOD_CONFIG.get(emotion, MOOD_CONFIG["neutral"])
        st.caption(f"**Rapport:** {mood['emoji']} {mood['label']} | **Trust:** {get_npc_trust(npc_key)}/5")

    # Chat input
    user_q = st.chat_input(f"Ask {npc['name']} a question...")
    if user_q:
        # Capture trust before interaction for comparison
        trust_before = get_npc_trust(npc_key)
        emotion_before = st.session_state.npc_state.get(npc_key, {}).get("emotion", "neutral")

        # Check for NPC unlock triggers
        unlock_notification = check_npc_unlock_triggers(user_q)

        # Track animal questions for nurse_joy
        if npc_key == "nurse_joy":
            from outbreak_logic import update_nurse_rapport
            animal_keywords = ['pig', 'pigs', 'livestock', 'animal', 'animals', 'abortion', 'abortions', 'sow', 'sows', 'litter', 'litters']
            if any(keyword in user_q.lower() for keyword in animal_keywords):
                update_nurse_rapport('animals', st.session_state)

        history.append({"role": "user", "content": user_q})
        st.session_state.interview_history[npc_key] = history

        with st.chat_message("user"):
            st.write(user_q)

        with st.chat_message("assistant", avatar=get_npc_avatar(npc)):
            # Use streaming for faster perceived response
            reply = st.write_stream(stream_npc_response(npc_key, user_q))

        history.append({"role": "assistant", "content": reply})
        st.session_state.interview_history[npc_key] = history

        # Track revealed clues
        _extract_revealed_clues(npc_key, npc, reply)

        # Show trust change feedback
        trust_after = get_npc_trust(npc_key)
        emotion_after = st.session_state.npc_state.get(npc_key, {}).get("emotion", "neutral")

        if trust_after > trust_before:
            st.toast(f"📈 Your rapport with {npc['name']} improved! (Trust: {trust_after})", icon="💚")
        elif trust_after < trust_before:
            st.toast(f"📉 Your rapport with {npc['name']} decreased. (Trust: {trust_after})", icon="⚠️")

        if emotion_after != emotion_before:
            emotion_emoji = {"cooperative": "😊", "neutral": "😐", "wary": "🤨", "annoyed": "😤", "offended": "😠"}.get(emotion_after, "😐")
            st.info(f"{npc['name']} now seems **{emotion_after}** {emotion_emoji}")

        # Show unlock notification
        if unlock_notification:
            st.success(unlock_notification)

        # Check achievements after every NPC interaction
        newly_earned = achievements.check_achievements(st.session_state)
        achievements.show_achievement_toasts(newly_earned)

        st.rerun()
