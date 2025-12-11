import streamlit as st
import anthropic
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from je_logic import (
    load_truth_data,
    generate_full_population,
    generate_study_dataset,
    process_lab_order,
    evaluate_interventions,
    check_day_prerequisites,
)

# =========================
# INITIALIZATION
# =========================

@st.cache_data
def load_truth_and_population(data_dir: str = "."):
    """Load truth data and generate a full population."""
    truth = load_truth_data(data_dir=data_dir)
    villages_df = truth["villages"]
    households_seed = truth["households_seed"]
    individuals_seed = truth["individuals_seed"]

    households_full, individuals_full = generate_full_population(
        villages_df, households_seed, individuals_seed
    )
    truth["households"] = households_full
    truth["individuals"] = individuals_full
    return truth


def init_session_state():
    if "truth" not in st.session_state:
        # CSV/JSON files are in the repo root right now
        st.session_state.truth = load_truth_and_population(data_dir=".")

    # Alert page logic (Day 0)
    st.session_state.setdefault("alert_acknowledged", False)

    if "current_day" not in st.session_state:
        # 1–5 for the investigation days
        st.session_state.current_day = 1

    if "current_view" not in st.session_state:
        # Start on alert screen until acknowledged
        st.session_state.current_view = "alert"

    # If alert is not acknowledged, force the view to "alert"
    if not st.session_state.alert_acknowledged:
        st.session_state.current_view = "alert"
    else:
        # If alert already acknowledged but view is still "alert", move to overview
        if st.session_state.current_view == "alert":
            st.session_state.current_view = "overview"

    # Resources
    st.session_state.setdefault("budget", 1000)
    st.session_state.setdefault("lab_credits", 20)

    # Decisions and artifacts
    if "decisions" not in st.session_state:
        st.session_state.decisions = {
            "case_definition": None,
            "case_definition_text": "",
            "study_design": None,
            "mapped_columns": [],
            "sample_size": {"cases": 15, "controls_per_case": 2},
            "lab_orders": [],
            "questionnaire_raw": [],
            "final_diagnosis": "",
            "recommendations": [],
        }

    st.session_state.setdefault("generated_dataset", None)
    st.session_state.setdefault("lab_results", [])
    st.session_state.setdefault("lab_samples_submitted", [])
    st.session_state.setdefault("interview_history", {})
    st.session_state.setdefault("revealed_clues", {})
    st.session_state.setdefault("current_npc", None)
    st.session_state.setdefault("unlock_flags", {})

    # NPC emotional state & memory summary (per NPC)
    # structure: npc_state[npc_key] = {
    #   "emotion": "neutral" | "cooperative" | "wary" | "annoyed" | "offended",
    #   "interaction_count": int,
    #   "rude_count": int,
    #   "polite_count": int,
    # }
    st.session_state.setdefault("npc_state", {})

    # Flags used for day progression
    st.session_state.setdefault("case_definition_written", False)
    st.session_state.setdefault("questionnaire_submitted", False)
    st.session_state.setdefault("descriptive_analysis_done", False)

    # Track whether user has opened the line list/epi view at least once (for Day 1)
    st.session_state.setdefault("line_list_viewed", False)

    # For messaging when advance-day fails
    st.session_state.setdefault("advance_missing_tasks", [])
    
    # Initial hypotheses (Day 1)
    st.session_state.setdefault("initial_hypotheses", [])
    st.session_state.setdefault("hypotheses_documented", False)
    
    # Investigation notebook
    st.session_state.setdefault("notebook_entries", [])
    
    # NPC unlocking system (One Health)
    st.session_state.setdefault("npcs_unlocked", ["dr_chen", "nurse_joy", "mama_kofi", "foreman_rex", "teacher_grace"])
    st.session_state.setdefault("one_health_triggered", False)
    st.session_state.setdefault("vet_unlocked", False)
    st.session_state.setdefault("env_officer_unlocked", False)
    st.session_state.setdefault("questions_asked_about", set())
    
    # Clinic records and case finding (Day 1)
    st.session_state.setdefault("clinic_records_reviewed", False)
    st.session_state.setdefault("selected_clinic_cases", [])
    st.session_state.setdefault("case_finding_score", None)
    
    # Descriptive epidemiology
    st.session_state.setdefault("descriptive_epi_viewed", False)


# =========================
# UTILITY FUNCTIONS
# =========================

def build_epidemiologic_context(truth: dict) -> str:
    """Short summary of the outbreak from truth tables."""
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"][["village_id", "village_name"]]

    hh_vil = households.merge(villages, on="village_id", how="left")
    merged = individuals.merge(
        hh_vil[["hh_id", "village_name"]], on="hh_id", how="left"
    )

    cases = merged[merged["symptomatic_AES"] == True]
    total_cases = len(cases)

    if total_cases == 0:
        return "No symptomatic AES cases have been assigned in the truth model."

    village_counts = cases["village_name"].value_counts().to_dict()

    bins = [0, 4, 14, 49, 120]
    labels = ["0–4", "5–14", "15–49", "50+"]
    age_groups = pd.cut(cases["age"], bins=bins, labels=labels, right=True)
    age_counts = age_groups.value_counts().to_dict()

    context = (
        f"There are currently about {total_cases} symptomatic AES cases in the district. "
        f"Cases by village: {village_counts}. "
        f"Cases by age group: {age_counts}. "
        "Most cases are children and come from villages with rice paddies and pigs."
    )
    return context


def build_npc_data_context(npc_key: str, truth: dict) -> str:
    """NPC-specific data context based on their data_access scope."""
    npc = truth["npc_truth"][npc_key]
    data_access = npc.get("data_access")

    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"][["village_id", "village_name"]]

    hh_vil = households.merge(villages, on="village_id", how="left")
    merged = individuals.merge(
        hh_vil[["hh_id", "village_name"]], on="hh_id", how="left"
    )

    epi_context = build_epidemiologic_context(truth)

    if data_access == "hospital_cases":
        cases = merged[merged["symptomatic_AES"] == True]
        summary = cases.groupby("village_name").size().to_dict()
        return (
            epi_context
            + " As hospital director, you mainly see hospitalized AES cases. "
              f"You know current hospitalized cases come from these villages: {summary}."
        )

    if data_access == "triage_logs":
        cases = merged[merged["symptomatic_AES"] == True]
        earliest = cases["onset_date"].min()
        latest = cases["onset_date"].max()
        return (
            epi_context
            + " As triage nurse, you mostly notice who walks in first. "
              f"You saw the first AES cases between {earliest} and {latest}."
        )

    if data_access == "private_clinic":
        cases = merged[
            (merged["symptomatic_AES"] == True)
            & (merged["village_name"] == "Nalu Village")
        ]
        n = len(cases)
        return (
            epi_context
            + f" As a private healer, you have personally seen around {n} early AES-like illnesses "
              "from households near pig farms and rice paddies in Nalu."
        )

    if data_access == "school_attendance":
        school_age = merged[(merged["age"] >= 5) & (merged["age"] <= 18)]
        cases = school_age[school_age["symptomatic_AES"] == True]
        n = len(cases)
        by_village = cases["village_name"].value_counts().to_dict()
        return (
            epi_context
            + f" As school principal, you mostly know about school-age children. "
              f"You know of AES cases among your students: {n} total, by village: {by_village}."
        )

    if data_access == "vet_surveillance":
        lab = truth["lab_samples"]
        pigs = lab[lab["sample_type"] == "pig_serum"]
        pos = pigs[pigs["true_JEV_positive"] == True]
        by_village = pos["linked_village_id"].value_counts().to_dict()
        return (
            epi_context
            + " As the district veterinary officer, you track pig health. "
              f"Recent pig tests suggest JEV circulation in villages: {by_village}."
        )

    if data_access == "environmental_data":
        env = truth["environment_sites"]
        high = env[env["breeding_index"] == "high"]
        sites = high["site_id"].tolist()
        return (
            epi_context
            + " As environmental health officer, you survey breeding sites. "
              f"You know of high mosquito breeding around these sites: {sites}."
        )

    return epi_context


