# Multi-Scenario Architecture

## Overview
The FETP Outbreak Simulation supports multiple disease outbreak scenarios with shared core logic and scenario-specific content.

## Directory Structure
```
fetp-outbreak-sim/
├── app.py (shared UI)
├── outbreak_logic.py (shared logic)
├── persistence.py (save/load functionality)
├── requirements.txt
├── README.md
├── .gitignore
└── scenarios/
    ├── aes_sidero_valley/ (JE scenario)
    │   ├── data/
    │   │   ├── villages.csv
    │   │   ├── households_seed.csv
    │   │   ├── individuals_seed.csv
    │   │   ├── lab_samples.csv
    │   │   ├── environment_sites.csv
    │   │   └── npc_truth.json
    │   └── content/
    │       ├── alert.md
    │       ├── day1_briefing.md
    │       ├── day2_briefing.md
    │       ├── day3_briefing.md
    │       ├── day4_briefing.md
    │       ├── day5_briefing.md
    │       ├── case_definition_template.md
    │       ├── hypothesis_examples.md
    │       └── interventions.md
    └── lepto_rivergate/ (Lepto scenario)
        ├── data/
        │   ├── villages.csv
        │   ├── households_seed.csv
        │   ├── individuals_seed.csv
        │   ├── lab_samples.csv
        │   ├── environment_sites.csv
        │   └── npc_truth.json
        └── content/
            ├── alert.md
            ├── day1_briefing.md
            ├── day2_briefing.md
            ├── day3_briefing.md
            ├── day4_briefing.md
            ├── day5_briefing.md
            ├── case_definition_template.md
            ├── hypothesis_examples.md
            └── interventions.md
```

## Scenario-Specific vs. Shared Components

### Shared Components (Core Framework)
**In `outbreak_logic.py`:**
- `generate_full_population()` - Population generation (scenario-aware)
- Descriptive epidemiology functions
- Study design framework (case-control, cohort)
- XLSForm processing
- Lab test framework
- Generic statistical functions

**In `app.py`:**
- UI framework and navigation
- Session state management
- Scenario selector
- Content loading functions (`load_scenario_content()`)
- Generic forms (case definition, hypotheses, questionnaires)
- Save/load functionality

### Scenario-Specific Components

**Data Files (`scenarios/{scenario_id}/data/`):**
- `villages.csv` - Geographic units with scenario-specific risk factors
- `households_seed.csv` - Household characteristics
- `individuals_seed.csv` - Initial cases with scenario-specific symptoms
- `lab_samples.csv` - Available lab tests for the disease
- `environment_sites.csv` - Environmental investigation sites
- `npc_truth.json` - NPC profiles and ground truth

**Content Files (`scenarios/{scenario_id}/content/`):**
- `alert.md` - Initial outbreak alert (Day 0)
- `day1_briefing.md` to `day5_briefing.md` - Daily briefings
- `case_definition_template.md` - WHO case definition guidance
- `hypothesis_examples.md` - Hypothesis generation guide
- `interventions.md` - Evidence-based intervention recommendations

## Adding New Scenarios

### Step 1: Create Directory Structure
```bash
mkdir -p scenarios/new_scenario/data
mkdir -p scenarios/new_scenario/content
```

### Step 2: Create Data Files
Copy and adapt data files from an existing scenario:

**Required in `data/`:**
- `villages.csv` - Columns: `village_id`, `village_name`, `population`, scenario-specific risk columns
- `households_seed.csv` - Initial household characteristics
- `individuals_seed.csv` - Initial cases with demographics and symptoms
- `lab_samples.csv` - Available diagnostic tests
- `environment_sites.csv` - Investigation sites (water sources, animal sites, etc.)
- `npc_truth.json` - NPC profiles with scenario-specific knowledge

### Step 3: Create Content Files
**Required in `content/`:**
- `alert.md` - Initial alert from local health authority
- `day1_briefing.md` through `day5_briefing.md` - Daily investigation guidance
- `case_definition_template.md` - WHO standard case definition
- `hypothesis_examples.md` - Hypothesis generation framework
- `interventions.md` - Evidence-based intervention options

### Step 4: Add Risk Model (if needed)
In `outbreak_logic.py`, locate the `assign_infections()` function and add scenario-specific risk calculation:

```python
elif scenario_type == "new_scenario":
    individuals_full = assign_new_scenario_infections(
        individuals_full,
        villages_df,
        households_df,
        target_cases=30,
        epicenter_village="V1"
    )
```

