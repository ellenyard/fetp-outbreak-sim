# Recommendations for FETP Outbreak Simulation

**Date:** 2026-01-27
**Priority Levels:** P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low)

---

## Executive Summary

This document outlines prioritized recommendations for improving the FETP Outbreak Simulation. Recommendations are grouped by effort level and impact, with implementation approaches provided.

**Quick Wins (1-4 hours):** 5 items
**Medium Effort (4-16 hours):** 6 items
**Large Effort (16+ hours):** 4 items

---

## QUICK WINS (1-4 hours each)

### QW-1: Remove Duplicate Sidebar Function
**Priority:** P1 | **Effort:** 1 hour | **Impact:** Code maintainability

**Current State:**
- `sidebar_navigation()` (lines 3688-3933) - Full featured, active
- `adventure_sidebar()` (lines 9137-9265) - Legacy/incomplete

**Recommendation:** Delete `adventure_sidebar()` function entirely. Search codebase for any references and remove.

**Implementation:**
```python
# Delete lines 9137-9265 (adventure_sidebar function)
# Search for "adventure_sidebar" calls and remove
```

---

### QW-2: Update Deprecated Anthropic Model
**Priority:** P2 | **Effort:** 30 minutes | **Impact:** API reliability

**Current State:**
Line 2407 uses `claude-3-haiku-20240307`

**Recommendation:** Update to current model:
```python
# Change from:
model="claude-3-haiku-20240307"
# To:
model="claude-3-5-haiku-20241022"
```

---

### QW-3: Add File Size Validation for Save Load
**Priority:** P2 | **Effort:** 1 hour | **Impact:** Error prevention

**Current State:** `persistence.py` line 379 reads entire file without size check.

**Recommendation:**
```python
def load_save_file(uploaded_file, session_state) -> Tuple[bool, str]:
    # Add size check
    MAX_SAVE_SIZE = 10 * 1024 * 1024  # 10MB
    if uploaded_file.size > MAX_SAVE_SIZE:
        return False, f"Save file too large ({uploaded_file.size / 1024 / 1024:.1f}MB). Maximum is 10MB."

    content = uploaded_file.read()
    # ... rest of function
```

---

### QW-4: Add Loading Indicator for Large Operations
**Priority:** P2 | **Effort:** 2 hours | **Impact:** User experience

**Current State:** Some operations (dataset generation, LLM calls) have minimal feedback.

**Recommendation:** Use Streamlit progress indicators:
```python
# For dataset generation
with st.status("Generating study dataset...", expanded=True) as status:
    st.write("Loading population data...")
    # ... population loading ...
    st.write("Assigning infections...")
    # ... infection assignment ...
    status.update(label="Dataset generated!", state="complete")
```

---

### QW-5: Add Error Boundaries Around Image Loading
**Priority:** P3 | **Effort:** 2 hours | **Impact:** Graceful degradation

**Current State:** Image loading silently fails.

**Recommendation:**
```python
def render_location_image(path, alt_text=""):
    try:
        if os.path.exists(path):
            st.image(path)
        else:
            st.info(f"📷 Image not available: {alt_text}")
    except Exception as e:
        st.warning(f"Could not load image: {alt_text}")
        logger.warning(f"Image load failed: {path} - {e}")
```

---

## MEDIUM EFFORT (4-16 hours each)

### ME-1: Implement View Registry Pattern
**Priority:** P1 | **Effort:** 8 hours | **Impact:** Maintainability, performance

**Current State:** 40+ line elif chain in `main()` for view routing.

**Recommendation:**
```python
# Create view registry
VIEW_REGISTRY = {
    "sitrep": view_sitrep,
    "map": view_travel_map,
    "area": view_area_visual,
    "location": view_location,
    "overview": view_overview,
    "casefinding": view_case_finding,
    # ... etc
}

# In main():
def main():
    # ... initialization ...

    current_view = st.session_state.get("current_view", "map")
    view_func = VIEW_REGISTRY.get(current_view, view_travel_map)
    view_func()
```

**Benefits:**
- Easier to add new views
- Cleaner main() function
- Enables lazy loading

---

### ME-2: Add Input Validation Layer
**Priority:** P1 | **Effort:** 8 hours | **Impact:** Robustness

**Current State:** User inputs processed without validation.