def analyze_user_tone(user_input: str) -> str:
    """
    Very simple tone detector: 'polite', 'rude', or 'neutral'.
    Used to update emotional state.
    """
    text = user_input.lower()

    polite_words = ["please", "thank you", "thanks", "appreciate", "grateful"]
    rude_words = [
        "stupid", "idiot", "useless", "incompetent", "what's wrong with you",
        "you people", "this is your fault", "do your job", "now!", "right now"
    ]

    if any(w in text for w in rude_words):
        return "rude"
    if any(w in text for w in polite_words):
        return "polite"
    # Very shouty messages
    if text.isupper() and len(text) > 5:
        return "rude"
    return "neutral"


def update_npc_emotion(npc_key: str, user_tone: str):
    """
    Strong emotional model:
    - Rude tone escalates emotion quickly to 'annoyed' or 'offended'
    - Polite tone causes mild softening
    - Neutral slowly heals annoyance over time
    """
    state = st.session_state.npc_state.setdefault(
        npc_key,
        {
            "emotion": "neutral",
            "interaction_count": 0,
            "rude_count": 0,
            "polite_count": 0,
        },
    )

    state["interaction_count"] += 1

    emotion_order = ["cooperative", "neutral", "wary", "annoyed", "offended"]

    def shift(current, steps):
        idx = emotion_order.index(current)
        idx = max(0, min(len(emotion_order) - 1, idx + steps))
        return emotion_order[idx]

    if user_tone == "polite":
        state["polite_count"] += 1
        # polite helps but not too fast
        state["emotion"] = shift(state["emotion"], -1)

    elif user_tone == "rude":
        state["rude_count"] += 1
        # rude pushes 2 steps more negative — very reactive
        state["emotion"] = shift(state["emotion"], +2)

    else:  # neutral tone
        # slow natural recovery only after several interactions
        if state["emotion"] in ["annoyed", "offended"] and state["interaction_count"] % 4 == 0:
            state["emotion"] = shift(state["emotion"], -1)

    st.session_state.npc_state[npc_key] = state
    return state


def describe_emotional_state(state: dict) -> str:
    """
    Turn emotion + history into a short description for the system prompt.
    This is what the LLM sees about how they feel toward the trainee.
    """
    emotion = state["emotion"]
    rude = state["rude_count"]
    polite = state["polite_count"]

    base = ""
    if emotion == "cooperative":
        base = "You currently feel friendly and cooperative toward the investigation team."
    elif emotion == "neutral":
        base = "You feel neutral toward the investigation team."
    elif emotion == "wary":
        base = "You feel cautious and slightly guarded. You will answer but watch your words."
    elif emotion == "annoyed":
        base = (
            "You feel irritated and impatient with the team. "
            "You give shorter answers and avoid volunteering extra information unless they ask clearly."
        )
    else:  # offended
        base = (
            "You feel offended by how the team has treated you. "
            "You answer briefly and share only what seems necessary for public health."
        )

    if rude >= 2 and emotion in ["annoyed", "offended"]:
        base += " You remember previous rude or disrespectful questions."

    if polite >= 2 and emotion in ["neutral", "wary"]:
        base += " They've also been respectful at times, which softens you a little."

    return base


def classify_question_scope(user_input: str) -> str:
    """
    Much stricter categorization:
    - 'greeting' : any greeting, no outbreak info allowed
    - 'broad'    : ONLY explicit broad requests like 'tell me everything'
    - 'narrow'   : direct, specific outbreak questions
    """
    text = user_input.strip().lower()

    # pure greetings → absolutely no outbreak info
    greeting_words = ["hi", "hello", "good morning", "good afternoon", "good evening"]
    if text in greeting_words or text.startswith("hi ") or text.startswith("hello "):
        return "greeting"

    # extremely explicit broad prompts only
    broad_phrases = [
        "tell me everything",
        "tell me what you know",
        "explain the whole situation",
        "give me an overview",
        "summarize everything",
        "what do you know about this outbreak",
    ]
    if any(text == p for p in broad_phrases):
        return "broad"

    # vague or small-talk questions should be treated as greeting
    vague_phrases = [
        "how are things",
        "how is everything",
        "what's going on",
        "what is going on",
        "what is happening",
        "how have you been",
        "how's your day",
    ]
    if any(p in text for p in vague_phrases):
        return "greeting"

    return "narrow"


def check_npc_unlock_triggers(user_input: str) -> str:
    """
    Check if user's question should unlock additional NPCs.
    Returns a notification message if unlock occurred, else empty string.
    """
    text = user_input.lower()
    notification = ""
    
    # Animal/pig triggers → unlock Vet Amina
    animal_triggers = ['animal', 'pig', 'livestock', 'pigs', 'swine', 'cattle', 'farm animal', 'piglet']
    if any(trigger in text for trigger in animal_triggers):
        st.session_state.questions_asked_about.add('animals')
        if not st.session_state.vet_unlocked:
            st.session_state.vet_unlocked = True
            st.session_state.one_health_triggered = True
            if 'vet_amina' not in st.session_state.npcs_unlocked:
                st.session_state.npcs_unlocked.append('vet_amina')
            notification = "🔓 **New Contact Unlocked:** Vet Amina (District Veterinary Officer) - Your question about animals opened a One Health perspective!"
    
    # Mosquito/environment triggers → unlock Mr. Osei
    env_triggers = ['mosquito', 'mosquitoes', 'vector', 'breeding', 'standing water', 'environment', 'rice paddy', 'irrigation', 'wetland']
    if any(trigger in text for trigger in env_triggers):
        st.session_state.questions_asked_about.add('environment')
        if not st.session_state.env_officer_unlocked:
            st.session_state.env_officer_unlocked = True
            st.session_state.one_health_triggered = True
            if 'mr_osei' not in st.session_state.npcs_unlocked:
                st.session_state.npcs_unlocked.append('mr_osei')
            notification = "🔓 **New Contact Unlocked:** Mr. Osei (Environmental Health Officer) - Your question about environmental factors opened a new perspective!"
    
    # Healer triggers (for earlier cases)
    healer_triggers = ['traditional', 'healer', 'clinic', 'private', 'early case', 'first case', 'before hospital']
    if any(trigger in text for trigger in healer_triggers):
        st.session_state.questions_asked_about.add('traditional')
        if 'healer_marcus' not in st.session_state.npcs_unlocked:
            st.session_state.npcs_unlocked.append('healer_marcus')
            notification = "🔓 **New Contact Unlocked:** Healer Marcus (Private Clinic) - You discovered there may be unreported cases!"
    
    return notification


def get_npc_response(npc_key: str, user_input: str) -> str:
    """Call Anthropic using npc_truth + epidemiologic context, with memory & emotional state."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ Anthropic API key missing."

    truth = st.session_state.truth
    npc_truth = truth["npc_truth"][npc_key]

    # Conversation history = memory
    history = st.session_state.interview_history.get(npc_key, [])
    meaningful_questions = sum(1 for m in history if m["role"] == "user")

    # Determine question scope & user tone
    question_scope = classify_question_scope(user_input)
    user_tone = analyze_user_tone(user_input)
    npc_state = update_npc_emotion(npc_key, user_tone)
    emotional_description = describe_emotional_state(npc_state)

    epi_context = build_npc_data_context(npc_key, truth)

    if npc_key not in st.session_state.revealed_clues:
        st.session_state.revealed_clues[npc_key] = []

    system_prompt = f"""
You are {npc_truth['name']}, the {npc_truth['role']} in Sidero Valley.

Personality:
{npc_truth['personality']}

Your current emotional state toward the investigation team:
{emotional_description}

The investigator has asked about {meaningful_questions} meaningful questions so far in this conversation.

Outbreak context (for your awareness; DO NOT recite this unless directly asked about those details):
{epi_context}

EARLY CONVERSATION RULE:
- If the investigator has asked fewer than 2 meaningful questions so far, you should NOT share multiple outbreak facts at once.
- Keep your early answers short and focused until they show clear, professional inquiry.

INFORMATION DISCLOSURE RULES BASED ON EMOTION:
- If you feel COOPERATIVE: you may volunteer small helpful context when appropriate.
- If you feel NEUTRAL: answer normally but do NOT volunteer extra details.
- If you feel WARY: be cautious; give minimal direct answers and avoid side details.
- If you feel ANNOYED: give short answers and avoid volunteering information unless they explicitly ask.
- If you feel OFFENDED: respond very briefly and share only essential facts needed for public health.

