"""NPC conversation engine for outbreak simulation.

Contains the core NPC response generation logic including lab label
management, avatar resolution, and Anthropic API integration for
generating in-character NPC dialogue.
"""

import json
import logging
import re
from pathlib import Path

import streamlit as st
import anthropic

from npc.context import (
    build_epidemiologic_context,
    build_npc_data_context,
    investigation_stage,
    redact_spoilers,
    sanitize_npc_truth_for_prompt,
    npc_style_hint,
)
from npc.emotions import (
    analyze_user_tone,
    update_npc_emotion,
    describe_emotional_state,
    get_npc_trust,
    classify_question_scope,
)
from npc.unlock import should_unlock_hospital_records


# =========================
# LAB LABELS (anti-spoiler)
# =========================

LAB_TEST_CATALOG = {
    "JE_IgM_CSF": {"generic": "Arbovirus IgM (CSF)", "confirmed": "Japanese Encephalitis IgM (CSF)"},
    "JE_IgM_serum": {"generic": "Arbovirus IgM (serum)", "confirmed": "Japanese Encephalitis IgM (serum)"},
    "JE_PCR_CSF": {"generic": "Arbovirus PCR (CSF)", "confirmed": "Japanese Encephalitis PCR (CSF)"},
    "JE_PCR_mosquito": {"generic": "Arbovirus PCR (mosquito pool)", "confirmed": "Japanese Encephalitis PCR (mosquito pool)"},
    "JE_Ab_pig": {"generic": "Arbovirus antibodies (pig serum)", "confirmed": "Japanese Encephalitis antibodies (pig serum)"},
    "LEPTO_ELISA_IGM": {"generic": "Leptospira IgM ELISA", "confirmed": "Leptospira IgM ELISA"},
    "LEPTO_PCR_BLOOD": {"generic": "Leptospira PCR (blood)", "confirmed": "Leptospira PCR (blood)"},
    "LEPTO_PCR_URINE": {"generic": "Leptospira PCR (urine)", "confirmed": "Leptospira PCR (urine)"},
    "LEPTO_MAT": {"generic": "Leptospira MAT", "confirmed": "Leptospira MAT"},
    "LEPTO_ENV_WATER_PCR": {"generic": "Leptospira PCR (water)", "confirmed": "Leptospira PCR (water)"},
    "RODENT_PCR": {"generic": "Rodent kidney PCR", "confirmed": "Rodent kidney PCR"},
    "MALARIA_RDT": {"generic": "Malaria RDT", "confirmed": "Malaria RDT"},
    "DENGUE_NS1": {"generic": "Dengue NS1", "confirmed": "Dengue NS1"},
    "BACTERIAL_MENINGITIS_CSF": {"generic": "Bacterial meningitis panel (CSF)", "confirmed": "Bacterial meningitis panel (CSF)"},
}


def _scenario_lab_catalog() -> dict:
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    catalog = {}
    for entry in scenario_config.get("lab_tests", []):
        code = entry.get("code")
        if not code:
            continue
        catalog[code] = {
            "generic": entry.get("label_generic", code),
            "confirmed": entry.get("label_confirmed", entry.get("label_generic", code)),
        }
    return catalog


def lab_test_label(test_code: str) -> str:
    stage = investigation_stage()
    catalog = _scenario_lab_catalog()
    entry = catalog.get(test_code) or LAB_TEST_CATALOG.get(test_code, {})
    if stage == "confirmed":
        return entry.get("confirmed", test_code)
    return entry.get("generic", test_code)


def refresh_lab_queue_for_day(day: int) -> None:
    """Promote PENDING lab results to final result when day >= ready_day."""
    if "lab_results" not in st.session_state or not st.session_state.lab_results:
        return

    stage_before = investigation_stage()

    for r in st.session_state.lab_results:
        ready_day = int(r.get("ready_day", 9999))
        if str(r.get("result", "")).upper() == "PENDING" and day >= ready_day:
            r["result"] = r.get("final_result_hidden", r.get("result", "PENDING"))

    # Reveal etiology if confirmatory test returns POSITIVE (only after Day 3+)
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    confirmatory = set(scenario_config.get("confirmatory_tests", []))
    if day >= 3 and stage_before != "confirmed":
        for r in st.session_state.lab_results:
            if str(r.get("result", "")).upper() == "POSITIVE" and r.get("test") in confirmatory:
                st.session_state.etiology_revealed = True
                break


