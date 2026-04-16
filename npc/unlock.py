"""NPC unlock triggers and hospital records access helpers.

Manages unlocking new NPCs based on user questions, and tracks
hospital records access permissions.
"""

import streamlit as st


# Scenario-specific One Health NPC mappings
_ONE_HEALTH_NPCS = {
    "lepto_rivergate": {
        "vet_key": "dr_villareal",
        "vet_name": "Dr. Ernesto Villareal (Private Veterinarian)",
        "env_key": "engr_ramon",
        "env_name": "Engr. Ramon Holt (DRRM Officer)",
        "healer_key": "pastor_elijah",
        "healer_name": "Pastor Elijah Gonzales (Faith Healer)",
    },
    # AES / Sidero Valley scenario
    "aes_sidero_valley": {
        "vet_key": "vet_amina",
        "vet_name": "Vet Supatra (District Veterinary Officer)",
        "env_key": "mr_osei",
        "env_name": "Mr. Nguyen (Environmental Health Officer)",
        "healer_key": "healer_marcus",
        "healer_name": "Healer Somchai (Private Clinic)",
    },
}


def _get_one_health_npcs() -> dict:
    """Return the One Health NPC mapping for the current scenario."""
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    return _ONE_HEALTH_NPCS.get(scenario_id, _ONE_HEALTH_NPCS["aes_sidero_valley"])


def check_npc_unlock_triggers(user_input: str) -> str:
    """
    Check if user's question should unlock additional NPCs.
    Returns a notification message if unlock occurred, else empty string.
    """
    text = user_input.lower()
    notification = ""
    oh = _get_one_health_npcs()

    # Animal/livestock triggers -> unlock veterinarian
    animal_triggers = ['animal', 'pig', 'livestock', 'pigs', 'swine', 'cattle',
                       'farm animal', 'piglet', 'rodent', 'rat', 'rats']
    if any(trigger in text for trigger in animal_triggers):
        st.session_state.questions_asked_about.add('animals')
        if not st.session_state.vet_unlocked:
            st.session_state.vet_unlocked = True
            st.session_state.one_health_triggered = True
            if oh["vet_key"] not in st.session_state.npcs_unlocked:
                st.session_state.npcs_unlocked.append(oh["vet_key"])
            notification = (
                f"\U0001f513 **New Contact Unlocked:** {oh['vet_name']} "
                f"- Your question about animals opened a One Health perspective!"
            )

    # Environment triggers -> unlock environment/DRRM officer
    env_triggers = ['mosquito', 'mosquitoes', 'vector', 'breeding',
                    'standing water', 'environment', 'rice paddy',
                    'irrigation', 'wetland', 'flood', 'drainage',
                    'water source', 'contamination']
    if any(trigger in text for trigger in env_triggers):
        st.session_state.questions_asked_about.add('environment')
        if not st.session_state.env_officer_unlocked:
            st.session_state.env_officer_unlocked = True
            st.session_state.one_health_triggered = True
            if oh["env_key"] not in st.session_state.npcs_unlocked:
                st.session_state.npcs_unlocked.append(oh["env_key"])
            notification = (
                f"\U0001f513 **New Contact Unlocked:** {oh['env_name']} "
                f"- Your question about environmental factors opened a new perspective!"
            )

    # Healer/traditional medicine triggers
    healer_triggers = ['traditional', 'healer', 'faith', 'prayer',
                       'private clinic', 'early case', 'first case',
                       'before hospital', 'pastor', 'minister']
    if any(trigger in text for trigger in healer_triggers):
        st.session_state.questions_asked_about.add('traditional')
        if oh["healer_key"] not in st.session_state.npcs_unlocked:
            st.session_state.npcs_unlocked.append(oh["healer_key"])
            notification = (
                f"\U0001f513 **New Contact Unlocked:** {oh['healer_name']} "
                f"- You discovered there may be unreported cases!"
            )

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