CONVERSATION BEHAVIOR:
- Speak like a real person from this district: natural, informal, sometimes imperfect.
- Vary sentence length and structure; avoid sounding scripted or overly polished.
- You remember what has already been discussed with this investigator.
- You may briefly refer back to earlier questions ("Like I mentioned before...") instead of repeating everything.
- If the user is polite and respectful, you tend to be warmer and more open.
- If the user is rude or demanding, you become more guarded and give shorter, cooler answers.
- If the user seems confused, you can slow down and clarify.
- You may occasionally repeat yourself or wander slightly off-topic, then pull yourself back.
- You never dump all your knowledge at once unless the user clearly asks something like "tell me everything you know."

QUESTION SCOPE:
- If the user just greets you, respond with a normal greeting and ask how you can help. Do NOT share outbreak facts yet.
- If the user asks a narrow, specific question, answer in 1–3 sentences.
- If the user asks a broad question like "what do you know" or "tell me everything", you may answer in more detail (up to about 5–7 sentences) and provide a thoughtful overview.

ALWAYS REVEAL (gradually, not all at once):
{npc_truth['always_reveal']}

CONDITIONAL CLUES:
- Reveal a conditional clue ONLY when the user's question clearly relates to that topic.
- Work clues into natural speech; do NOT list them as bullet points.
{npc_truth['conditional_clues']}

RED HERRINGS:
- You may mention these occasionally, but do NOT contradict the core truth:
{npc_truth['red_herrings']}

UNKNOWN:
- If the user asks about these topics, you must say you do not know:
{npc_truth['unknowns']}

