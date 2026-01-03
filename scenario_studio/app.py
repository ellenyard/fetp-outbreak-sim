"""
Scenario Studio - AI-Powered FETP Scenario Designer

A web-based interface for creating and reviewing outbreak investigation scenarios
using Manus.AI (Claude with Computer Use).

Usage:
    streamlit run scenario_studio/app.py
"""

import streamlit as st
from pathlib import Path
import json
from datetime import datetime
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Scenario Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        padding: 20px 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .subheader {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 30px;
    }
    .step-container {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 25px;
        margin: 20px 0;
        border: 1px solid #dee2e6;
    }
    .action-card {
        border: 2px solid #4CAF50;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        margin: 10px 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .progress-step {
        padding: 8px 16px;
        border-radius: 20px;
        margin: 0 5px;
        font-weight: 500;
    }
    .step-complete {
        background: #4CAF50;
        color: white;
    }
    .step-current {
        background: #2196F3;
        color: white;
    }
    .step-pending {
        background: #e0e0e0;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        'current_mode': '🏠 Home',
        'in_wizard': False,
        'wizard_step': 1,
        'scenario_title': '',
        'disease': 'Cholera',
        'setting': '',
        'cultural_context': 'Latin America',
        'population': 3000,
        'difficulty': 'Medium',
        'learning_objectives': [],
        'storyline_generated': False,
        'generated_storyline': None,
        'review_mode': False,
        'review_target': None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_state(key, default=None):
    """Safely get session state value."""
    return st.session_state.get(key, default)


def set_state(key, value):
    """Set session state value."""
    st.session_state[key] = value


# ============================================================================
# NAVIGATION
# ============================================================================

def render_sidebar():
    """Render sidebar navigation."""
    with st.sidebar:
        st.markdown("# 🎬 Scenario Studio")
        st.markdown("*AI-Powered Design Assistant*")
        st.markdown("---")
        
        # Mode selection
        if not get_state('in_wizard'):
            mode = st.radio(
                "Navigation",
                ["🏠 Home", "✨ New Scenario", "🔍 Review Existing", "⚙️ Settings"],
                label_visibility="collapsed"
            )
            set_state('current_mode', mode)
        else:
            st.markdown("### 🎯 Active Project")
            st.info(f"**{get_state('scenario_title') or 'Untitled Scenario'}**\n\nStep {get_state('wizard_step')} of 7")
            
            if st.button("❌ Exit Wizard", use_container_width=True):
                if st.session_state.get('confirm_exit'):
                    set_state('in_wizard', False)
                    set_state('wizard_step', 1)
                    set_state('current_mode', '🏠 Home')
                    set_state('confirm_exit', False)
                    st.rerun()
                else:
                    st.session_state.confirm_exit = True
                    st.warning("Click again to confirm exit (unsaved work will be lost)")
        
        st.markdown("---")
        
        # Quick stats
        st.markdown("### 📊 Quick Stats")
        project_dir = Path("/mnt/project")
        scenarios_dir = project_dir / "scenarios"
        
        if scenarios_dir.exists():
            n_scenarios = len([d for d in scenarios_dir.iterdir() if d.is_dir()])
            st.metric("Total Scenarios", n_scenarios)
        
        # Help section
        st.markdown("---")
        st.markdown("### 💡 Help")
        with st.expander("🎥 Quick Start"):
            st.markdown("""
            1. Click **New Scenario**
            2. Fill in basic information
            3. Let AI generate storyline
            4. Review and export!
            """)
        
        with st.expander("🔍 Review Mode"):
            st.markdown("""
            Use this to:
            - Analyze existing scenarios
            - Get improvement suggestions
            - Fix consistency issues
            - Update difficulty
            """)


# ============================================================================
# PROGRESS BAR
# ============================================================================

def render_progress_bar(current_step: int, total_steps: int = 7):
    """Render a visual progress bar."""
    steps = ["Basic", "Objectives", "Storyline", "Data", "NPCs", "Artifacts", "Review"]
    
    cols = st.columns(total_steps)
    
    for i, (col, label) in enumerate(zip(cols, steps)):
        with col:
            if i < current_step - 1:
                st.markdown(f'<div class="progress-step step-complete">✓ {label}</div>', unsafe_allow_html=True)
            elif i == current_step - 1:
                st.markdown(f'<div class="progress-step step-current">● {label}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="progress-step step-pending">○ {label}</div>', unsafe_allow_html=True)
    
    st.markdown("---")


# ============================================================================
# HOME SCREEN
# ============================================================================

def render_home():
    """Render home screen."""
    st.markdown('<div class="main-header">🎬 SCENARIO STUDIO</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheader">AI-Powered Outbreak Investigation Designer</div>', unsafe_allow_html=True)
    
    st.markdown("### Welcome! 👋")
    st.markdown("Create realistic FETP training scenarios with AI assistance.")
    
    st.markdown("")
    
    # Quick action cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="action-card">
            <h3>✨ New Scenario</h3>
            <p style="color: #666;">Create from scratch with AI guidance</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start Creating →", key="home_new", use_container_width=True, type="primary"):
            set_state('current_mode', '✨ New Scenario')
            set_state('in_wizard', True)
            set_state('wizard_step', 1)
            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="action-card" style="border-color: #2196F3;">
            <h3>🔍 Review Existing</h3>
            <p style="color: #666;">Analyze and improve scenarios</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Open Review Mode →", key="home_review", use_container_width=True):
            set_state('current_mode', '🔍 Review Existing')
            st.rerun()
    
    with col3:
        st.markdown("""
        <div class="action-card" style="border-color: #FF9800;">
            <h3>📚 Browse Library</h3>
            <p style="color: #666;">View all scenarios</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Browse →", key="home_browse", use_container_width=True):
            list_scenarios()
    
    st.markdown("---")
    
    # Recent activity
    st.markdown("### 📂 Recent Scenarios")
    list_scenarios(limit=5)


def list_scenarios(limit=None):
    """List available scenarios."""
    project_dir = Path("/mnt/project")
    scenarios_dir = project_dir / "scenarios"
    
    if not scenarios_dir.exists():
        st.info("No scenarios found. Create your first one above!")
        return
    
    scenarios = [d for d in scenarios_dir.iterdir() if d.is_dir()]
    
    if not scenarios:
        st.info("No scenarios found yet.")
        return
    
    if limit:
        scenarios = scenarios[:limit]
    
    for scenario_dir in scenarios:
        scenario_file = scenario_dir / "scenario.json"
        
        col1, col2, col3 = st.columns([4, 2, 2])
        
        with col1:
            st.markdown(f"**📁 {scenario_dir.name}**")
            if scenario_file.exists():
                with open(scenario_file) as f:
                    data = json.load(f)
                    st.caption(f"Disease: {data.get('disease', 'Unknown')} | Population: {data.get('population', 'N/A')}")
            else:
                st.caption("Scenario data not available")
        
        with col2:
            if st.button("Review", key=f"review_{scenario_dir.name}"):
                set_state('review_target', str(scenario_dir))
                set_state('current_mode', '🔍 Review Existing')
                st.rerun()
        
        with col3:
            if st.button("Export", key=f"export_{scenario_dir.name}"):
                st.info(f"Export functionality coming soon for {scenario_dir.name}")
        
        st.markdown("---")


# ============================================================================
# WIZARD - STEP 1: BASIC INFO
# ============================================================================

def render_step_1_basic_info():
    """Step 1: Basic scenario information."""
    st.markdown("## Step 1: Basic Information")
    st.markdown("Tell us about the outbreak scenario you want to create.")
    
    st.markdown('<div class="step-container">', unsafe_allow_html=True)
    
    # Scenario title
    title = st.text_input(
        "Scenario Title *",
        value=get_state('scenario_title', ''),
        placeholder="E.g., Cholera Outbreak - Puerto Esperanza",
        help="Give your scenario a descriptive name"
    )
    set_state('scenario_title', title)
    
    # Disease selection
    col1, col2 = st.columns([2, 1])
    
    with col1:
        disease_options = [
            "Cholera", "Measles", "Japanese Encephalitis", "Leptospirosis",
            "Ebola", "Dengue", "Typhoid", "Hepatitis A", "COVID-19",
            "Malaria", "Tuberculosis", "Yellow Fever", "Meningitis",
            "Influenza", "Norovirus", "Salmonella", "E. coli"
        ]
        
        disease = st.selectbox(
            "Disease/Pathogen *",
            options=disease_options,
            index=disease_options.index(get_state('disease', 'Cholera')),
            help="Select the disease for this outbreak scenario"
        )
        set_state('disease', disease)
    
    with col2:
        if disease:
            st.markdown("##### Quick Facts")
            suggestions = get_disease_suggestions(disease)
            st.caption(f"**Transmission:** {suggestions['transmission']}")
            st.caption(f"**Attack Rate:** {suggestions['attack_rate']}")
            st.caption(f"**Incubation:** {suggestions['incubation']}")
    
    # Setting
    st.markdown("---")
    setting = st.text_area(
        "Geographic & Cultural Setting *",
        value=get_state('setting', ''),
        height=100,
        placeholder="E.g., Coastal fishing town in Latin America after Hurricane Maria damaged water infrastructure",
        help="Describe the location and context for the outbreak"
    )
    set_state('setting', setting)
    
    # Cultural context
    col1, col2 = st.columns(2)
    
    with col1:
        cultural_options = ["Latin America", "Sub-Saharan Africa", "South Asia", 
                           "Southeast Asia", "Eastern Europe", "Middle East", "Pacific Islands", "Other"]
        
        culture = st.selectbox(
            "Cultural/Regional Context",
            options=cultural_options,
            index=cultural_options.index(get_state('cultural_context', 'Latin America'))
        )
        set_state('cultural_context', culture)
    
    with col2:
        population = st.number_input(
            "Target Population Size *",
            min_value=500,
            max_value=50000,
            value=get_state('population', 3000),
            step=500,
            help="Total population in the affected area"
        )
        set_state('population', population)
    
    # Difficulty
    st.markdown("---")
    st.markdown("##### Difficulty Level *")
    
    difficulty = st.radio(
        "Select difficulty level",
        options=["Easy", "Medium", "Hard"],
        index=["Easy", "Medium", "Hard"].index(get_state('difficulty', 'Medium')),
        horizontal=True,
        label_visibility="collapsed"
    )
    set_state('difficulty', difficulty)
    
    # Difficulty explanation
    difficulty_info = {
        "Easy": "Strong ORs (5-8), minimal confounding, obvious red herrings",
        "Medium": "Moderate ORs (3-5), some confounding, plausible red herrings",
        "Hard": "Weak ORs (1.5-3), strong confounding, sophisticated red herrings"
    }
    
    st.info(f"**{difficulty} Difficulty:** {difficulty_info[difficulty]}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Navigation
    st.markdown("")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("← Back to Home", use_container_width=True):
            set_state('in_wizard', False)
            set_state('current_mode', '🏠 Home')
            st.rerun()
    
    with col2:
        if st.button("Next: Learning Objectives →", use_container_width=True, type="primary"):
            if validate_step_1():
                set_state('wizard_step', 2)
                st.rerun()
            else:
                st.error("Please fill in all required fields (*)")


def validate_step_1() -> bool:
    """Validate step 1 required fields."""
    required = ['scenario_title', 'disease', 'setting']
    return all(get_state(field) for field in required)


def get_disease_suggestions(disease: str) -> dict:
    """Get basic disease information."""
    disease_db = {
        "Cholera": {
            "transmission": "Waterborne",
            "attack_rate": "1-5%",
            "incubation": "1-5 days",
            "risk_factors": ["Contaminated water", "Poor sanitation", "Crowding"]
        },
        "Measles": {
            "transmission": "Airborne",
            "attack_rate": "10-40%",
            "incubation": "10-14 days",
            "risk_factors": ["Unvaccinated", "Crowding", "School exposure"]
        },
        "Japanese Encephalitis": {
            "transmission": "Vector (mosquito)",
            "attack_rate": "0.5-2%",
            "incubation": "5-15 days",
            "risk_factors": ["Pigs nearby", "Rice paddies", "Evening outdoors", "Unvaccinated"]
        },
        "Leptospirosis": {
            "transmission": "Waterborne/animal",
            "attack_rate": "1-10%",
            "incubation": "2-30 days",
            "risk_factors": ["Flooding", "Animal exposure", "Contaminated water"]
        }
    }
    
    return disease_db.get(disease, {
        "transmission": "Contact/Droplet/Vector",
        "attack_rate": "Varies",
        "incubation": "Varies",
        "risk_factors": ["To be determined"]
    })


# ============================================================================
# WIZARD - STEP 2: LEARNING OBJECTIVES
# ============================================================================

def render_step_2_objectives():
    """Step 2: Learning objectives."""
    st.markdown("## Step 2: Learning Objectives")
    st.markdown("What should trainees learn from this scenario?")
    
    st.markdown('<div class="step-container">', unsafe_allow_html=True)
    
    # Get or initialize objectives
    objectives = get_state('learning_objectives', [])
    
    if not objectives:
        objectives = ['', '', '', '']
    
    # Objective inputs
    st.markdown("##### Core Learning Objectives")
    st.caption("Enter 3-5 specific, measurable objectives")
    
    updated_objectives = []
    
    for i in range(4):
        obj = st.text_input(
            f"Objective {i+1}" + (" *" if i < 2 else " (optional)"),
            value=objectives[i] if i < len(objectives) else '',
            placeholder=f"E.g., {'Design water quality sampling strategy' if i == 0 else 'Calculate attack rates by neighborhood' if i == 1 else 'Communicate risk without causing panic' if i == 2 else 'Implement emergency WASH interventions'}",
            key=f"obj_{i}"
        )
        if obj.strip():
            updated_objectives.append(obj.strip())
    
    set_state('learning_objectives', updated_objectives)
    
    # AI suggestions
    st.markdown("---")
    st.markdown("##### 🤖 AI-Generated Suggestions")
    
    if st.button("Generate Objective Suggestions", use_container_width=True):
        with st.spinner("Generating suggestions based on your disease and setting..."):
            suggestions = generate_objective_suggestions(
                get_state('disease'),
                get_state('setting'),
                get_state('difficulty')
            )
            set_state('objective_suggestions', suggestions)
    
    if get_state('objective_suggestions'):
        st.markdown("**Suggested objectives (click to add):**")
        suggestions = get_state('objective_suggestions')
        
        for i, suggestion in enumerate(suggestions):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"• {suggestion}")
            with col2:
                if st.button("Add", key=f"add_sugg_{i}"):
                    current = get_state('learning_objectives', [])
                    if suggestion not in current:
                        current.append(suggestion)
                        set_state('learning_objectives', current)
                        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Navigation
    st.markdown("")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("← Back", use_container_width=True):
            set_state('wizard_step', 1)
            st.rerun()
    
    with col2:
        if st.button("Next: Generate Storyline →", use_container_width=True, type="primary"):
            if validate_step_2():
                set_state('wizard_step', 3)
                st.rerun()
            else:
                st.error("Please enter at least 2 learning objectives")


def validate_step_2() -> bool:
    """Validate step 2."""
    objectives = get_state('learning_objectives', [])
    return len(objectives) >= 2


def generate_objective_suggestions(disease: str, setting: str, difficulty: str) -> list:
    """Generate learning objective suggestions (mock for now)."""
    # In full implementation, this would call Manus.AI
    # For now, return relevant suggestions based on disease
    
    suggestions_db = {
        "Cholera": [
            "Calculate and interpret attack rates by neighborhood",
            "Design water quality sampling strategy",
            "Distinguish point-source from continuous common source outbreaks",
            "Communicate risk to affected communities without causing panic",
            "Implement emergency WASH interventions",
            "Design case-control study for waterborne disease"
        ],
        "Japanese Encephalitis": [
            "Apply One Health approach to vector-borne disease investigation",
            "Design environmental mosquito sampling strategy",
            "Interpret animal surveillance data (pig seroprevalence)",
            "Recognize age-specific attack rate patterns",
            "Implement emergency vector control measures",
            "Navigate political sensitivities around agricultural practices"
        ]
    }
    
    return suggestions_db.get(disease, [
        "Describe cases by person, place, and time",
        "Develop working case definition",
        "Design appropriate analytic study",
        "Implement evidence-based interventions"
    ])[:5]


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    
    mode = get_state('current_mode')
    
    if get_state('in_wizard'):
        # Wizard mode
        step = get_state('wizard_step')
        render_progress_bar(step)
        
        if step == 1:
            render_step_1_basic_info()
        elif step == 2:
            render_step_2_objectives()
        elif step == 3:
            # Step 3 will be created next
            st.info("Step 3: AI Storyline Generation - Coming in next file!")
        else:
            st.info(f"Step {step} under construction...")
    
    elif mode == '🏠 Home':
        render_home()
    
    elif mode == '🔍 Review Existing':
        render_review_mode()
    
    elif mode == '⚙️ Settings':
        render_settings()


def render_review_mode():
    """Review existing scenario mode."""
    st.markdown("## 🔍 Review Existing Scenario")
    
    review_target = get_state('review_target')
    
    if not review_target:
        st.markdown("### Select a scenario to review:")
        st.markdown("**Option 1: Review the JE Scenario from Project Files**")
        
        if st.button("📁 Review JE Scenario (Current Project)", type="primary", use_container_width=True):
            set_state('review_target', '/mnt/project')
            st.rerun()
        
        st.markdown("---")
        st.markdown("**Option 2: Review from Scenarios Library**")
        list_scenarios()
    else:
        target_path = Path(review_target)
        st.markdown(f"### Reviewing: `{target_path.name if target_path.name else 'JE Scenario'}`")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("← Back"):
                set_state('review_target', None)
                set_state('review_report', None)
                st.rerun()
        
        st.markdown("---")
        
        # Collect scenario files
        scenario_files = collect_scenario_files(target_path)
        
        if not scenario_files:
            st.error("No scenario files found in this directory.")
            return
        
        # Show file inventory
        with st.expander("📂 Files Found", expanded=False):
            for name, path in scenario_files.items():
                st.text(f"✓ {name}")
        
        st.markdown("### 🤖 AI-Powered Review")
        
        # Focus area selection
        focus_areas = st.multiselect(
            "Focus areas (leave empty for comprehensive review)",
            ["Narrative Consistency", "Epidemiological Accuracy", "Data Quality", 
             "NPC Dialogue", "Pedagogical Alignment", "Plot & Red Herrings", "Technical Issues"],
            help="Select specific areas to focus on, or leave empty for full review"
        )
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button("🚀 Run Comprehensive Review", type="primary", use_container_width=True):
                run_scenario_review(scenario_files, focus_areas)
        
        with col2:
            if st.button("📊 Quick Check", use_container_width=True):
                run_quick_check(scenario_files)
        
        # Display review report if available
        review_report = get_state('review_report')
        if review_report:
            display_review_report(review_report)


def collect_scenario_files(base_path: Path) -> Dict[str, str]:
    """Collect all scenario files from a directory."""
    files = {}
    
    # Check for common scenario files
    file_patterns = {
        "app.py": "Main simulation code",
        "outbreak_logic.py": "Backend logic",
        "npc_truth.json": "NPC personalities & knowledge",
        "villages.csv": "Village data",
        "households_seed.csv": "Household seed data",
        "individuals_seed.csv": "Individual seed data",
        "lab_samples.csv": "Laboratory samples",
        "environment_sites.csv": "Environmental sampling sites"
    }
    
    for filename, description in file_patterns.items():
        filepath = base_path / filename
        if filepath.exists():
            files[f"{filename} ({description})"] = str(filepath)
    
    return files


def run_scenario_review(scenario_files: Dict[str, str], focus_areas: List[str]):
    """Execute AI review of scenario."""
    try:
        from scenario_studio.utils.manus_executor import ScenarioReviewer
        
        with st.spinner("🤖 Manus.AI is analyzing your scenario... This may take 1-2 minutes."):
            reviewer = ScenarioReviewer()
            
            # Convert focus areas to tags
            focus_tags = [area.lower().replace(" ", "_") for area in focus_areas] if focus_areas else ["all"]
            
            report = reviewer.review_scenario(scenario_files, focus_tags)
            
            if report.get("error"):
                st.error(f"Review failed: {report.get('message')}")
                with st.expander("🔍 Diagnostic Information"):
                    st.json(report.get('trace', []))
            else:
                set_state('review_report', report)
                st.success("✅ Review complete!")
                st.rerun()
    
    except ImportError:
        st.error("Manus executor not found. Make sure utils/manus_executor.py is in place.")
    except Exception as e:
        st.error(f"Review failed: {str(e)}")
        st.exception(e)


def run_quick_check(scenario_files: Dict[str, str]):
    """Run quick validation checks without full AI review."""
    with st.spinner("Running quick checks..."):
        import pandas as pd
        import json
        
        checks = {
            "Files Present": "PASS" if len(scenario_files) >= 5 else "FAIL",
            "NPCs Defined": "UNKNOWN",
            "Data Integrity": "UNKNOWN"
        }
        
        # Check NPC file
        npc_file = next((path for name, path in scenario_files.items() if "npc_truth" in name), None)
        if npc_file:
            try:
                with open(npc_file) as f:
                    npcs = json.load(f)
                    checks["NPCs Defined"] = f"PASS ({len(npcs)} NPCs)"
            except:
                checks["NPCs Defined"] = "FAIL"
        
        # Check CSV integrity
        csv_files = [path for name, path in scenario_files.items() if path.endswith('.csv')]
        try:
            for csv_path in csv_files:
                df = pd.read_csv(csv_path)
                if df.empty:
                    checks["Data Integrity"] = "FAIL (empty files)"
                    break
            else:
                checks["Data Integrity"] = f"PASS ({len(csv_files)} CSVs)"
        except:
            checks["Data Integrity"] = "FAIL"
        
        st.markdown("### Quick Check Results")
        for check, result in checks.items():
            if "PASS" in result:
                st.success(f"✅ {check}: {result}")
            elif "FAIL" in result:
                st.error(f"❌ {check}: {result}")
            else:
                st.info(f"ℹ️ {check}: {result}")
        
        st.info("💡 Run 'Comprehensive Review' for detailed AI analysis")


def display_review_report(report: Dict[str, Any]):
    """Display comprehensive review report."""
    st.markdown("---")
    st.markdown("## 📋 Review Report")
    
    # Overall status
    status = report.get("overall_status", "UNKNOWN")
    status_colors = {
        "PASS": "🟢",
        "NEEDS_WORK": "🟡",
        "CRITICAL": "🔴"
    }
    
    st.markdown(f"### {status_colors.get(status, '⚪')} Overall Status: {status}")
    st.markdown(report.get("summary", "No summary available"))
    
    st.markdown("---")
    
    # Categories
    categories = report.get("categories", {})
    
    tabs = st.tabs(["📖 Narrative", "🔬 Epidemiology", "📊 Data", "👥 NPCs", "🎯 Pedagogy", "🕵️ Plot", "⚙️ Technical"])
    
    category_keys = ["narrative", "epidemiology", "data_quality", "npcs", "pedagogy", "plot", "technical"]
    
    for tab, key in zip(tabs, category_keys):
        with tab:
            cat_data = categories.get(key, {})
            status = cat_data.get("status", "UNKNOWN")
            
            st.markdown(f"**Status:** {status_colors.get(status, '⚪')} {status}")
            
            findings = cat_data.get("findings", [])
            if findings:
                st.markdown("**Findings:**")
                for finding in findings:
                    st.markdown(f"• {finding}")
            
            suggestions = cat_data.get("suggestions", [])
            if suggestions:
                st.markdown("**Suggestions:**")
                for suggestion in suggestions:
                    st.markdown(f"💡 {suggestion}")
    
    # Priorities
    st.markdown("---")
    st.markdown("### 🎯 Action Items by Priority")
    
    priorities = report.get("priorities", {})
    
    if priorities.get("critical"):
        st.error("**🔴 Critical Issues:**")
        for item in priorities["critical"]:
            st.markdown(f"- {item}")
    
    if priorities.get("high"):
        st.warning("**🟡 High Priority:**")
        for item in priorities["high"]:
            st.markdown(f"- {item}")
    
    if priorities.get("medium"):
        st.info("**🔵 Medium Priority:**")
        for item in priorities["medium"]:
            st.markdown(f"- {item}")
    
    if priorities.get("low"):
        with st.expander("🟢 Low Priority Items"):
            for item in priorities.get("low", []):
                st.markdown(f"- {item}")
    
    # Export report
    st.markdown("---")
    if st.button("📥 Export Report as JSON"):
        report_json = json.dumps(report, indent=2)
        st.download_button(
            "Download Report",
            report_json,
            "review_report.json",
            "application/json"
        )


def render_settings():
    """Settings page."""
    st.markdown("## ⚙️ Settings")
    
    st.markdown("### API Configuration")
    st.info("Anthropic API key is configured via Streamlit secrets.")
    
    st.markdown("### Output Preferences")
    
    output_dir = st.text_input(
        "Default output directory",
        value="/mnt/project/scenarios"
    )
    
    st.markdown("### AI Generation Settings")
    
    temperature = st.slider(
        "Creativity level (temperature)",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1,
        help="Higher = more creative but less predictable"
    )
    
    st.markdown("### About")
    st.markdown("""
    **Scenario Studio v0.1**
    
    Created for FETP training program development.
    
    Uses Manus.AI (Claude with Computer Use) to assist scenario designers.
    """)


if __name__ == "__main__":
    main()