def get_npc_avatar(npc: dict) -> str:
    """Get the avatar for an NPC - returns image path if available, otherwise emoji."""
    image_path = npc.get("image_path")
    if image_path and Path(image_path).exists():
        return image_path
    return npc.get("avatar", "\U0001f9d1")


def _npc_fallback_message(npc_key: str, error_type: str) -> str:
    """Return an in-character fallback when the AI API is unavailable.

    Instead of showing raw error JSON, give the player a message that
    feels like part of the simulation while hinting they should retry.
    """
    npc_name = npc_key.replace("_", " ").title()

    if error_type == "busy":
        return (
            f"*{npc_name} is speaking with another patient right now.* "
            "Please try again in a moment."
        )
    if error_type == "network":
        return (
            f"*The phone line to {npc_name} cuts out.* "
            "There seems to be a connection issue — please try again."
        )
    if error_type == "config":
        return (
            "\u26a0\ufe0f The simulation's AI service is not configured correctly. "
            "Please ask your facilitator to check the API key."
        )
    # Generic fallback for api / unknown / empty / malformed
    return (
        f"*{npc_name} pauses and seems distracted.* "
        "\"Sorry, can you repeat that?\" "
        "(There was a temporary issue — please try your question again.)"
    )


def get_npc_response(npc_key: str, user_input: str) -> str:
    """Call Anthropic using npc_truth + epidemiologic context, with memory & emotional state."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "\u26a0\ufe0f Anthropic API key missing."

    truth = st.session_state.truth
    npc_truth_dict = truth.get("npc_truth", {})
    if npc_key not in npc_truth_dict:
        return f"\u26a0\ufe0f NPC '{npc_key}' not found in scenario data."
    npc_truth = npc_truth_dict[npc_key]
    stage = investigation_stage()
    npc_truth_safe = sanitize_npc_truth_for_prompt(npc_truth, stage)

    # Conversation history = memory
    history = st.session_state.interview_history.get(npc_key, [])
    meaningful_questions = sum(1 for m in history if m["role"] == "user")

    # Determine question scope & user tone
    question_scope = classify_question_scope(user_input)
    user_tone = analyze_user_tone(user_input)
    npc_state = update_npc_emotion(npc_key, user_tone)
    emotional_description = describe_emotional_state(npc_state)
    trust_level = get_npc_trust(npc_key)

    epi_context = build_npc_data_context(npc_key, truth)
    epi_context = redact_spoilers(epi_context, stage)

    if npc_key not in st.session_state.revealed_clues:
        st.session_state.revealed_clues[npc_key] = []

    system_prompt = f"""
You are {npc_truth_safe['name']}, the {npc_truth_safe['role']} in Sidero Valley.

CORE RULES:
You are NOT an AI assistant. You are a fictional character in a training simulation.
Do not offer to help. Do not be polite unless your character personality is polite.
If the user asks a vague question, give a vague answer.
Force them to ask the right specific questions to get the information.

CRITICAL ANTI-SPOILER RULES:
- Be BRIEF and PROFESSIONAL. Keep responses to 2-4 sentences unless asked for more detail.
- DO NOT name specific pathogens (JEV, Japanese Encephalitis, arbovirus) unless you see lab confirmation.
- DO NOT jump to conclusions about the cause. Only provide RAW OBSERVATIONAL DATA.
- DO NOT volunteer diagnostic hunches. You are a witness, not a diagnostician.
- If asked "what is causing this?", say you don't know - you only see symptoms/patterns.

Personality:
{npc_truth_safe['personality']}

Your current emotional state toward the investigation team:
{emotional_description}

Your level of trust toward the investigation team: {trust_level}/5

The investigator has asked about {meaningful_questions} meaningful questions so far in this conversation.

STYLE GUIDANCE:
{npc_style_hint(npc_key, meaningful_questions, npc_state)}

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
- If the user asks a narrow, specific question, answer in 1-3 sentences.
- If the user asks a broad question like "what do you know" or "tell me everything", you may answer in more detail (up to about 5-7 sentences) and provide a thoughtful overview.

ALWAYS REVEAL (gradually, not all at once):
{npc_truth_safe['always_reveal']}

CONDITIONAL CLUES:
- Reveal a conditional clue ONLY when the user's question clearly relates to that topic.
- Work clues into natural speech; do NOT list them as bullet points.
{npc_truth_safe['conditional_clues']}