INFORMATION RULES:
- Never invent new outbreak details (case counts, test results, locations) beyond what is implied in the context.
- If you are unsure, say you are not certain.
"""

    # Decide which conditional clues are allowed in this answer
    lower_q = user_input.lower()
    conditional_to_use = []
    for keyword, clue in npc_truth.get("conditional_clues", {}).items():
        # Require keyword substring AND a question mark for a clearer "ask"
        if keyword.lower() in lower_q and "?" in lower_q and clue not in st.session_state.revealed_clues[npc_key]:
            conditional_to_use.append(clue)
            st.session_state.revealed_clues[npc_key].append(clue)

    # For narrow questions, keep at most 1 new conditional clue
    if question_scope != "broad" and len(conditional_to_use) > 1:
        conditional_to_use = conditional_to_use[:1]

    if conditional_to_use:
        system_prompt += (
            "\n\nThe user has just asked about topics that connect to some NEW ideas you can reveal. "
            "Work the following ideas naturally into your answer if they fit the question:\n"
            + "\n".join(f"- {c}" for c in conditional_to_use)
        )

    client = anthropic.Anthropic(api_key=api_key)

    msgs = [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": user_input})

    resp = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=400,
        system=system_prompt,
        messages=msgs,
    )

    text = resp.content[0].text

    # Unlock flags (One Health unlocks)
    unlock_flag = npc_truth.get("unlocks")
    if unlock_flag:
        st.session_state.unlock_flags[unlock_flag] = True

    return text


# =========================
# CLINIC RECORDS FOR CASE FINDING
# =========================

def generate_clinic_records():
    """
    Generate messy, handwritten-style clinic records.
    Mix of AES cases and unrelated illnesses.
    Returns list of record dicts.
    """
    import random
    random.seed(42)
    
    # True AES cases that should be found (6-8 cases)
    true_aes_cases = [
        {
            "record_id": "NHC-0034",
            "date": "2-Jun",
            "patient": "Kwame A., male",
            "age": "7 yrs",
            "village": "Nalu",
            "complaint": "fever 3 days, confusion, jerking movements",
            "notes": "mother says child was playing near rice fields. referred to hosp.",
            "is_aes": True
        },
        {
            "record_id": "NHC-0041",
            "date": "4-Jun", 
            "patient": "Esi M.",
            "age": "5",
            "village": "Nalu vill.",
            "complaint": "High fever, not responding to name, shaking",
            "notes": "very sick. Family has pigs. Sent to district hosp URGENT",
            "is_aes": True
        },
        {
            "record_id": "NHC-0047",
            "date": "5 June",
            "patient": "Yaw K. (boy)",
            "age": "9 years",
            "village": "Kabwe",
            "complaint": "fever, severe headache, vomited x3, then seizure in clinic",
            "notes": "Lives nr paddy fields. Admitted for obs then transferred",
            "is_aes": True
        },
        {
            "record_id": "NHC-0052",
            "date": "6/6",
            "patient": "Abena F.",
            "age": "4y",
            "village": "Nalu",
            "complaint": "feverish, drowsy, mother says 'not herself', stiff neck?",
            "notes": "neck stiffness uncertain - child crying. watch closely",
            "is_aes": True
        },
        {
            "record_id": "NHC-0058",
            "date": "7-June",
            "patient": "Kofi B.",
            "age": "11",
            "village": "Kabwe village",
            "complaint": "fever x4 days, confusion today, parents v. worried",
            "notes": "walks past pig coop to school daily. Referred to hosp",
            "is_aes": True
        },
        {
            "record_id": "NHC-0063",
            "date": "8 Jun",
            "patient": "Adwoa S., F",
            "age": "6 yr",
            "village": "Nalu",
            "complaint": "fever, then became unresponsive, jerking arms",
            "notes": "no net at home. near rice paddies. URGENT referral",
            "is_aes": True
        },
        {
            "record_id": "NHC-0071",
            "date": "9-Jun",
            "patient": "male child (name unclear)",
            "age": "~8",
            "village": "Nalu area",
            "complaint": "brought in fitting, high fever, confusion",
            "notes": "family farms rice + keeps pigs. transferred to DH",
            "is_aes": True
        },
    ]
    
    # Non-AES cases (noise - 18-22 records)
    non_aes_cases = [
        {
            "record_id": "NHC-0031",
            "date": "1-Jun",
            "patient": "Akua D.",
            "age": "34",
            "village": "Tamu",
            "complaint": "cough x2 weeks, some fever",
            "notes": "?TB - refer for sputum",
            "is_aes": False
        },
        {
            "record_id": "NHC-0032",
            "date": "1-Jun",
            "patient": "Mensah K.",
            "age": "45 yrs",
            "village": "Kabwe",
            "complaint": "painful urination, fever",
            "notes": "UTI. Gave antibiotics",
            "is_aes": False
        },
        {
            "record_id": "NHC-0033",
            "date": "2-Jun",
            "patient": "baby girl (Serwaa)",
            "age": "8 months",
            "village": "Nalu",
            "complaint": "diarrhea x3 days, not feeding well",
            "notes": "ORS given. mother counseled on feeding",
            "is_aes": False
        },
        {
            "record_id": "NHC-0035",
            "date": "2-Jun",
            "patient": "Owusu P.",
            "age": "52",
            "village": "Tamu",
            "complaint": "knee pain, swelling",
            "notes": "arthritis. gave pain meds",
            "is_aes": False
        },
        {
            "record_id": "NHC-0036",
            "date": "3-Jun",
            "patient": "Ama T.",
            "age": "28",
            "village": "Kabwe",
            "complaint": "pregnant, routine ANC visit",
            "notes": "28 weeks. All normal.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0037",
            "date": "3-Jun",
            "patient": "child (Kweku)",
            "age": "3",
            "village": "Nalu",
            "complaint": "fever, runny nose, cough",
            "notes": "common cold. supportive care",
            "is_aes": False
        },
        {
            "record_id": "NHC-0038",
            "date": "3 June",
            "patient": "Fatima A.",
            "age": "19",
            "village": "Tamu",
            "complaint": "headache, body pains, fever",
            "notes": "? malaria. RDT positive. Gave ACT.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0039",
            "date": "4-Jun",
            "patient": "elderly man (Nana K.)",
            "age": "~70",
            "village": "Kabwe",
            "complaint": "difficulty breathing, swollen legs",
            "notes": "heart failure? referred to hospital",
            "is_aes": False
        },
        {
            "record_id": "NHC-0040",
            "date": "4-Jun",
            "patient": "Adjoa M.",
            "age": "25",
            "village": "Nalu",
            "complaint": "skin rash, itching x1 week",
            "notes": "fungal infection. Gave cream.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0042",
            "date": "4-Jun",
            "patient": "Yaw A.",
            "age": "6",
            "village": "Tamu",
            "complaint": "ear pain, fever",
            "notes": "otitis media. antibiotics given",
            "is_aes": False
        },
        {
            "record_id": "NHC-0043",
            "date": "5-Jun",
            "patient": "Comfort O.",
            "age": "31",
            "village": "Kabwe",
            "complaint": "lower abdominal pain",
            "notes": "? PID. referred for further eval",
            "is_aes": False
        },
        {
            "record_id": "NHC-0044",
            "date": "5-Jun",
            "patient": "Kofi M.",
            "age": "40",
            "village": "Nalu",
            "complaint": "cut on hand from farming, infected",
            "notes": "wound cleaned, dressed, tetanus given",
            "is_aes": False
        },
        {
            "record_id": "NHC-0045",
            "date": "5-Jun",
            "patient": "Grace A.",
            "age": "15",
            "village": "Tamu",
            "complaint": "painful menstruation",
            "notes": "dysmenorrhea. pain meds given",
            "is_aes": False
        },
        {
            "record_id": "NHC-0046",
            "date": "5 Jun",
            "patient": "infant (Kwabena)",
            "age": "4 mo",
            "village": "Kabwe",
            "complaint": "immunization visit",
            "notes": "vaccines given. growing well.",
            "is_aes": False
        },
        {
            "record_id": "NHC-0048",
            "date": "6-Jun",
            "patient": "Akosua B.",
            "age": "22",
            "village": "Nalu",
            "complaint": "vomiting, diarrhea since yesterday",
            "notes": "gastroenteritis. ORS, observe",
            "is_aes": False
        },
        {
            "record_id": "NHC-0049",
            "date": "6-Jun",
            "patient": "Kwame O.",
            "age": "55",
            "village": "Tamu",
            "complaint": "high BP at community screening",
            "notes": "BP 160/95. started on meds. f/u 2 weeks",
            "is_aes": False
        },
        {
            "record_id": "NHC-0050",
            "date": "6-Jun",
            "patient": "child (Ama)",
            "age": "2 yrs",
            "village": "Kabwe",
            "complaint": "not eating, mild fever, irritable",
            "notes": "teething? no serious illness. reassured mother",
            "is_aes": False
        },
        {
            "record_id": "NHC-0051",
            "date": "6/6",
            "patient": "Joseph K.",
            "age": "38",
            "village": "Nalu",
            "complaint": "back pain x1 month",
            "notes": "muscle strain from farming. rest + pain meds",
            "is_aes": False
        },
        {
            "record_id": "NHC-0053",
            "date": "7-Jun",
            "patient": "Afia S.",
            "age": "12",
            "village": "Tamu",
            "complaint": "fever, joint pains, headache",
            "notes": "malaria RDT neg. ? viral illness. observe",
            "is_aes": False
        },
        {
            "record_id": "NHC-0054",
            "date": "7-Jun",
            "patient": "Nana A.",
            "age": "65",
            "village": "Kabwe",
            "complaint": "blurry vision, eye pain",
            "notes": "? cataracts. referred to eye clinic",
            "is_aes": False
        },
        {
            "record_id": "NHC-0055",
            "date": "7-Jun",
            "patient": "Charity M.",
            "age": "29",
            "village": "Nalu",
            "complaint": "breast lump, worried",
            "notes": "small mobile lump. referred for mammo",
            "is_aes": False
        },
        {
            "record_id": "NHC-0056",
            "date": "7 Jun",
            "patient": "boy (Yaw)",
            "age": "10",
            "village": "Kabwe",
            "complaint": "fell from tree, arm pain",
            "notes": "? fracture. splinted, sent to hosp for xray",
            "is_aes": False
        },
        {
            "record_id": "NHC-0057",
            "date": "7-Jun",
            "patient": "Esi K.",
            "age": "8",
            "village": "Tamu",
            "complaint": "fever, vomiting, abdominal pain",
            "notes": "? acute abdomen. referred to hospital",
            "is_aes": False
        },
        {
            "record_id": "NHC-0059",
            "date": "8-Jun",
            "patient": "adult male",
            "age": "~30",
            "village": "Nalu",
            "complaint": "productive cough, night sweats",
            "notes": "TB suspect. sputum collected",
            "is_aes": False
        },
        {
            "record_id": "NHC-0060",
            "date": "8-Jun",
            "patient": "Abena K.",
            "age": "48",
            "village": "Kabwe",
            "complaint": "fatigue, weight loss, thirst",
            "notes": "? diabetes. referred for glucose test",
            "is_aes": False
        },
        {
            "record_id": "NHC-0061",
            "date": "8 Jun",
            "patient": "infant girl",
            "age": "6 mo",
            "village": "Tamu",
            "complaint": "rash on face and body",
            "notes": "eczema. gave moisturizer advice",
            "is_aes": False
        },
        {
            "record_id": "NHC-0062",
            "date": "8-Jun",
            "patient": "Kwesi A.",
            "age": "44",
            "village": "Nalu",
            "complaint": "epigastric pain after eating",
            "notes": "? peptic ulcer. gave antacids. diet advice",
            "is_aes": False
        },
    ]
    
    # Combine and shuffle
    all_records = true_aes_cases + non_aes_cases
    random.shuffle(all_records)
    
    return all_records


def render_clinic_record(record: dict, show_checkbox: bool = True) -> bool:
    """
    Render a single clinic record in a handwritten style.
    Returns True if selected as potential case.
    """
    # Simulate messy handwriting with varied formatting
    style = """
    <div style="
        background: #fffef0;
        border: 1px solid #d4c99e;
        border-radius: 2px;
        padding: 12px;
        margin: 8px 0;
        font-family: 'Comic Sans MS', 'Segoe Script', cursive;
        font-size: 14px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        transform: rotate({rotation}deg);
    ">
        <div style="color: #666; font-size: 11px; border-bottom: 1px dashed #ccc; padding-bottom: 4px; margin-bottom: 8px;">
            <strong>{record_id}</strong> &nbsp;|&nbsp; {date}
        </div>
        <div><strong>Pt:</strong> {patient} &nbsp; <strong>Age:</strong> {age}</div>
        <div><strong>Village:</strong> {village}</div>
        <div style="margin-top: 6px;"><strong>Complaint:</strong> {complaint}</div>
        <div style="margin-top: 6px; color: #555; font-style: italic;">Notes: {notes}</div>
    </div>
    """
    
    import random
    rotation = random.uniform(-0.5, 0.5)
    
    html = style.format(
        rotation=rotation,
        record_id=record.get("record_id", "???"),
        date=record.get("date", "???"),
        patient=record.get("patient", "???"),
        age=record.get("age", "?"),
        village=record.get("village", "?"),
        complaint=record.get("complaint", ""),
        notes=record.get("notes", "")
    )
    
    st.markdown(html, unsafe_allow_html=True)
    
    if show_checkbox:
        return st.checkbox(
            f"Add to line list", 
            key=f"select_{record['record_id']}",
            value=record['record_id'] in st.session_state.get('selected_clinic_cases', [])
        )
    return False


# =========================
# VISUALS: MAP, LINE LIST, EPI CURVE
# =========================

def make_village_map(truth: dict) -> go.Figure:
    """Simple schematic map of villages with pig density and rice paddies."""
    villages = truth["villages"].copy()
    # Assign simple coordinates for display
    villages = villages.reset_index(drop=True)
    villages["x"] = np.arange(len(villages))
    villages["y"] = 0

    # Marker size from population, color from pig_density
    size = 20 + 5 * (villages["population_size"] / villages["population_size"].max())
    color_map = {"high": "red", "medium": "orange", "low": "yellow", "none": "green"}
    colors = [color_map.get(str(d).lower(), "gray") for d in villages["pig_density"]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=villages["x"],
            y=villages["y"],
            mode="markers+text",
            text=villages["village_name"],
            textposition="top center",
            marker=dict(size=size, color=colors, line=dict(color="black", width=1)),
            hovertext=[
                f"{row['village_name']}<br>Pigs: {row['pig_density']}<br>Rice paddies: {row['has_rice_paddies']}"
                for _, row in villages.iterrows()
            ],
            hoverinfo="text",
        )
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        title="Schematic Map of Sidero Valley",
        showlegend=False,
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def get_initial_cases(truth: dict, n: int = 12) -> pd.DataFrame:
    """Return a small line list of earliest AES cases."""
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"][["village_id", "village_name"]]

    hh_vil = households.merge(villages, on="village_id", how="left")
    merged = individuals.merge(
        hh_vil[["hh_id", "village_name"]], on="hh_id", how="left"
    )

    cases = merged[merged["symptomatic_AES"] == True].copy()
    if "onset_date" in cases.columns:
        cases = cases.sort_values("onset_date")
    return cases.head(n)[
        ["person_id", "age", "sex", "village_name", "onset_date", "severe_neuro", "outcome"]
    ]


def make_epi_curve(truth: dict) -> go.Figure:
    """Epi curve of AES cases by onset date."""
    individuals = truth["individuals"]
    cases = individuals[individuals["symptomatic_AES"] == True].copy()
    if "onset_date" not in cases.columns:
        fig = go.Figure()
        fig.update_layout(title="Epi curve not available")
        return fig

    counts = cases.groupby("onset_date").size().reset_index(name="cases")
    counts = counts.sort_values("onset_date")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=counts["onset_date"],
            y=counts["cases"],
        )
    )
    fig.update_layout(
        title="AES cases by onset date",
        xaxis_title="Onset date",
        yaxis_title="Number of cases",
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


# =========================
# UI COMPONENTS
# =========================

def sidebar_navigation():
    st.sidebar.title("Sidero Valley JE Simulation")

    if not st.session_state.alert_acknowledged:
        # Before the alert is acknowledged, keep sidebar simple
        st.sidebar.markdown("**Status:** Awaiting outbreak alert acknowledgment.")
        st.sidebar.info("Review the alert on the main screen to begin the investigation.")
        return

    st.sidebar.markdown(
        f"**Day:** {st.session_state.current_day} / 5\n\n"
        f"**Budget:** ${st.session_state.budget}\n"
        f"**Lab credits:** {st.session_state.lab_credits}"
    )

    # Progress indicator
    st.sidebar.markdown("### Progress")
    for day in range(1, 6):
        if day < st.session_state.current_day:
            status = "✅"
        elif day == st.session_state.current_day:
            status = "🟡"
        else:
            status = "⬜"
        st.sidebar.markdown(f"{status} Day {day}")

    st.sidebar.markdown("---")

    # Navigation - day-appropriate options
    labels = ["Overview / Briefing", "Case Finding", "Descriptive Epi", "Interviews", "Spot Map", "Data & Study Design", "Lab & Environment", "Interventions & Outcome"]
    internal = ["overview", "casefinding", "descriptive", "interviews", "spotmap", "study", "lab", "outcome"]
    
    if st.session_state.current_view in internal:
        current_idx = internal.index(st.session_state.current_view)
    else:
        current_idx = 0

    choice = st.sidebar.radio("Go to:", labels, index=current_idx)
    st.session_state.current_view = internal[labels.index(choice)]

    st.sidebar.markdown("---")
    
    # Investigation Notebook
    with st.sidebar.expander("📓 Investigation Notebook"):
        st.caption("Record your observations, questions, and insights here.")
        
        new_note = st.text_area("Add a note:", height=80, key="new_note_input")
        if st.button("Save Note", key="save_note_btn"):
            if new_note.strip():
                from datetime import datetime
                entry = {
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "day": st.session_state.current_day,
                    "note": new_note.strip()
                }
                st.session_state.notebook_entries.append(entry)
                st.success("Note saved!")
                st.rerun()
        
        if st.session_state.notebook_entries:
            st.markdown("**Your Notes:**")
            for entry in reversed(st.session_state.notebook_entries[-10:]):  # Show last 10
                st.markdown(f"*Day {entry['day']} @ {entry['timestamp']}*")
                st.markdown(f"> {entry['note']}")
                st.markdown("---")
    
    # One Health Progress Tracker
    with st.sidebar.expander("🌍 One Health Integration"):
        st.markdown(f"{'✅' if st.session_state.vet_unlocked else '🔒'} Veterinary perspective")
        st.markdown(f"{'✅' if st.session_state.env_officer_unlocked else '🔒'} Environmental perspective")
        
        # Check for animal/mosquito samples
        has_animal_samples = any('pig' in s.get('sample_type', '') for s in st.session_state.lab_samples_submitted)
        has_vector_samples = any('mosquito' in s.get('sample_type', '') for s in st.session_state.lab_samples_submitted)
        
        st.markdown(f"{'✅' if has_animal_samples else '🔒'} Animal samples collected")
        st.markdown(f"{'✅' if has_vector_samples else '🔒'} Vector samples collected")

    st.sidebar.markdown("---")
    
    # Advance day button (at bottom)
    if st.session_state.current_day < 5:
        if st.sidebar.button(f"⏭️ Advance to Day {st.session_state.current_day + 1}", use_container_width=True):
            can_advance, missing = check_day_prerequisites(st.session_state.current_day, st.session_state)
            if can_advance:
                st.session_state.current_day += 1
                st.session_state.advance_missing_tasks = []
                st.rerun()
            else:
                st.session_state.advance_missing_tasks = missing
                st.sidebar.warning("Cannot advance yet. See missing tasks on Overview.")
    else:
        st.sidebar.success("📋 Final Day - Complete your briefing!")


def day_briefing_text(day: int) -> str:
    if day == 1:
        return (
            "Day 1 focuses on detection and initial description of the outbreak. "
            "Your goals are to understand the basic pattern (time, place, person), "
            "draft a working case definition, and begin hypothesis-generating interviews."
        )
    if day == 2:
        return (
            "Day 2 focuses on hypothesis generation and study design. "
            "You will design an analytic study and develop a questionnaire to collect data."
        )
    if day == 3:
        return (
            "Day 3 is dedicated to data cleaning and analysis. "
            "You will work with your generated dataset to describe the outbreak and identify risk factors."
        )
    if day == 4:
        return (
            "Day 4 focuses on laboratory and environmental investigations. "
            "You will decide which human, animal, and environmental samples to collect and how to test them."
        )
    return (
        "Day 5 focuses on recommendations and communication. "
        "You will integrate all evidence and present your findings and interventions to leadership."
    )


def day_task_list(day: int):
    """Show tasks and whether they are completed."""
    st.markdown("### Key tasks for today")
    if day == 1:
        st.checkbox("Review initial cases", value=st.session_state.line_list_viewed, disabled=True)
        st.checkbox("Review clinic records for additional cases", value=st.session_state.clinic_records_reviewed, disabled=True)
        st.checkbox("Perform descriptive epidemiology", value=st.session_state.descriptive_epi_viewed, disabled=True)
        st.checkbox("Write a working case definition", value=st.session_state.case_definition_written, disabled=True)
        st.checkbox("Document initial hypotheses", value=st.session_state.hypotheses_documented, disabled=True)
        st.checkbox("Complete at least 2 interviews", value=len(st.session_state.interview_history) >= 2, disabled=True)
    elif day == 2:
        st.checkbox("Choose a study design", value=st.session_state.decisions.get("study_design") is not None, disabled=True)
        st.checkbox("Submit questionnaire", value=st.session_state.questionnaire_submitted, disabled=True)
        st.checkbox("Generate study dataset", value=st.session_state.generated_dataset is not None, disabled=True)
    elif day == 3:
        st.checkbox("Complete descriptive analysis", value=st.session_state.descriptive_analysis_done, disabled=True)
    elif day == 4:
        st.checkbox("Submit at least one lab sample", value=len(st.session_state.lab_samples_submitted) > 0, disabled=True)
    else:
        st.checkbox("Enter final diagnosis", value=bool(st.session_state.decisions.get("final_diagnosis")), disabled=True)
        st.checkbox("Record main recommendations", value=bool(st.session_state.decisions.get("recommendations")), disabled=True)

    if st.session_state.advance_missing_tasks:
        st.warning("To advance to the next day, you still need to:\n- " + "\n- ".join(st.session_state.advance_missing_tasks))

# =========================
# VIEWS
# =========================

def view_alert():
    """Day 0: Alert call intro screen."""
    st.title("📞 Outbreak Alert – Sidero Valley")

    st.markdown(
        """