**Recommendation:** Create validation utilities:
```python
# validators.py
from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import date

class CaseDefinition(BaseModel):
    onset_start: date
    onset_end: date
    villages: List[str]
    required_symptoms: List[str]
    optional_symptoms: List[str] = []
    min_optional: int = 0

    @validator('onset_end')
    def end_after_start(cls, v, values):
        if 'onset_start' in values and v < values['onset_start']:
            raise ValueError('onset_end must be after onset_start')
        return v

    @validator('min_optional')
    def min_optional_valid(cls, v, values):
        if 'optional_symptoms' in values and v > len(values['optional_symptoms']):
            raise ValueError('min_optional cannot exceed optional_symptoms count')
        return v
```

---

### ME-3: Add Comprehensive Error Handling
**Priority:** P1 | **Effort:** 6 hours | **Impact:** User experience

**Current State:** Many functions lack error handling or show technical errors.

**Recommendation:** Create error handling decorator:
```python
def handle_errors(user_message="An error occurred"):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValidationError as e:
                st.error(f"Invalid input: {e}")
                logger.warning(f"Validation error in {func.__name__}: {e}")
            except FileNotFoundError as e:
                st.error(f"Required file not found. Please check scenario data.")
                logger.error(f"File not found in {func.__name__}: {e}")
            except Exception as e:
                st.error(user_message)
                logger.exception(f"Unexpected error in {func.__name__}")
        return wrapper
    return decorator

# Usage:
@handle_errors("Could not generate dataset. Please check your case definition.")
def generate_study_dataset(...):
    ...
```

---

### ME-4: Add One Health Synthesis View
**Priority:** P2 | **Effort:** 12 hours | **Impact:** Educational value

**Current State:** One Health NPCs (vet, environmental officer) unlock but no dedicated view synthesizes their data with human cases.

**Recommendation:** Create `view_one_health_synthesis()`:
- Side-by-side timeline: human cases, pig cases, environmental samples
- Correlation analysis prompt
- Discussion questions for facilitator mode
- Evidence linking exercise

---

### ME-5: Implement Streamlit Fragments
**Priority:** P2 | **Effort:** 8 hours | **Impact:** Performance

**Current State:** Heavy use of `st.rerun()` causes full page reloads.

**Recommendation:** Use `@st.fragment` decorator for interactive components:
```python
@st.fragment
def interview_chat_fragment(npc_key: str, npc: dict):
    """Interactive chat that doesn't trigger full rerun."""
    # ... chat implementation ...
    # Only this fragment reruns on interaction
```

**Target areas:**
- NPC chat interface
- Case definition builder
- Line list column selector
- Lab order form

---

### ME-6: Add Session Backup/Recovery
**Priority:** P2 | **Effort:** 6 hours | **Impact:** Data safety

**Current State:** No automatic session backup. Browser close = data loss.

**Recommendation:**
```python
# Auto-save to browser localStorage every 5 minutes
def auto_backup_session():
    backup_data = serialize_session_state(st.session_state)
    backup_json = json.dumps(backup_data)

    # Use streamlit-js-eval for localStorage
    st.components.v1.html(f"""
        <script>
        localStorage.setItem('fetp_autosave', '{backup_json}');
        localStorage.setItem('fetp_autosave_time', new Date().toISOString());
        </script>
    """, height=0)

# On page load, offer to restore
def check_autosave():
    # ... check localStorage and offer restore ...
```

---

## LARGE EFFORT (16+ hours each)

### LE-1: Modularize app.py
**Priority:** P1 | **Effort:** 24 hours | **Impact:** Maintainability

**Current State:** Single 9,653-line file with all views, logic, and UI.

**Recommendation:** Split into modules:
```
app/
├── __init__.py
├── main.py              # Entry point, routing
├── config.py            # Constants, settings
├── session.py           # Session state management
├── components/
│   ├── sidebar.py
│   ├── navigation.py
│   ├── npc_chat.py
│   └── ...
├── views/
│   ├── intro.py
│   ├── overview.py
│   ├── interviews.py
│   ├── case_finding.py
│   └── ...
└── utils/
    ├── formatting.py
    ├── translations.py
    └── resources.py
```

**Migration Steps:**
1. Create module structure
2. Move constants to config.py
3. Extract view functions one at a time
4. Extract shared components
5. Update imports in main.py
6. Test each migration step

---

### LE-2: Implement State Machine for Game Flow
**Priority:** P2 | **Effort:** 20 hours | **Impact:** Robustness

**Current State:** Multiple independent state variables with possible invalid combinations.