### Step 5: Add to Scenario Selector
In `app.py`, locate the scenario selector (around line 7368) and add:

```python
scenario_options = [
    ("aes_sidero_valley", "🦟 Shadows Over Sidero Valley"),
    ("lepto_rivergate", "🌊 Rivergate After the Storm"),
    ("new_scenario_id", "🔬 New Scenario Name - Location"),
]
```

### Step 6: Configure Scenario Detection
In `app.py`, update the `detect_scenario_type()` function if you need a new scenario type:

```python
def detect_scenario_type(data_dir: str) -> str:
    data_dir_lower = data_dir.lower()
    if "lepto" in data_dir_lower or "maharlika" in data_dir_lower:
        return "lepto"
    elif "new_disease" in data_dir_lower:
        return "new_disease"
    # Default to JE for AES/Sidero Valley
    return "je"
```

## Content Loading System

The application uses `load_scenario_content()` to dynamically load markdown content:

```python
def load_scenario_content(scenario_id: str, content_type: str) -> str:
    """Load scenario-specific content file."""
    content_path = Path(f"scenarios/{scenario_id}/content/{content_type}.md")
    if content_path.exists():
        return content_path.read_text()
    else:
        return f"⚠️ Content file not found: {content_path}"
```

**Usage:**
```python
# Load Day 1 briefing
scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
briefing = load_scenario_content(scenario_id, "day1_briefing")
st.markdown(briefing)
```

## Scenario-Specific Risk Factors

### Japanese Encephalitis (aes_sidero_valley)
**Village-level risk factors (in `villages.csv`):**
- `pig_density` - Pigs per household (amplification hosts)
- `rice_hectares` - Rice cultivation area (vector breeding)
- `JE_vacc_coverage` - Vaccination coverage (0-1)

**Individual/Household exposures:**
- Proximity to pig pens (<100m)
- Distance from rice fields
- Mosquito net use
- Outdoor activities during dusk/dawn
- JE vaccination status

### Leptospirosis (lepto_rivergate)
**Village-level risk factors:**
- `flood_severity` - Post-typhoon flooding (0-1)
- `cleanup_workers` - Number of flood cleanup workers
- `rat_burden` - Rodent infestation level (low/medium/high)

**Individual exposures:**
- Flood water contact (barefoot wading)
- Cleanup work participation
- Water source contamination
- Protective equipment use (boots, gloves)
- Occupation (farmer, fisher, cleanup worker)

## Testing a New Scenario

1. **Data validation:** Ensure all required CSV files have correct columns
2. **Content check:** Verify all required markdown files exist
3. **Load test:** Select scenario in UI, verify no errors
4. **Case generation:** Confirm realistic number of cases (~20-35)
5. **Content display:** Check Day 0 alert, Day 1-5 briefings load correctly
6. **Case definition:** Verify template displays scenario-appropriate criteria
7. **Interventions:** Confirm scenario-specific recommendations appear

## Troubleshooting

**"Content file not found" warnings:**
- Check file exists in `scenarios/{scenario_id}/content/`
- Verify filename matches exactly (e.g., `day1_briefing.md`, not `Day1_Briefing.md`)

**No cases generated or wrong number:**
- Check `individuals_seed.csv` has initial cases
- Verify risk model in `outbreak_logic.py` for your scenario type
- Confirm `target_cases` parameter in risk model

**Scenario doesn't appear in selector:**
- Verify folder name in `scenarios/` directory
- Check scenario added to `scenario_options` in `app.py`
- Restart Streamlit application

**JE-specific content appears in non-JE scenario:**
- Check for hardcoded references in app.py
- Verify `load_scenario_content()` is called with correct scenario_id
- Check scenario type detection logic

## Best Practices

1. **Start from an existing scenario:** Copy and modify rather than create from scratch
2. **Realistic case counts:** Aim for 20-40 cases for pedagogical balance
3. **Geographic clustering:** Concentrate cases in 1-2 epicenter villages
4. **Temporal pattern:** Realistic incubation periods and epidemic curve
5. **Consistent content:** Ensure all content files use consistent terminology
6. **Test thoroughly:** Verify all days (0-5) display correct content
7. **Evidence-based:** Base interventions on WHO/CDC guidance for the disease

## Future Enhancements

Potential additions to the multi-scenario architecture:
- Scenario-specific assets (images, maps)
- Multiple language support per scenario
- Scenario difficulty levels (basic, intermediate, advanced)
- Custom evaluation criteria per scenario
- Scenario-specific NPCs and interview content
- Adaptive difficulty based on learner performance
