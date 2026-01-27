# FETP Outbreak Simulation - Comprehensive Review Report

**Date:** 2026-01-27
**Scenario Reviewed:** Rivergate After the Storm (Leptospirosis)
**Total Code Lines Analyzed:** ~16,000 (app.py: 9,653 | outbreak_logic.py: 4,617 | day1_utils.py: 1,188 | persistence.py: 420)

---

## Executive Summary

The FETP Outbreak Simulation is a well-designed educational tool for training field epidemiologists. The codebase demonstrates sophisticated understanding of both epidemiology and game mechanics. However, several technical issues and incomplete features require attention.

**Overall Assessment:** 🟡 **Good with Notable Issues**

| Category | Rating | Summary |
|----------|--------|---------|
| Code Quality | 7/10 | Well-structured but monolithic; needs modularization |
| Epidemiological Accuracy | 9/10 | Excellent disease modeling; realistic outbreak patterns |
| User Experience | 6/10 | Functional but friction points exist |
| Feature Completeness | 7/10 | Core features work; some mechanics incomplete |
| Save/Load System | 8/10 | Works for common cases; edge case issues |

---

## CATEGORY 1: Technical/Coding Issues

### 🔴 CRITICAL Issues

#### 1.1 Lepto Symptoms Not Assigned to Generated Cases
**File:** `outbreak_logic.py` lines 1525-1597
**Status:** ✅ FIXED in this review

**Problem:** Generated individuals (non-seed cases) had symptom columns initialized to `False` but never populated. The function `assign_lepto_infections()` set `symptomatic_lepto=True` but individual symptoms (`symptoms_fever`, `symptoms_myalgia`, etc.) remained `False`.

**Impact:** Case definition matching would fail for generated cases because the symptom columns were always `False`, even though cases were marked as symptomatic.

**Fix Applied:** Added `assign_lepto_symptoms()` function to populate individual symptom columns based on symptomatic/severe status with realistic probability distributions.

---

#### 1.2 Duplicate Sidebar Functions
**File:** `app.py` lines 3688-3933 and 9137-9265

**Problem:** Two sidebar functions exist:
- `sidebar_navigation()` (260 lines) - Full featured, active
- `adventure_sidebar()` (130 lines) - Appears to be legacy/incomplete

**Impact:** Code duplication, confusion about which sidebar is active, maintenance burden.

**Recommendation:** Remove or consolidate `adventure_sidebar()`.

---

### 🟠 HIGH Severity Issues

#### 1.3 Missing Error Handling in Data Loading
**Files:** Multiple locations

**Examples:**
- `load_day1_assets()` silently falls back to defaults on path issues
- `run_case_finding()` can crash on malformed source data (ValueError from `float()`/`int()`)
- Image loading functions silently fail without user feedback

**Recommendation:** Add proper try/except blocks with user-facing error messages.

---

#### 1.4 DataFrame Serialization Type Loss
**File:** `persistence.py` lines 155-159, 222-227

**Problem:** DataFrame serialization using `to_json(orient='split')` loses:
- Category dtypes (converted to strings)
- MultiIndex column names
- Custom dtype information

**Impact:** After save/load, some data comparisons may fail due to changed dtypes.

**Recommendation:** Add dtype preservation or validation after deserialization.

---

#### 1.5 Excessive st.rerun() Calls
**File:** `app.py` - 40+ occurrences

**Problem:** Heavy use of `st.rerun()` causes full script re-execution (~9,600 lines) on every interaction.

**Impact:** Performance degradation, UI flicker, potential state issues.

**Recommendation:** Use Streamlit fragments (`@st.fragment`) for interactive components, callbacks instead of reruns where possible.

---

### 🟡 MEDIUM Severity Issues

#### 1.6 Hardcoded Scenario-Specific Values
**File:** `app.py` lines 2043-2062