**Recommendation:** Use a proper state machine:
```python
from enum import Enum, auto
from transitions import Machine

class GameState(Enum):
    INTRO = auto()
    ALERT = auto()
    DAY1_BRIEFING = auto()
    DAY1_ACTIVE = auto()
    DAY1_COMPLETE = auto()
    DAY2_BRIEFING = auto()
    # ... etc

class GameStateMachine:
    states = [s.name for s in GameState]

    transitions = [
        {'trigger': 'accept_assignment', 'source': 'INTRO', 'dest': 'ALERT'},
        {'trigger': 'acknowledge_alert', 'source': 'ALERT', 'dest': 'DAY1_BRIEFING'},
        {'trigger': 'start_investigation', 'source': 'DAY1_BRIEFING', 'dest': 'DAY1_ACTIVE'},
        # ... etc
    ]

    def __init__(self):
        self.machine = Machine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial='INTRO'
        )
```

**Benefits:**
- Single source of truth for game state
- Impossible invalid states
- Clear transition rules
- Easy to visualize flow

---

### LE-3: Add Cloud Save Integration
**Priority:** P3 | **Effort:** 24 hours | **Impact:** Multi-device support

**Current State:** Only local file save/load.

**Recommendation:** Add optional cloud save:
```python
# Using Supabase (free tier available)
from supabase import create_client

class CloudSaveManager:
    def __init__(self, supabase_url, supabase_key):
        self.client = create_client(supabase_url, supabase_key)

    def save_session(self, user_id: str, session_data: dict) -> str:
        """Save session to cloud, return session ID."""
        result = self.client.table('sessions').insert({
            'user_id': user_id,
            'data': session_data,
            'scenario_id': session_data.get('current_scenario'),
            'current_day': session_data.get('current_day', 1),
        }).execute()
        return result.data[0]['id']

    def load_session(self, session_id: str) -> Optional[dict]:
        """Load session from cloud."""
        result = self.client.table('sessions').select('*').eq('id', session_id).execute()
        if result.data:
            return result.data[0]['data']
        return None

    def list_sessions(self, user_id: str) -> List[dict]:
        """List all sessions for user."""
        result = self.client.table('sessions').select('id,scenario_id,current_day,created_at').eq('user_id', user_id).execute()
        return result.data
```

---

### LE-4: Add Facilitator Analytics Dashboard
**Priority:** P3 | **Effort:** 30 hours | **Impact:** Training oversight

**Current State:** Facilitator mode shows some extra info but no analytics.

**Recommendation:** Create `view_facilitator_dashboard()`:
- Real-time progress tracking for all trainees
- Common mistake patterns
- Time spent per activity
- Intervention timing recommendations
- Group discussion prompts based on progress
- Export reports (CSV, PDF)

---

## Implementation Priority Matrix

| Recommendation | Effort | Impact | Priority |
|----------------|--------|--------|----------|
| QW-1: Remove duplicate sidebar | Low | Medium | P1 |
| QW-2: Update Anthropic model | Low | Medium | P2 |
| ME-1: View registry pattern | Medium | High | P1 |
| ME-2: Input validation | Medium | High | P1 |
| ME-3: Error handling | Medium | High | P1 |
| LE-1: Modularize app.py | High | High | P1 |
| ME-4: One Health synthesis | Medium | Medium | P2 |
| ME-5: Streamlit fragments | Medium | Medium | P2 |
| ME-6: Session backup | Medium | Medium | P2 |
| LE-2: State machine | High | Medium | P2 |
| QW-3: File size validation | Low | Low | P2 |
| QW-4: Loading indicators | Low | Low | P2 |
| QW-5: Image error handling | Low | Low | P3 |
| LE-3: Cloud save | High | Medium | P3 |
| LE-4: Facilitator analytics | High | Medium | P3 |

---

## Recommended Implementation Order

**Sprint 1 (Week 1):** Quick Wins
- [ ] QW-1: Remove duplicate sidebar
- [ ] QW-2: Update Anthropic model
- [ ] QW-3: File size validation
- [ ] QW-4: Loading indicators
- [ ] QW-5: Image error handling

**Sprint 2 (Weeks 2-3):** Core Improvements
- [ ] ME-1: View registry pattern
- [ ] ME-2: Input validation
- [ ] ME-3: Error handling

**Sprint 3 (Weeks 4-6):** Major Refactoring
- [ ] LE-1: Modularize app.py (parallel with other work)

**Sprint 4 (Weeks 7-8):** Performance & Features
- [ ] ME-5: Streamlit fragments
- [ ] ME-4: One Health synthesis view
- [ ] ME-6: Session backup

**Future:** Nice-to-Have
- [ ] LE-2: State machine
- [ ] LE-3: Cloud save
- [ ] LE-4: Facilitator analytics
