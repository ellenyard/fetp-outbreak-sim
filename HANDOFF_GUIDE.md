# FETP Outbreak Simulation - Project Handoff Guide

**Date:** 2026-01-27
**Project:** Field Epidemiology Training Program (FETP) Outbreak Investigation Simulator

---

## 1. Project Overview

This is an interactive web-based training simulation for Field Epidemiology Training Program (FETP) Intermediate 2.0 trainees. Players investigate disease outbreaks across 5 days, interviewing AI-powered NPCs, analyzing data, and making epidemiological decisions.

**Live URL:** Deployed on Streamlit Cloud (connect to GitHub repo)

**Current Scenarios:**
1. **Shadows Over Sidero Valley** - Japanese Encephalitis outbreak
2. **Rivergate After the Storm** - Leptospirosis post-flood outbreak (most developed)

---

## 2. File Structure & Descriptions

### Core Python Files

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | ~9,200 | Main Streamlit application - UI, views, NPC chat, game flow |
| `outbreak_logic.py` | ~4,600 | Disease modeling, population generation, case definitions, lab tests |
| `day1_utils.py` | ~1,200 | Day 1 specific utilities (medical records, clinic logs) |
| `persistence.py` | ~420 | Save/load game state to JSON files |

### Scenario Data (per scenario)

```
scenarios/{scenario_id}/
├── scenario_config.json     # Scenario settings, resources, day specs
├── storyline.md             # Narrative outline (for reference)
├── content/
│   ├── about.md             # Scenario background
│   ├── alert.md             # Initial alert notification
│   ├── day{1-5}_briefing.md # Daily briefing content
│   ├── case_definition_template.md
│   ├── hypothesis_examples.md
│   └── interventions.md
├── data/
│   ├── npc_truth.json       # NPC knowledge, clues, red herrings
│   ├── day1_assets.json     # Day 1 data (villages, households, individuals)
│   ├── hospital_records.json # Patient medical records
│   └── clinic_records.json  # Clinic visit logs
└── assets/
    └── *.png                # Scene images, NPC portraits, location images
```

### Shared Assets

```
assets/
├── Hospital/          # Hospital location images
├── Kabwe/             # Village images (JE scenario)
├── Nalu/              # Village images
├── Tamu/              # Village images
└── map_background.png # Main travel map
```

### Localization

```
Locales/
├── en/ui.json   # English UI strings
├── es/ui.json   # Spanish
├── fr/ui.json   # French
└── pt/ui.json   # Portuguese
```

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Basic setup instructions (needs updating) |
| `REVIEW_REPORT.md` | Comprehensive code review findings |
| `RECOMMENDATIONS.md` | Prioritized improvement suggestions |
| `IMPLEMENTATION_LOG.md` | Log of fixes applied |
| `LEPTO_EPI_REVIEW.md` | Epidemiological accuracy assessment |
| `MULTI_SCENARIO_ARCHITECTURE.md` | Multi-scenario system design |

---

## 3. Technology Stack

### Dependencies (requirements.txt)

| Package | Purpose |
|---------|---------|
| `streamlit>=1.32.0` | Web application framework |
| `anthropic>=0.18.0` | Claude AI API for NPC conversations |
| `pandas>=2.0.0` | Data manipulation |
| `plotly>=5.18.0` | Interactive charts |
| `numpy>=1.24.0` | Numerical operations |
| `openpyxl>=3.1.2` | Excel file handling (questionnaires) |
| `openai>=1.30.0` | OpenAI API (optional, unused currently) |
| `pillow>=10.3.0` | Image processing |

### External Services

| Service | Purpose | Required |
|---------|---------|----------|
| **Anthropic Claude API** | Powers NPC conversations | Yes |
| **Streamlit Cloud** | Hosting platform | Recommended |
| **GitHub** | Source control, CI/CD trigger | Yes |

---

## 4. Repository Transfer Options

### Option A: Fork the Repository (Recommended)

1. Go to https://github.com/ellenyard/fetp-outbreak-sim
2. Click "Fork" button
3. New owners get full copy with commit history
4. Original repo can still receive updates via pull requests

### Option B: Transfer Ownership

1. Go to Repository Settings > General > Danger Zone
2. Click "Transfer ownership"
3. Enter new owner's GitHub username
4. They accept the transfer
5. All issues, PRs, and settings transfer

### Option C: Clone and Create New Repo

```bash
git clone https://github.com/ellenyard/fetp-outbreak-sim.git
cd fetp-outbreak-sim
git remote remove origin
git remote add origin https://github.com/NEW_OWNER/NEW_REPO.git
git push -u origin main
```

---

## 5. Deployment Setup

### Streamlit Cloud Deployment

1. Connect GitHub repository to Streamlit Cloud
2. Select `app.py` as the main file
3. Add secrets in Streamlit Cloud dashboard:

```toml
# .streamlit/secrets.toml (DO NOT commit to repo)
ANTHROPIC_API_KEY = "sk-ant-..."
```

