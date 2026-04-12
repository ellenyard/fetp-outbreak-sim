"""NPC unlock triggers and hospital records access helpers.

Manages unlocking new NPCs based on user questions, and tracks
hospital records access permissions.
"""

import streamlit as st


def check_npc_unlock_triggers(user_input: str) -> str:
    """
    Check if user's question should unlock additional NPCs.
    Returns a notification message if unlock occurred, else empty string.
    """
    text = user_input.lower()
    notification = ""

    # Animal/pig triggers -> unlock Vet Amina
    animal_triggers = ['animal', 'pig', 'livestock', 'pigs', 'swine', 'cattle', 'farm animal', 'piglet']
    if any(trigger in text for trigger in animal_triggers):
        st.session_state.questions_asked_about.add('animals')
        if not st.session_state.vet_unlocked:
            st.session_state.vet_unlocked = True
            st.session_state.one_health_triggered = True
            if 'vet_amina' not in st.session_state.npcs_unlocked:
                st.session_state.npcs_unlocked.append('vet_amina')
            notification = "\U0001f513 **New Contact Unlocked:** Vet Supatra (District Veterinary Officer) - Your question about animals opened a One Health perspective!"

    # Mosquito/environment triggers -> unlock Mr. Osei
    env_triggers = ['mosquito', 'mosquitoes', 'vector', 'breeding', 'standing water', 'environment', 'rice paddy', 'irrigation', 'wetland']
    if any(trigger in text for trigger in env_triggers):
        st.session_state.questions_asked_about.add('environment')
        if not st.session_state.env_officer_unlocked:
            st.session_state.env_officer_unlocked = True
            st.session_state.one_health_triggered = True
            if 'mr_osei' not in st.session_state.npcs_unlocked:
                st.session_state.npcs_unlocked.append('mr_osei')
            notification = "\U0001f513 **New Contact Unlocked:** Mr. Nguyen (Environmental Health Officer) - Your question about environmental factors opened a new perspective!"

    # Healer triggers (for earlier cases)
    healer_triggers = ['traditional', 'healer', 'clinic', 'private', 'early case', 'first case', 'before hospital']
    if any(trigger in text for trigger in healer_triggers):
        st.session_state.questions_asked_about.add('traditional')
        if 'healer_marcus' not in st.session_state.npcs_unlocked:
            st.session_state.npcs_unlocked.append('healer_marcus')
            notification = "\U0001f513 **New Contact Unlocked:** Healer Somchai (Private Clinic) - You discovered there may be unreported cases!"

    return notification


# =========================
# RECORDS ACCESS HELPERS
# =========================

HOSPITAL_RECORDS_UNLOCK_KEYWORDS = ("hospital", "ward")


def should_unlock_hospital_records(unlock_flag: str) -> bool:
    if not unlock_flag:
        return False
    if unlock_flag in ("records_access", "tran_permission_granted"):
        return True
    lower_flag = unlock_flag.lower()
    return "record" in lower_flag and any(key in lower_flag for key in HOSPITAL_RECORDS_UNLOCK_KEYWORDS)


def has_hospital_records_access() -> bool:
    if st.session_state.get("tran_permission", False):
        return True
    unlock_flags = st.session_state.get("unlock_flags", {})
    if unlock_flags.get("records_access"):
        return True
    return any(
        enabled and should_unlock_hospital_records(flag)
        for flag, enabled in unlock_flags.items()
    )


def get_hospital_records_contact_name() -> str:
    npc_truth = st.session_state.truth.get("npc_truth", {})
    for npc in npc_truth.values():
        unlock_flag = npc.get("unlocks")
        if should_unlock_hospital_records(unlock_flag):
            return npc.get("name", "the hospital director")
    return "the hospital director"