You are on duty at the District Health Office when a call comes in from the regional hospital.

> **"We’ve admitted several children with sudden fever, seizures, and confusion.  
> Most are from the rice-growing villages in Sidero Valley. We’re worried this might be the start of something bigger."**

Within the last 48 hours:
- Multiple children with acute encephalitis syndrome (AES) have been hospitalized  
- Most are from Nalu and Kabwe villages  
- No obvious foodborne event or large gathering has been identified  

Your team has been asked to investigate, using a One Health approach.
"""
    )

    st.info(
        "When you’re ready, begin the investigation. You’ll move through the steps of an outbreak investigation over five simulated days."
    )

    if st.button("Begin investigation"):
        st.session_state.alert_acknowledged = True
        st.session_state.current_day = 1
        st.session_state.current_view = "overview"


def view_overview():
    truth = st.session_state.truth

    st.title("JE Outbreak Investigation – Sidero Valley")
    st.subheader(f"Day {st.session_state.current_day} briefing")

    st.markdown(day_briefing_text(st.session_state.current_day))

    day_task_list(st.session_state.current_day)

    st.markdown("---")
    st.markdown("### Situation overview")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Line list (initial AES cases)")
        line_list = get_initial_cases(truth)
        st.dataframe(line_list)
        st.session_state.line_list_viewed = True

    with col2:
        st.markdown("#### Epi curve")
        epi_fig = make_epi_curve(truth)
        st.plotly_chart(epi_fig, use_container_width=True)

    st.markdown("### Map of Sidero Valley")
    map_fig = make_village_map(truth)
    st.plotly_chart(map_fig, use_container_width=True)
    
    # Day 1: Case Definition and Initial Hypotheses
    if st.session_state.current_day == 1:
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📝 Case Definition")
            
            with st.form("case_definition_form"):
                st.markdown("**Clinical criteria:**")
                clinical = st.text_area("What symptoms/signs define a case?", height=80)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    person = st.text_input("**Person:** Who? (age, characteristics)")
                with col_b:
                    place = st.text_input("**Place:** Where?")
                
                time_period = st.text_input("**Time:** When?")
                
                if st.form_submit_button("Save Case Definition"):
                    full_def = f"Clinical: {clinical}\nPerson: {person}\nPlace: {place}\nTime: {time_period}"
                    st.session_state.decisions["case_definition_text"] = full_def
                    st.session_state.decisions["case_definition"] = {"clinical_AES": True}
                    st.session_state.case_definition_written = True
                    st.success("✅ Case definition saved!")
            
            if st.session_state.case_definition_written:
                st.info("✓ Case definition recorded")
        
        with col2:
            st.markdown("### 💡 Initial Hypotheses")
            st.caption("Based on what you know so far, what might be causing this outbreak?")
            
            with st.form("hypotheses_form"):
                h1 = st.text_input("Hypothesis 1:")
                h2 = st.text_input("Hypothesis 2:")
                h3 = st.text_input("Hypothesis 3:")
                h4 = st.text_input("Hypothesis 4 (optional):")
                
                if st.form_submit_button("Save Hypotheses"):
                    hypotheses = [h for h in [h1, h2, h3, h4] if h.strip()]
                    st.session_state.initial_hypotheses = hypotheses
                    st.session_state.hypotheses_documented = True
                    st.success(f"✅ {len(hypotheses)} hypotheses saved!")
            
            if st.session_state.hypotheses_documented:
                st.info(f"✓ {len(st.session_state.initial_hypotheses)} hypotheses recorded")


def view_interviews():
    truth = st.session_state.truth
    npc_truth = truth["npc_truth"]

    st.header("👥 Interviews")
    st.info(f"💰 Budget: ${st.session_state.budget} | Interview community members and officials to gather information.")

    # Group NPCs by availability
    available_npcs = []
    locked_npcs = []
    
    for npc_key, npc in npc_truth.items():
        if npc_key in st.session_state.npcs_unlocked:
            available_npcs.append((npc_key, npc))
        else:
            locked_npcs.append((npc_key, npc))
    
    # Show available NPCs
    st.markdown("### Available Contacts")
    cols = st.columns(3)
    for i, (npc_key, npc) in enumerate(available_npcs):
        with cols[i % 3]:
            interviewed = npc_key in st.session_state.interview_history
            status = "✓ Interviewed" if interviewed else ""
            
            st.markdown(f"**{npc['avatar']} {npc['name']}** {status}")
            st.caption(f"{npc['role']} — Cost: ${npc['cost']}")
            
            btn_label = "Continue" if interviewed else "Talk"
            if st.button(f"{btn_label}", key=f"btn_{npc_key}"):
                cost = 0 if interviewed else npc.get("cost", 0)
                if st.session_state.budget >= cost:
                    if not interviewed:
                        st.session_state.budget -= cost
                    st.session_state.current_npc = npc_key
                    st.session_state.interview_history.setdefault(npc_key, [])
                    st.rerun()
                else:
                    st.error("Insufficient budget for this interview.")
    
    # Show locked NPCs (without hints about how to unlock)
    if locked_npcs:
        st.markdown("### Other Contacts")
        st.caption("Some contacts may become available as your investigation progresses.")
        cols = st.columns(3)
        for i, (npc_key, npc) in enumerate(locked_npcs):
            with cols[i % 3]:
                st.markdown(f"**🔒 {npc['name']}**")
                st.caption(f"{npc['role']}")
                st.caption("*Not yet available*")

    # Active conversation
    npc_key = st.session_state.current_npc
    if npc_key and npc_key in npc_truth:
        npc = npc_truth[npc_key]
        st.markdown("---")
        st.subheader(f"Talking to {npc['name']} ({npc['role']})")
        
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("🔙 End Interview"):
                st.session_state.current_npc = None
                st.rerun()

        history = st.session_state.interview_history.get(npc_key, [])
        for msg in history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["content"])
            else:
                with st.chat_message("assistant", avatar=npc["avatar"]):
                    st.write(msg["content"])

        user_q = st.chat_input("Ask your question...")
        if user_q:
            # Check for NPC unlock triggers BEFORE getting response
            unlock_notification = check_npc_unlock_triggers(user_q)
            
            history.append({"role": "user", "content": user_q})
            st.session_state.interview_history[npc_key] = history

            with st.chat_message("user"):
                st.write(user_q)

            with st.chat_message("assistant", avatar=npc["avatar"]):
                with st.spinner("..."):
                    reply = get_npc_response(npc_key, user_q)
                st.write(reply)
            
            history.append({"role": "assistant", "content": reply})
            st.session_state.interview_history[npc_key] = history
            
            # Show unlock notification if any
            if unlock_notification:
                st.success(unlock_notification)
                st.rerun()


def view_case_finding():
    """View for reviewing clinic records and finding additional cases."""
    st.header("🔍 Case Finding - Clinic Records Review")
    
    st.markdown("""
    You've obtained permission to review records from the **Nalu Health Center**.
    Look through these handwritten clinic notes to identify potential AES cases 
    that may not have been reported to the district hospital.
    
    **Your task:** Review each record and select any that might be related to the outbreak.
    Consider: fever, neurological symptoms (confusion, seizures, altered consciousness), 
    and geographic/temporal clustering.
    """)
    
    st.info("💡 Tip: Not every fever is AES. Look for the combination of fever AND neurological symptoms.")
    
    # Generate clinic records
    if 'clinic_records' not in st.session_state:
        st.session_state.clinic_records = generate_clinic_records()
    
    records = st.session_state.clinic_records
    
    # Show records in columns
    st.markdown("---")
    st.markdown("### 📋 Nalu Health Center - Patient Register (June 2025)")
    
    col1, col2 = st.columns(2)
    
    selected = []
    for i, record in enumerate(records):
        with col1 if i % 2 == 0 else col2:
            render_clinic_record(record, show_checkbox=False)
            is_selected = st.checkbox(
                f"Potential AES case",
                key=f"clinic_select_{record['record_id']}",
                value=record['record_id'] in st.session_state.selected_clinic_cases
            )
            if is_selected:
                selected.append(record['record_id'])
    
    st.markdown("---")
    
    # Summary and submission
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"**Selected records:** {len(selected)}")
        if selected:
            st.caption(", ".join(selected))
    
    with col2:
        if st.button("Submit Case Finding", type="primary"):
            st.session_state.selected_clinic_cases = selected
            st.session_state.clinic_records_reviewed = True
            
            # Calculate score
            true_positives = sum(1 for rid in selected 
                               for r in records if r['record_id'] == rid and r.get('is_aes'))
            false_positives = len(selected) - true_positives
            
            # Count total true AES cases
            total_aes = sum(1 for r in records if r.get('is_aes'))
            false_negatives = total_aes - true_positives
            
            st.session_state.case_finding_score = {
                'true_positives': true_positives,
                'false_positives': false_positives,
                'false_negatives': false_negatives,
                'total_aes': total_aes,
                'selected': len(selected)
            }
            
            st.success(f"✅ Case finding complete! You identified {true_positives} of {total_aes} potential AES cases.")
            
            if false_positives > 0:
                st.warning(f"⚠️ {false_positives} record(s) you selected may not be AES cases.")
            if false_negatives > 0:
                st.info(f"📝 {false_negatives} potential AES case(s) were missed. Review records with fever + neurological symptoms.")
            
            st.rerun()
    
    # Show previous score if available
    if st.session_state.case_finding_score:
        score = st.session_state.case_finding_score
        with st.expander("📊 Your Case Finding Results"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("True Positives", score['true_positives'])
            with col2:
                st.metric("False Positives", score['false_positives'])
            with col3:
                st.metric("Missed Cases", score['false_negatives'])
            
            sensitivity = score['true_positives'] / score['total_aes'] * 100 if score['total_aes'] > 0 else 0
            st.progress(sensitivity / 100)
            st.caption(f"Sensitivity: {sensitivity:.0f}% ({score['true_positives']}/{score['total_aes']} AES cases identified)")


def view_descriptive_epi():
    """View for descriptive epidemiology analysis."""
    st.header("📈 Descriptive Epidemiology")
    
    st.session_state.descriptive_epi_viewed = True
    
    truth = st.session_state.truth
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"]
    
    # Get all symptomatic cases
    cases = individuals[individuals["symptomatic_AES"] == True].copy()
    
    # Merge with location info
    hh_vil = households.merge(villages[["village_id", "village_name"]], on="village_id", how="left")
    cases = cases.merge(hh_vil[["hh_id", "village_name", "village_id"]], on="hh_id", how="left")
    
    st.markdown("""
    Descriptive epidemiology summarizes the outbreak by **Person**, **Place**, and **Time**.
    This helps characterize who is affected and generate hypotheses about the cause.
    """)
    
    st.markdown("---")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Cases", len(cases))
    with col2:
        deaths = len(cases[cases['outcome'] == 'died'])
        cfr = deaths / len(cases) * 100 if len(cases) > 0 else 0
        st.metric("Deaths", deaths, f"CFR: {cfr:.1f}%")
    with col3:
        median_age = cases['age'].median()
        st.metric("Median Age", f"{median_age:.0f} years")
    with col4:
        date_range = f"{cases['onset_date'].min()} to {cases['onset_date'].max()}"
        st.metric("Date Range", date_range)
    
    st.markdown("---")
    
    # Three columns for Person, Place, Time
    tab1, tab2, tab3 = st.tabs(["👤 Person", "📍 Place", "📅 Time"])
    
    with tab1:
        st.markdown("### Person Characteristics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Age Distribution")
            
            # Age histogram
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=cases['age'],
                nbinsx=15,
                marker_color='#3498db'
            ))
            fig.update_layout(
                xaxis_title="Age (years)",
                yaxis_title="Number of cases",
                height=300,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Age group table
            bins = [0, 4, 9, 14, 19, 49, 100]
            labels = ['0-4', '5-9', '10-14', '15-19', '20-49', '50+']
            cases['age_group'] = pd.cut(cases['age'], bins=bins, labels=labels, right=True)
            age_table = cases['age_group'].value_counts().sort_index()
            
            st.markdown("**Cases by Age Group:**")
            age_df = pd.DataFrame({
                'Age Group': age_table.index,
                'Cases': age_table.values,
                '%': (age_table.values / len(cases) * 100).round(1)
            })
            st.dataframe(age_df, hide_index=True)
        
        with col2:
            st.markdown("#### Sex Distribution")
            
            sex_counts = cases['sex'].value_counts()
            
            fig = go.Figure(data=[go.Pie(
                labels=sex_counts.index,
                values=sex_counts.values,
                marker_colors=['#3498db', '#e74c3c']
            )])
            fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("**Cases by Sex:**")
            for sex, count in sex_counts.items():
                pct = count / len(cases) * 100
                st.markdown(f"- {sex}: {count} ({pct:.1f}%)")
            
            st.markdown("#### Outcomes")
            outcome_counts = cases['outcome'].value_counts()
            for outcome, count in outcome_counts.items():
                pct = count / len(cases) * 100
                st.markdown(f"- {outcome}: {count} ({pct:.1f}%)")
    
    with tab2:
        st.markdown("### Place - Geographic Distribution")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Cases by Village")
            
            village_counts = cases['village_name'].value_counts()
            
            fig = go.Figure(data=[go.Bar(
                x=village_counts.index,
                y=village_counts.values,
                marker_color=['#e74c3c', '#f39c12', '#27ae60'][:len(village_counts)]
            )])
            fig.update_layout(
                xaxis_title="Village",
                yaxis_title="Number of cases",
                height=300,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### Attack Rates by Village")
            
            # Calculate attack rates
            village_pop = villages.set_index('village_name')['population_size'].to_dict()
            
            attack_rates = []
            for village in village_counts.index:
                pop = village_pop.get(village, 500)
                cases_n = village_counts[village]
                ar = cases_n / pop * 1000
                attack_rates.append({
                    'Village': village,
                    'Cases': cases_n,
                    'Population': pop,
                    'Attack Rate (per 1000)': round(ar, 1)
                })
            
            ar_df = pd.DataFrame(attack_rates)
            st.dataframe(ar_df, hide_index=True)
            
            st.markdown("#### Village Characteristics")
            st.dataframe(
                villages[['village_name', 'has_rice_paddies', 'pig_density', 'JE_vacc_coverage']],
                hide_index=True
            )
    
    with tab3:
        st.markdown("### Time - Epidemic Curve")
        
        # Epi curve
        if 'onset_date' in cases.columns:
            counts = cases.groupby('onset_date').size().reset_index(name='cases')
            counts = counts.sort_values('onset_date')
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=counts['onset_date'],
                y=counts['cases'],
                marker_color='#e74c3c'
            ))
            fig.update_layout(
                xaxis_title="Onset Date",
                yaxis_title="Number of Cases",
                height=350,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Temporal Summary:**")
                st.markdown(f"- First case onset: {cases['onset_date'].min()}")
                st.markdown(f"- Last case onset: {cases['onset_date'].max()}")
                st.markdown(f"- Peak date: {counts.loc[counts['cases'].idxmax(), 'onset_date']}")
            
            with col2:
                st.markdown("**Epi Curve Interpretation:**")
                st.markdown("""
                - **Point source:** Sharp rise and fall
                - **Propagated:** Multiple peaks
                - **Continuous:** Plateau pattern
                """)
        
        # Cases by village over time
        st.markdown("#### Cases by Village Over Time")
        if 'onset_date' in cases.columns:
            pivot = cases.groupby(['onset_date', 'village_name']).size().unstack(fill_value=0)
            
            fig = go.Figure()
            colors = {'Nalu Village': '#e74c3c', 'Kabwe Village': '#f39c12', 'Tamu Village': '#27ae60'}
            for col in pivot.columns:
                fig.add_trace(go.Bar(
                    x=pivot.index,
                    y=pivot[col],
                    name=col,
                    marker_color=colors.get(col, '#3498db')
                ))
            
            fig.update_layout(
                barmode='stack',
                xaxis_title="Onset Date",
                yaxis_title="Number of Cases",
                height=300,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Interpretation prompts
    with st.expander("🤔 Descriptive Epi Interpretation Questions"):
        st.markdown("""
        **Person:**
        - What age groups are most affected? What does this suggest?
        - Is there a sex difference? If so, what might explain it?
        
        **Place:**
        - Which villages have the highest attack rates?
        - What do the affected villages have in common?
        - What might explain the geographic pattern?
        
        **Time:**
        - What type of epidemic curve does this look like?
        - What does the timing suggest about the incubation period?
        - Is the outbreak ongoing or resolving?
        
        **Synthesis:**
        - Based on person, place, and time, what hypotheses can you generate?
        - What additional information would help narrow down the cause?
        """)


def view_study_design():
    st.header("📊 Data & Study Design")

    # Case definition
    st.markdown("### Step 1: Case Definition")
    text = st.text_area(
        "Write your working case definition:",
        value=st.session_state.decisions.get("case_definition_text", ""),
        height=120,
    )
    if st.button("Save Case Definition"):
        st.session_state.decisions["case_definition_text"] = text
        st.session_state.decisions["case_definition"] = {"clinical_AES": True}
        st.session_state.case_definition_written = True
        st.success("Case definition saved.")

    # Study design
    st.markdown("### Step 2: Study Design")
    sd_type = st.radio("Choose a study design:", ["Case-control", "Retrospective cohort"])
    if sd_type == "Case-control":
        st.session_state.decisions["study_design"] = {"type": "case_control"}
    else:
        st.session_state.decisions["study_design"] = {"type": "cohort"}

    # Questionnaire
    st.markdown("### Step 3: Questionnaire")
    st.caption("List the key questions or variables you plan to include (one per line).")
    q_text = st.text_area(
        "Questionnaire items:",
        value="\n".join(st.session_state.decisions.get("questionnaire_raw", [])),
        height=160,
    )
    if st.button("Save Questionnaire"):
        lines = [ln for ln in q_text.splitlines() if ln.strip()]
        st.session_state.decisions["questionnaire_raw"] = lines
        # je_logic will map these strings → specific columns using keyword rules
        st.session_state.decisions["mapped_columns"] = lines
        st.session_state.questionnaire_submitted = True
        st.success("Questionnaire saved.")

    # Dataset generation
    st.markdown("### Step 4: Generate Simulated Study Dataset")
    if st.button("Generate Dataset"):
        truth = st.session_state.truth
        df = generate_study_dataset(
            truth["individuals"], truth["households"], st.session_state.decisions
        )
        st.session_state.generated_dataset = df
        st.session_state.descriptive_analysis_done = True  # simple proxy
        st.success("Dataset generated. Preview below; export for analysis as needed.")
        st.dataframe(df.head())


def view_lab_and_environment():
    st.header("🧪 Lab & Environment")

    st.markdown(
        "Order lab tests and environmental investigations. "
        "This simple interface demonstrates how orders flow into `process_lab_order()`."
    )

    truth = st.session_state.truth
    villages = truth["villages"]

    col1, col2, col3 = st.columns(3)
    with col1:
        sample_type = st.selectbox(
            "Sample type",
            ["human_CSF", "human_serum", "pig_serum", "mosquito_pool"],
        )
    with col2:
        village_id = st.selectbox(
            "Village",
            villages["village_id"],
            format_func=lambda vid: villages.set_index("village_id").loc[vid, "village_name"],
        )
    with col3:
        test = st.selectbox(
            "Test",
            ["JE_IgM_CSF", "JE_IgM_serum", "JE_PCR_mosquito", "JE_Ab_pig"],
        )

    source_description = st.text_input("Source description (e.g., 'Case from Nalu')", "")

    if st.button("Submit lab order"):
        order = {
            "sample_type": sample_type,
            "village_id": village_id,
            "test": test,
            "source_description": source_description or "Unspecified source",
        }
        result = process_lab_order(order, truth["lab_samples"])
        st.session_state.lab_results.append(result)
        st.session_state.lab_samples_submitted.append(order)
        st.session_state.lab_credits -= result.get("cost", 0)
        st.success(
            f"Lab order submitted. Result: {result['result']} "
            f"(turnaround {result['days_to_result']} days)."
        )

    if st.session_state.lab_results:
        st.markdown("### Lab results so far")
        st.dataframe(pd.DataFrame(st.session_state.lab_results))


def view_spot_map():
    """Geographic spot map of cases."""
    st.header("📍 Spot Map - Geographic Distribution of Cases")
    
    truth = st.session_state.truth
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"]
    
    # Get symptomatic cases
    cases = individuals[individuals["symptomatic_AES"] == True].copy()
    
    if len(cases) == 0:
        st.warning("No cases to display on map.")
        return
    
    # Merge with household and village info
    hh_vil = households.merge(villages[["village_id", "village_name"]], on="village_id", how="left")
    cases = cases.merge(hh_vil[["hh_id", "village_name", "village_id"]], on="hh_id", how="left")
    
    # Assign coordinates with jitter for visualization
    village_coords = {
        'V1': {'lat': 5.55, 'lon': -0.20, 'name': 'Nalu Village'},
        'V2': {'lat': 5.52, 'lon': -0.15, 'name': 'Kabwe Village'},
        'V3': {'lat': 5.58, 'lon': -0.12, 'name': 'Tamu Village'}
    }
    
    # Add coordinates with jitter
    np.random.seed(42)
    cases['lat'] = cases['village_id'].apply(
        lambda v: village_coords.get(v, {}).get('lat', 5.55) + np.random.uniform(-0.012, 0.012)
    )
    cases['lon'] = cases['village_id'].apply(
        lambda v: village_coords.get(v, {}).get('lon', -0.18) + np.random.uniform(-0.012, 0.012)
    )
    
    # Color by severity
    cases['severity'] = cases['severe_neuro'].map({True: 'Severe', False: 'Mild'})
    
    # Create map
    fig = px.scatter_mapbox(
        cases,
        lat='lat',
        lon='lon',
        color='severity',
        color_discrete_map={'Severe': '#e74c3c', 'Mild': '#f39c12'},
        size_max=15,
        hover_data=['age', 'sex', 'village_name', 'onset_date', 'outcome'],
        zoom=12,
        height=500
    )
    
    # Add village markers
    for vid, coords in village_coords.items():
        fig.add_trace(go.Scattermapbox(
            lat=[coords['lat']],
            lon=[coords['lon']],
            mode='markers+text',
            marker=dict(size=20, color='blue', opacity=0.4),
            text=[coords['name']],
            textposition='top center',
            name=coords['name'],
            showlegend=False
        ))
    
    fig.update_layout(
        mapbox_style="carto-positron",
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Summary statistics
    st.markdown("---")
    st.markdown("#### Geographic Summary")
    
    col1, col2, col3 = st.columns(3)
    
    village_counts = cases['village_id'].value_counts()
    
    with col1:
        n = village_counts.get('V1', 0)
        st.metric("Nalu Village", f"{n} cases")
    
    with col2:
        n = village_counts.get('V2', 0)
        st.metric("Kabwe Village", f"{n} cases")
    
    with col3:
        n = village_counts.get('V3', 0)
        st.metric("Tamu Village", f"{n} cases")
    
    # Interpretation prompts
    with st.expander("🤔 Spot Map Interpretation Questions"):
        st.markdown("""
        Consider these questions as you review the geographic distribution:
        
        1. **Clustering:** Do cases cluster in specific areas? What might explain this?
        2. **Village comparison:** Why might some villages have more cases than others?
        3. **Environmental features:** What is located near the case clusters?
        4. **Hypothesis generation:** What geographic exposures might explain this pattern?
        """)


def view_interventions_and_outcome():
    st.header("📉 Interventions & Outcome")

    st.markdown("### Final Diagnosis")
    dx = st.text_input(
        "What is your final diagnosis?",
        value=st.session_state.decisions.get("final_diagnosis", ""),
    )
    st.session_state.decisions["final_diagnosis"] = dx

    st.markdown("### Recommendations")
    rec_text = st.text_area(
        "List your main recommendations:",
        value="\n".join(st.session_state.decisions.get("recommendations", [])),
        height=160,
    )
    st.session_state.decisions["recommendations"] = [
        ln for ln in rec_text.splitlines() if ln.strip()
    ]

    if st.button("Evaluate Outcome"):
        outcome = evaluate_interventions(
            st.session_state.decisions, st.session_state.interview_history
        )
        st.subheader(f"Outcome: {outcome['status']}")
        st.markdown(outcome["narrative"])
        st.markdown("### Factors considered")
        for line in outcome["outcomes"]:
            st.write(line)
        st.write(f"Score: {outcome['score']}")
        st.write(f"Estimated additional cases: {outcome['new_cases']}")


# =========================
# MAIN
# =========================

def main():
    st.set_page_config(
        page_title="FETP Sim: Sidero Valley",
        page_icon="🦟",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session_state()
    sidebar_navigation()

    # If alert hasn't been acknowledged yet, always show alert screen
    if not st.session_state.alert_acknowledged:
        view_alert()
        return

    view = st.session_state.current_view
    if view == "overview":
        view_overview()
    elif view == "casefinding":
        view_case_finding()
    elif view == "descriptive":
        view_descriptive_epi()
    elif view == "interviews":
        view_interviews()
    elif view == "spotmap":
        view_spot_map()
    elif view == "study":
        view_study_design()
    elif view == "lab":
        view_lab_and_environment()
    elif view == "outcome":
        view_interventions_and_outcome()
    else:
        view_overview()


if __name__ == "__main__":
    main()