4. Deploy

### Local Development

```bash
# Clone repository
git clone https://github.com/YOUR_ORG/fetp-outbreak-sim.git
cd fetp-outbreak-sim

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set API key (for local testing)
export ANTHROPIC_API_KEY="sk-ant-..."

# Run locally
streamlit run app.py
```

---

## 6. Required Credentials & Secrets

| Secret | Where to Get | Where to Store |
|--------|--------------|----------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com | Streamlit Cloud Secrets |

**Important:** Never commit API keys to the repository.

---

## 7. Asset Creation (Midjourney)

All images in the `assets/` and `scenarios/*/assets/` directories were created using **Midjourney AI**.

### Image Categories

| Type | Naming Convention | Example |
|------|-------------------|---------|
| NPC Portraits | `npc_{lastname}_{firstname}.png` | `npc_vale_anton.png` |
| Locations | `loc_{location_name}.png` | `loc_district_hospital_ward.png` |
| Scenes | `scene_{description}.png` | `scene_flooded_northbend_during.png` |
| Documents | `doc_{type}.png` | `doc_handwritten_clinic_record.png` |

### Midjourney Prompt Style

For consistency, images use a semi-realistic Southeast Asian setting:

```
[subject description], Southeast Asian rural village setting,
warm natural lighting, photorealistic, --ar 16:9 --v 6
```

### Creating New Images

1. Generate in Midjourney with consistent style
2. Upscale to high resolution
3. Save as PNG (transparency supported)
4. Recommended dimensions: 1920x1080 for scenes, 512x512 for portraits
5. Place in appropriate `assets/` directory
6. Reference in `scenario_config.json` or `npc_truth.json`

---

## 8. Key Architectural Concepts

### Session State

All game state is stored in `st.session_state`. Key variables:

| Variable | Purpose |
|----------|---------|
| `current_day` | Current investigation day (1-5) |
| `current_view` | Active UI view |
| `truth` | Ground truth data (population, cases, NPCs) |
| `decisions` | Player decisions log |
| `interview_history` | NPC conversation history |
| `npcs_unlocked` | List of available NPCs |

### View Registry Pattern

Views are routed via dictionaries in `app.py`:
- `VIEWS_WITH_RETURN_BUTTON` - Views needing navigation back to map
- `VIEWS_DIRECT` - Views without return button
- `route_to_view()` - Main routing function

### NPC System

NPCs are defined in `npc_truth.json` with:
- `base_knowledge` - Always shared information
- `hidden_clues` - Revealed with specific questions
- `red_herrings` - Misleading information (realism)
- `unknown_topics` - Topics NPC won't answer (prevents hallucination)

Trust system affects NPC responses based on player tone (polite/rude).

### Disease Modeling

`outbreak_logic.py` implements:
- Population generation with risk factors
- Lognormal incubation period distribution
- Symptom assignment based on severity
- Laboratory test sensitivity by day
- Case definition matching

---

## 9. Known Issues & Future Work

See `RECOMMENDATIONS.md` for detailed priority list. Key items:

**Completed:**
- [x] View registry pattern
- [x] Error handling decorator
- [x] File size validation
- [x] Trust system UI feedback
- [x] Lepto symptom assignment fix

**Recommended Next:**
- [ ] Modularize app.py into multiple files
- [ ] Add input validation layer
- [ ] Implement Streamlit fragments for performance
- [ ] Add One Health synthesis view
- [ ] Session auto-backup to localStorage

---

## 10. Contact & Support

**Original Developer:** Ellen Yard
**AI Development Partner:** Claude (Anthropic)

For questions about:
- **Epidemiological content:** Contact FETP program leads
- **Technical issues:** Check GitHub Issues or create new issue
- **Anthropic API:** https://docs.anthropic.com

---

## 11. Quick Start Checklist for New Leads

- [ ] Fork or transfer GitHub repository
- [ ] Create Anthropic API account and get key
- [ ] Set up Streamlit Cloud deployment
- [ ] Add `ANTHROPIC_API_KEY` to Streamlit secrets
- [ ] Test deployment with both scenarios
- [ ] Review `REVIEW_REPORT.md` for current state
- [ ] Review `RECOMMENDATIONS.md` for improvement roadmap
- [ ] Familiarize with `npc_truth.json` structure for content updates
- [ ] Set up Midjourney account if creating new images

---

## Appendix: File Inventory

### Python Files (4)
- `app.py` - Main application
- `outbreak_logic.py` - Simulation logic
- `day1_utils.py` - Day 1 utilities
- `persistence.py` - Save/load system

### JSON Data Files (~15)
- 2x `scenario_config.json`
- 2x `npc_truth.json`
- 2x `day1_assets.json`
- 4x `Locales/*/ui.json`
- Various records files

### Markdown Content (~25)
- Briefings, alerts, templates per scenario
- Documentation files

### Image Assets (~50+)
- NPC portraits
- Location images
- Scene illustrations
- UI elements