**Problem:** NPC unlock strings contain hardcoded names:
```python
"Vet Supatra (District Veterinary Officer)"
"Mr. Nguyen (Environmental Health Officer)"
```

**Impact:** Makes adding new scenarios difficult; names should come from `npc_truth.json`.

---

#### 1.7 No State Machine for Game Flow
**File:** `app.py`

**Problem:** Game state is managed through multiple independent variables (`game_state`, `current_view`, `current_day`) with no single source of truth.

**Impact:** Possible invalid state combinations, difficult debugging.

**Recommendation:** Implement a proper state machine pattern.

---

#### 1.8 Missing Input Validation
**File:** `app.py` various locations

**Problem:** User inputs (case definitions, questionnaire uploads) lack validation before processing.

**Recommendation:** Add input sanitization and validation.

---

### 🟢 LOW Severity Issues

#### 1.9 Deprecated Anthropic Model
**File:** `app.py` line 2407

Uses `claude-3-haiku-20240307` which may be deprecated.

#### 1.10 Missing Type Hints
Throughout codebase - approximately 90% of functions lack type annotations.

#### 1.11 Sparse Docstrings
Many complex functions lack documentation of parameters, return values, and side effects.

---

## CATEGORY 2: Interactive/Gameplay Issues

### 🔴 CRITICAL Issues

#### 2.1 Trust System Feedback Invisible
**Status:** ✅ FIXED in this review

**Problem:** NPC trust levels changed based on user tone, but users received no feedback about trust changes. The system worked internally but was invisible.

**Fix Applied:** Added trust indicator showing current rapport and emotion, plus toast notifications when trust changes.

---

### 🟠 HIGH Severity Issues

#### 2.2 Unclear Day Advancement Prerequisites
**Problem:** When users can't advance to the next day, error messages show raw session state keys like `prereq.day1.case_definition` instead of human-readable text.

**Status:** Previously fixed according to session history.

---

#### 2.3 Case Definition Feedback Too Generic
**Problem:** Feedback on case definitions was generic rather than scenario-specific.

**Status:** Previously improved according to session history.

---

### 🟡 MEDIUM Severity Issues

#### 2.4 Medical Records Could Be More Realistic
**Problem:** Initial medical records were too brief for realistic chart review training.

**Status:** Previously expanded to 3-4 pages per case.

---

#### 2.5 No Progress Indicators During LLM Calls
**Problem:** Long-running NPC responses have minimal feedback (just a spinner).

**Recommendation:** Add streaming response display.

---

### 🟢 LOW Severity Issues

#### 2.6 Mobile Responsiveness
Column layouts may not work well on mobile devices.

#### 2.7 Keyboard Navigation
Limited keyboard shortcuts for power users.

---

## CATEGORY 3: Epidemiological Accuracy & Pedagogy

### Assessment: EXCELLENT (9/10)

#### ✅ Strengths

**Incubation Period:** 2-30 days with median ~10 days using lognormal distribution - matches WHO/CDC data perfectly.

**Symptom Accuracy:**
- Fever (≥38°C) - correctly universal
- Calf myalgia - appropriately emphasized as hallmark
- Conjunctival suffusion - correctly described without discharge (vs. conjunctivitis)
- Jaundice - correctly associated with severe form
- Renal failure - correctly associated with Weil's disease

**Risk Factors:**
- Barefoot floodwater exposure - correctly identified as primary route
- Skin wounds as entry point - correctly required
- Rat contact as reservoir - correctly emphasized
- Pigs as amplifying hosts - correctly incorporated (One Health)
- Dose-response relationship with flood depth - correctly modeled

**Laboratory Tests:**
- IgM ELISA timing (day 5+) - correct
- PCR blood (early) vs urine (late) - correct
- MAT as gold standard - correct
- Exclusion tests (malaria, dengue) - appropriate

**Attack Rates:**
- V1 (epicenter): 25.5/1000 - realistic for post-flood lepto outbreak
- V4 (control): 0/1000 - appropriate control