RED HERRINGS:
- You may mention these occasionally, but do NOT contradict the core truth:
{npc_truth_safe['red_herrings']}

UNKNOWN:
- If the user asks about these topics, you must say you do not know:
{npc_truth_safe['unknowns']}

INFORMATION RULES:
- Never invent new outbreak details (case counts, test results, locations) beyond what is implied in the context.
- If you are unsure, say you are not certain.
"""

    # Decide which conditional clues are allowed in this answer
    lower_q = user_input.lower()
    conditional_to_use = []
    topic_synonyms = {
        "water": ["well", "river", "stream", "paddies", "irrigation", "pond"],
        "pigs": ["pig", "pork", "swine", "hog", "sow", "litter"],
        "animals": ["livestock", "cattle", "goat", "chicken", "duck"],
        "mosquito": ["vector", "bite", "mosquitoes", "dusk", "nets"],
        "vaccine": ["vaccination", "immunization", "shot", "campaign"],
        "market": ["bazaar", "marketplace", "vendors"],
        "travel": ["bus", "trip", "journey", "visited", "overnight"],
    }

    def topic_matches(keyword: str, text: str) -> bool:
        if keyword in text:
            return True
        for synonym in topic_synonyms.get(keyword, []):
            if synonym in text:
                return True
        return False

    for keyword, clue in npc_truth.get("conditional_clues", {}).items():
        if topic_matches(keyword.lower(), lower_q) and clue not in st.session_state.revealed_clues[npc_key]:
            conditional_to_use.append(redact_spoilers(clue, stage))
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

    # Limit conversation history to last 10 exchanges to reduce latency
    recent_history = history[-20:] if len(history) > 20 else history
    msgs = [{"role": m["role"], "content": m["content"]} for m in recent_history]
    msgs.append({"role": "user", "content": user_input})

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,  # Slightly reduced for faster responses
            system=system_prompt,
            messages=msgs,
        )

        # Validate response structure before accessing content
        if not resp.content or len(resp.content) == 0:
            return _npc_fallback_message(npc_key, "empty response")

        if not hasattr(resp.content[0], 'text'):
            return _npc_fallback_message(npc_key, "malformed response")

        text = resp.content[0].text
    except anthropic.APIConnectionError:
        return _npc_fallback_message(npc_key, "network")
    except anthropic.RateLimitError:
        return _npc_fallback_message(npc_key, "busy")
    except anthropic.AuthenticationError:
        logger.error("Anthropic API authentication failed — check ANTHROPIC_API_KEY")
        return _npc_fallback_message(npc_key, "config")
    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        return _npc_fallback_message(npc_key, "api")
    except Exception as e:
        logger.error("Unexpected NPC conversation error: %s", e)
        return _npc_fallback_message(npc_key, "unknown")

    text = redact_spoilers(text, stage)

    # Unlock flags (One Health unlocks)
    unlock_flag = npc_truth.get("unlocks")
    permission_keywords = ["permission", "access", "records", "investigate", "allow"]
    permission_requested = any(keyword in lower_q for keyword in permission_keywords)

    if unlock_flag:
        if unlock_flag == "tran_permission_granted":
            if permission_requested:
                st.session_state.unlock_flags[unlock_flag] = True
        else:
            st.session_state.unlock_flags[unlock_flag] = True

        if should_unlock_hospital_records(unlock_flag) and (
            unlock_flag != "tran_permission_granted" or permission_requested
        ):
            st.session_state.unlock_flags["records_access"] = True

    # SPECIAL LOGIC: Permission granting for hospital records access
    if npc_key == "dr_chen" and permission_requested:
        st.session_state.unlock_flags["records_access"] = True
        st.session_state.unlock_flags["tran_permission_granted"] = True
        st.rerun()  # Force refresh to unlock the buttons immediately

    # SPECIAL LOGIC: Ward Parent livestock question counter
    if npc_key == "ward_parent":
        lower_q = user_input.lower()
        # Increment counter if asking about livestock/animals/pigs
        if any(keyword in lower_q for keyword in ["livestock", "animal", "pig", "cow", "chicken", "duck"]):
            if "?" in lower_q:  # Must be a question
                if 'ward_parent_livestock_asks' not in st.session_state:
                    st.session_state.ward_parent_livestock_asks = 0
                st.session_state.ward_parent_livestock_asks += 1

                # On second ask about livestock, reveal pigs
                if st.session_state.ward_parent_livestock_asks >= 2:
                    # Make sure the pig info gets included
                    if "pigs" not in text.lower() and "pig" not in text.lower():
                        text += "\n\n...Well, actually, we do keep pigs. Two of them, right near the house. They're for the New Year festival."

    return text


def stream_npc_response(npc_key: str, user_input: str):
    """
    Stream NPC response for faster perceived response time.
    Yields text chunks as they arrive from the API.
    Returns the full text after streaming completes.
    """
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield "\u26a0\ufe0f Anthropic API key missing."
        return

    truth = st.session_state.truth
    npc_truth_dict = truth.get("npc_truth", {})
    if npc_key not in npc_truth_dict:
        yield f"\u26a0\ufe0f NPC '{npc_key}' not found in scenario data."
        return

    npc_truth = npc_truth_dict[npc_key]
    stage = investigation_stage()
    npc_truth_safe = sanitize_npc_truth_for_prompt(npc_truth, stage)

    history = st.session_state.interview_history.get(npc_key, [])
    meaningful_questions = sum(1 for m in history if m["role"] == "user")

    question_scope = classify_question_scope(user_input)
    user_tone = analyze_user_tone(user_input)
    npc_state = update_npc_emotion(npc_key, user_tone)
    emotional_description = describe_emotional_state(npc_state)
    trust_level = get_npc_trust(npc_key)

    epi_context = build_npc_data_context(npc_key, truth)
    epi_context = redact_spoilers(epi_context, stage)

    if npc_key not in st.session_state.revealed_clues:
        st.session_state.revealed_clues[npc_key] = []

    # Shortened system prompt for faster responses
    system_prompt = f"""You are {npc_truth_safe['name']}, {npc_truth_safe['role']} in this district.

