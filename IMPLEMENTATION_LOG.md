# Implementation Log

**Date:** 2026-01-27
**Review Session:** Comprehensive FETP Simulation Analysis

---

## Fix #1: Lepto Symptoms Not Assigned to Generated Cases

### Issue
Generated individuals (non-seed cases) in the leptospirosis scenario had symptom columns (`symptoms_fever`, `symptoms_myalgia`, `symptoms_conjunctival_suffusion`, `symptoms_jaundice`, `symptoms_renal_failure`) initialized to `False` but never populated based on their symptomatic/severe status.

### Root Cause
The `assign_lepto_infections()` function in `outbreak_logic.py` correctly set:
- `true_lepto_infection`
- `symptomatic_lepto`
- `severe_lepto`
- `onset_date`
- `outcome`

But did NOT populate the individual symptom columns that case definition matching relies on.

### File Changed
`outbreak_logic.py`

### Lines Modified
After line 1595, before `return individuals_df`

### Fix Applied
Added `assign_lepto_symptoms()` function that populates individual symptoms based on symptomatic/severe status:

```python
def assign_lepto_symptoms(row):
    # Skip seed cases - they already have symptoms from CSV
    if row['person_id'].startswith('P0') or row['person_id'].startswith('P1') or row['person_id'].startswith('P2'):
        if len(row['person_id']) <= 5:
            return row  # Keep existing values

    # Non-symptomatic cases have no symptoms
    if not row.get('symptomatic_lepto', False):
        return row

    # Symptomatic cases get symptoms based on severity
    is_severe = row.get('severe_lepto', False)

    # Fever - almost universal in symptomatic leptospirosis (>95%)
    row['symptoms_fever'] = np.random.random() < 0.98

    # Headache - very common (~80%)
    row['symptoms_headache'] = np.random.random() < 0.80

    # Myalgia (especially calf) - hallmark symptom (~85%)
    row['symptoms_myalgia'] = np.random.random() < 0.85

    # Conjunctival suffusion - common but more diagnostic
    if is_severe:
        row['symptoms_conjunctival_suffusion'] = np.random.random() < 0.70
    else:
        row['symptoms_conjunctival_suffusion'] = np.random.random() < 0.45

    # Jaundice - mainly severe cases (Weil's disease)
    if is_severe:
        row['symptoms_jaundice'] = np.random.random() < 0.85
    else:
        row['symptoms_jaundice'] = np.random.random() < 0.05

    # Renal failure - severe cases only
    if is_severe:
        row['symptoms_renal_failure'] = np.random.random() < 0.60
    else:
        row['symptoms_renal_failure'] = False

    return row

individuals_df = individuals_df.apply(assign_lepto_symptoms, axis=1)
```

### Symptom Probability Rationale (Based on Medical Literature)

| Symptom | Mild Cases | Severe Cases | Source |
|---------|------------|--------------|--------|
| Fever | 98% | 98% | Universal in symptomatic lepto |
| Headache | 80% | 80% | Very common presentation |
| Myalgia | 85% | 85% | Hallmark symptom, especially calves |
| Conjunctival suffusion | 45% | 70% | More common in severe |
| Jaundice | 5% | 85% | Defines Weil's disease |
| Renal failure | 0% | 60% | Severe form marker |

### How to Test
1. Start new leptospirosis scenario
2. Generate study dataset
3. Check that generated cases (not P0xxx seed cases) have symptom columns populated
4. Verify case definition matching works for generated cases

---

## Fix #2: Trust System Visual Feedback

### Issue
The NPC trust system was functional internally but users received no feedback when their tone affected trust levels. The `analyze_user_tone()` and `update_npc_emotion()` functions worked correctly, but changes were invisible to users.

### Root Cause
Trust changes happened inside `get_npc_response()` but the UI never displayed:
1. Current trust/rapport status
2. Notifications when trust changed
3. Emotional state indicator

### File Changed
`app.py`

### Function Modified
`render_npc_chat()` (lines 9024-9135)

### Fix Applied

**Added trust indicator display:**
```python
# Show trust indicator for non-nurse NPCs
if npc_key != "nurse_joy":
    trust = get_npc_trust(npc_key)
    npc_state_info = st.session_state.npc_state.get(npc_key, {"emotion": "neutral"})
    emotion = npc_state_info.get("emotion", "neutral")
    emotion_emoji = {"cooperative": "😊", "neutral": "😐", "wary": "🤨", "annoyed": "😤", "offended": "😠"}.get(emotion, "😐")
    st.caption(f"**Rapport:** {emotion_emoji} {emotion.title()} | **Trust:** {trust}/5")
```

**Added trust change notifications:**
```python
# Capture trust before interaction for comparison
trust_before = get_npc_trust(npc_key)
emotion_before = st.session_state.npc_state.get(npc_key, {}).get("emotion", "neutral")

# ... (after NPC response) ...

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
```

### How Trust System Works (Documentation)

**Tone Detection (`analyze_user_tone()`):**
- Polite triggers: "please", "thank you", "thanks", "appreciate", "grateful"
- Rude triggers: "stupid", "idiot", "useless", "incompetent", "do your job", etc.
- ALL CAPS messages > 5 characters = rude

**Trust Changes:**
- Polite: Trust +1 (max 5), emotion shifts toward cooperative
- Rude: Trust -1 (min -3), emotion shifts 2 steps toward offended
- Neutral: Slow recovery every 4 interactions if annoyed/offended

**Emotion Scale:**
cooperative → neutral → wary → annoyed → offended

**Impact on NPC Responses:**
- Cooperative: May volunteer extra helpful context
- Neutral: Normal answers, no volunteering
- Wary: Minimal direct answers
- Annoyed: Short answers only
- Offended: Very brief, essential facts only

### How to Test
1. Start interview with any NPC (not Nurse Joy who has special rapport system)
2. Observe rapport indicator showing "Neutral" and trust level
3. Ask polite questions with "please" or "thank you"
4. Observe toast notification and updated rapport
5. Ask rude questions (or use ALL CAPS)
6. Observe rapport decrease and emotional state change
7. Verify NPC responses become shorter/less helpful when offended

---

## Changes Summary

| Fix | File | Type | Lines |
|-----|------|------|-------|
| Lepto symptoms | outbreak_logic.py | Bug fix | +40 lines |
| Trust feedback | app.py | UX improvement | +20 lines |

---

## Testing Checklist

- [ ] Lepto scenario generates cases with proper symptom columns
- [ ] Case definition matching works for generated cases
- [ ] Trust indicator displays on NPC chat
- [ ] Polite messages increase trust with notification
- [ ] Rude messages decrease trust with notification
- [ ] Emotion changes display with indicator
- [ ] NPC response quality varies with trust level