---

#### ⚠️ Areas for Enhancement

**Symptomatic Rate:** Uses 15% of infections become symptomatic. Some sources suggest 5-10%. This is acceptable for teaching purposes (compressed for case volume).

**CFR Accuracy:** 10% of severe cases - within range (WHO: 5-15% for severe lepto).

---

## CATEGORY 4: Incomplete/Placeholder Features

### 🔴 Trust System Investigation

**Finding:** The trust system IS implemented and functional.

**Implementation:**
- `analyze_user_tone()` - Detects polite/rude/neutral
- `update_npc_emotion()` - Updates emotion (cooperative→neutral→wary→annoyed→offended) and trust (-3 to 5)
- Trust affects NPC responses via system prompt injection

**Issue:** The system worked but users couldn't see changes. **Fixed in this review** by adding visual feedback.

---

### 🟠 Incomplete Features

#### 4.1 Evidence Board System
- Initialized in `init_evidence_board()` (line 9345)
- Sync function exists (`sync_evidence_board_from_log()`)
- View function exists (`view_evidence_board()`)
- **Status:** Implemented but may need testing

#### 4.2 One Health Integration
- NPC unlock triggers work (vet, environmental officer)
- One Health samples defined in scenario config
- **Missing:** Dedicated One Health synthesis view

#### 4.3 Scoring System
- `evaluate_interventions()` exists with comprehensive scoring
- **Status:** Appears complete but needs validation

---

### 🟡 Stubbed/Placeholder Items

#### 4.4 Unused Configuration Keys
`scenario_config.json` has `"resources"` section but resource limits aren't strictly enforced in some views.

#### 4.5 Legacy Code
`adventure_sidebar()` appears to be legacy, partially duplicates `sidebar_navigation()`.

---

## CATEGORY 5: Save/Load & Multi-Day Functionality

### Assessment: 8/10 - Works with Limitations

#### ✅ What Works

**Save Functionality:**
- Creates JSON save file with version and timestamp
- Serializes DataFrames, sets, nested dicts correctly for common types
- 84 session state keys tracked across 10 categories
- Human-readable output (indent=2)

**Load Functionality:**
- Validates version field
- Handles individual key failures gracefully
- Returns success/failure with user message

**Day Progression:**
- Prerequisites checked via `check_day_prerequisites()`
- Time penalty for overtime carries to next day
- Lab queue refreshes per day
- SITREP blocking screen forces briefing acknowledgment

---

#### ⚠️ Limitations

**No Cloud Save:**
- Only local file download/upload
- No automatic sync or backup
- No multi-device support

**DataFrame Edge Cases:**
- Category dtypes become strings
- Returns None on any deserialization error (data loss)
- Large DataFrames may cause issues

**Version Compatibility:**
- Only warns on version mismatch, doesn't block
- No migration path for schema changes

---

## Summary of Issues by Severity

| Severity | Count | Examples |
|----------|-------|----------|
| 🔴 Critical | 2 | Lepto symptoms bug (FIXED), duplicate sidebar |
| 🟠 High | 5 | Error handling, DataFrame types, excessive reruns |
| 🟡 Medium | 5 | Hardcoded values, state machine, input validation |
| 🟢 Low | 5 | Model deprecation, type hints, mobile UX |

---

## Fixes Implemented in This Review

1. **Lepto Symptoms Assignment** - Added function to populate symptom columns for generated cases
2. **Trust System Visibility** - Added rapport indicator and change notifications

See `IMPLEMENTATION_LOG.md` for details.

---

## Recommended Priority Actions

1. **High Priority:** Fix duplicate sidebar, add error handling
2. **Medium Priority:** Implement state machine, add input validation
3. **Low Priority:** Add type hints, improve mobile UX, update deprecated model

See `RECOMMENDATIONS.md` for detailed implementation suggestions.