RULES: You are a character, not an AI. Be BRIEF (2-4 sentences). Don't name pathogens unless lab-confirmed. Don't volunteer diagnoses.

Personality: {npc_truth_safe['personality']}
Emotional state: {emotional_description} (Trust: {trust_level}/5)

Context (don't recite unless asked): {epi_context}

ALWAYS REVEAL (gradually): {npc_truth_safe['always_reveal']}

CONDITIONAL (only if asked about topic): {npc_truth_safe['conditional_clues']}

RED HERRINGS (may mention): {npc_truth_safe['red_herrings']}

UNKNOWN (say you don't know): {npc_truth_safe['unknowns']}
"""

    # Conditional clues logic
    lower_q = user_input.lower()
    topic_synonyms = {
        "water": ["well", "river", "stream", "paddies", "irrigation", "pond"],
        "pigs": ["pig", "pork", "swine", "hog", "sow", "litter"],
        "animals": ["livestock", "cattle", "goat", "chicken", "duck"],
        "mosquito": ["vector", "bite", "mosquitoes", "dusk", "nets"],
    }

    def topic_matches(keyword: str, text: str) -> bool:
        if keyword in text:
            return True
        for synonym in topic_synonyms.get(keyword, []):
            if synonym in text:
                return True
        return False

    conditional_to_use = []
    for keyword, clue in npc_truth.get("conditional_clues", {}).items():
        if topic_matches(keyword.lower(), lower_q) and clue not in st.session_state.revealed_clues[npc_key]:
            conditional_to_use.append(redact_spoilers(clue, stage))
            st.session_state.revealed_clues[npc_key].append(clue)

    if question_scope != "broad" and len(conditional_to_use) > 1:
        conditional_to_use = conditional_to_use[:1]

    if conditional_to_use:
        system_prompt += "\n\nREVEAL naturally: " + "; ".join(conditional_to_use)

    client = anthropic.Anthropic(api_key=api_key)

    recent_history = history[-20:] if len(history) > 20 else history
    msgs = [{"role": m["role"], "content": m["content"]} for m in recent_history]
    msgs.append({"role": "user", "content": user_input})

    try:
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=system_prompt,
            messages=msgs,
        ) as stream:
            for text_chunk in stream.text_stream:
                yield text_chunk
    except anthropic.RateLimitError:
        yield _npc_fallback_message(npc_key, "busy")
    except anthropic.APIConnectionError:
        yield _npc_fallback_message(npc_key, "network")
    except anthropic.AuthenticationError:
        logger.error("Anthropic API authentication failed — check ANTHROPIC_API_KEY")
        yield _npc_fallback_message(npc_key, "config")
    except Exception as e:
        logger.error("Streaming NPC error: %s", e)
        yield _npc_fallback_message(npc_key, "unknown")
