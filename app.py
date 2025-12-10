import streamlit as st
import anthropic
import pandas as pd
import plotly.express as px
from datetime import datetime

# Page config
st.set_page_config(
    page_title="FETP Outbreak Sim: Sidero Valley",
    page_icon="🦟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for "Messy" Handwriting and UI
st.markdown("""
<style>
    .main-header {
        background-color: #2E4053;
        color: white;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    /* Simulating messy handwritten notes */
    .handwritten-note {
        font-family: 'Comic Sans MS', 'Chalkboard SE', 'Marker Felt', sans-serif;
        font-size: 16px;
        background-color: #fdf6e3; /* Yellowish paper */
        color: #2c3e50;
        padding: 15px;
        border: 1px solid #d6d6d6;
        box-shadow: 3px 3px 7px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        transform: rotate(-0.5deg);
        line-height: 1.4;
    }
    .handwritten-note:nth-child(even) {
        transform: rotate(1deg);
        background-color: #fffbf0;
    }
    .stChatInput {
        position: fixed;
        bottom: 0;
        padding-bottom: 20px;
        z-index: 1000;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'home'
if 'interview_history' not in st.session_state:
    st.session_state.interview_history = {}
if 'interviewed_characters' not in st.session_state:
    st.session_state.interviewed_characters = set()
if 'private_clinic_unlocked' not in st.session_state:
    st.session_state.private_clinic_unlocked = False
if 'manually_entered_cases' not in st.session_state:
    st.session_state.manually_entered_cases = []
if 'notes' not in st.session_state:
    st.session_state.notes = []

# --- STORY & CHARACTERS ---
STORY_CONTEXT = """
Situation: "The Shaking Sickness" in Sidero Valley. 
Symptoms: High fever, tremors, confusion, seizures.
Setting: Mining region (North), Rice/Pig Farms (South).
"""

CHARACTERS = {
    "dr_chen": {
        "name": "Dr. Elena Chen",
        "role": "Director, St. Mary's Hospital",
        "avatar": "👩‍⚕️",
        "emoji": "👩‍⚕️",
        "personality": "Professional, academic. Relies on data.",
        "truth_document": "You have 6 adult male patients (miners). You suspect toxic gas.",
        "initial_greeting": "I'm convinced this is occupational. All my patients are miners from the north."
    },
    "healer_marcus": {
        "name": "Marcus the Healer",
        "role": "Private Clinic Practitioner",
        "avatar": "🌿",
        "emoji": "🌿",
        "personality": "Suspicious, traditional. Protective of farmers.",
        "truth_document": "You treat farmers and children. They have the shaking sickness too. You keep messy paper notes.",
        "initial_greeting": "My people are sick, but the government only cares about the mine. Why should I help you?"
    }
}

# --- DATASETS ---

# Clean Hospital Data
PUBLIC_CASES = [
    {"ID": "H-01", "Age": 45, "Sex": "M", "Occupation": "Miner", "Onset": "2025-12-08", "Symptoms": "Fever, Tremors", "Status": "Alive"},
    {"ID": "H-02", "Age": 28, "Sex": "M", "Occupation": "Miner", "Onset": "2025-12-09", "Symptoms": "Fever, Confusion", "Status": "Alive"},
    {"ID": "H-03", "Age": 52, "Sex": "M", "Occupation": "Miner", "Onset": "2025-12-09", "Symptoms": "Seizures, Coma", "Status": "Deceased"},
    {"ID": "H-04", "Age": 33, "Sex": "M", "Occupation": "Miner", "Onset": "2025-12-10", "Symptoms": "Fever, Tremors", "Status": "Alive"},
    {"ID": "H-05", "Age": 41, "Sex": "M", "Occupation": "Miner", "Onset": "2025-12-10", "Symptoms": "Fever, Ataxia", "Status": "Alive"},
    {"ID": "H-06", "Age": 29, "Sex": "M", "Occupation": "Miner", "Onset": "2025-12-10", "Symptoms": "Headache, Fever", "Status": "Alive"},
]

# Messy Clinic Notes (Mix of Cases and Non-Cases)
CLINIC_NOTES_PILE = [
    "Dec 7. Sarah (6y F). Pig farm. High fever, shaking hands. Mom says she fell in mud.",
    "Dec 7. Old John (65y M). Farmer. Complains of back pain from planting rice. No fever.",
    "Dec 8. Twin boys (8y M). Farm B. Both vomiting and twitching. Fever very high.",
    "Dec 8. Mary (24y F). Pregnant. Routine checkup. Healthy.",
    "Dec 9. Mrs. Adama (40y F). Collapsed in field. Eyes rolling back. Seizing.",
    "Dec 9. Boy (12y). Cut leg on rusty fence. Tetanus shot given.",
    "Dec 9. Baby K (2y M). High fever, stiff neck, screaming. Fontanelle bulging.",
    "Dec 10. Miner Tom (30y M). Coughing blood. TB suspect. Refer to hospital.",
    "Dec 10. Girl (5y). Pig farm. Fever, confused, can't walk straight.",
    "Dec 10. Farmer Ben (50y). Broken arm from tractor accident.",
    "Dec 11. Grandma Esi (70y). Just old age. Weakness.",
    "Dec 11. Boy (9y). Farm A. Seizures started this morning. Fever 39.5.",
    "Dec 11. Girl (7y). Farm A. Same as brother. Shaking.",
    "Dec 11. Man (45y). Drunk. Sleeping it off.",
    "Dec 12. Woman (33y). Fever, headache, severe tremors in hands."
]

# --- FUNCTIONS ---

def get_ai_response(char_key, user_input, history):
    """Simple AI Responder"""
    char = CHARACTERS[char_key]
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key: return "⚠️ API Key Missing"
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msgs = [{"role": m["role"], "content": m["content"]} for m in history]
        msgs.append({"role": "user", "content": user_input})
        
        system_prompt = f"Roleplay {char['name']}. Context: {STORY_CONTEXT}. Keep answers brief."
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            system=system_prompt,
            messages=msgs
        )
        return response.content[0].text
    except:
        return "System Error."

# --- MAIN APP ---

st.markdown('<div class="main-header"><h1>🏔️ Sidero Valley: Outbreak Investigation</h1></div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### 🕵️ Investigation Hub")
    if st.button("🏠 Briefing"): st.session_state.current_view = 'home'
    if st.button("👥 Interviews"): st.session_state.current_view = 'contacts'
    if st.button("🏥 Hospital Data"): st.session_state.current_view = 'hospital_data'
    if st.button("🏚️ Clinic Data (Triage)"): st.session_state.current_view = 'clinic_data'
    st.markdown("---")
    if st.button("📊 **Master Line List & Analysis**"): st.session_state.current_view = 'analysis'

# VIEWS

if st.session_state.current_view == 'home':
    st.info("MISSION: Investigate cluster of 'Acute Encephalitis' in Sidero Valley.")
    st.write("Start by interviewing Dr. Chen to get the hospital data.")

elif st.session_state.current_view == 'contacts':
    st.markdown("### 👥 Interviews")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Dr. Chen (Hospital)")
        if st.button("Talk to Chen"):
            st.session_state.current_character = 'dr_chen'
            st.session_state.current_view = 'interview'
            st.rerun()
    with col2:
        st.markdown("#### Healer Marcus (Clinic)")
        if st.button("Talk to Marcus"):
            st.session_state.current_character = 'healer_marcus'
            st.session_state.current_view = 'interview'
            st.rerun()

elif st.session_state.current_view == 'interview':
    char = CHARACTERS[st.session_state.current_character]
    if st.session_state.current_character == 'healer_marcus': st.session_state.private_clinic_unlocked = True
    
    st.markdown(f"### 💬 {char['name']}")
    if st.button("🔙 Back"): st.session_state.current_view = 'contacts'; st.rerun()
    
    # Init history
    if st.session_state.current_character not in st.session_state.interview_history:
        st.session_state.interview_history[st.session_state.current_character] = [{"role": "assistant", "content": char['initial_greeting']}]
    
    history = st.session_state.interview_history[st.session_state.current_character]
    for msg in history:
        with st.chat_message(msg['role']): st.write(msg['content'])
            
    if prompt := st.chat_input("Ask a question..."):
        with st.chat_message("user"): st.write(prompt)
        history.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            resp = get_ai_response(st.session_state.current_character, prompt, history[:-1])
            st.write(resp)
        history.append({"role": "assistant", "content": resp})

elif st.session_state.current_view == 'hospital_data':
    st.markdown("### 🏥 Hospital Records (Clean)")
    if 'dr_chen' in st.session_state.interviewed_characters: # Simple check: has user talked to Chen?
        st.dataframe(pd.DataFrame(PUBLIC_CASES))
    else:
        st.warning("🔒 Talk to Dr. Chen to access records.")

elif st.session_state.current_view == 'clinic_data':
    st.markdown("### 🏚️ Private Clinic Records (Triage Task)")
    
    if not st.session_state.private_clinic_unlocked:
        st.warning("🔒 You need to find Healer Marcus first.")
    else:
        st.info("📝 **Task:** Read the notes. Decide if each patient meets the Case Definition (Fever + Neuro symptoms). Ignore non-cases.")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### 📥 The 'Pile' of Notes")
            for note in CLINIC_NOTES_PILE:
                st.markdown(f'<div class="handwritten-note">{note}</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown("#### 💻 Data Entry Form")
            with st.form("entry_form"):
                st.markdown("**Enter New Case**")
                c_id = st.text_input("Patient ID (e.g., C-01)")
                c_age = st.number_input("Age", 0, 100)
                c_sex = st.selectbox("Sex", ["M", "F"])
                c_occ = st.selectbox("Occupation", ["Miner", "Farmer", "Child", "Other"])
                c_onset = st.date_input("Onset Date", value=None)
                c_sympt = st.multiselect("Symptoms", ["Fever", "Tremors", "Seizures", "Confusion", "Vomiting", "Headache", "None"])
                
                submitted = st.form_submit_button("➕ Add to Line List")
                if submitted:
                    if not c_id:
                        st.error("ID required")
                    else:
                        new_case = {
                            "ID": c_id, "Age": c_age, "Sex": c_sex, 
                            "Occupation": c_occ, "Onset": str(c_onset), 
                            "Symptoms": ", ".join(c_sympt), "Status": "Unknown"
                        }
                        st.session_state.manually_entered_cases.append(new_case)
                        st.success(f"Added Case {c_id}")

            st.markdown("---")
            st.markdown(f"**Cases Digitized: {len(st.session_state.manually_entered_cases)}**")
            if st.session_state.manually_entered_cases:
                st.dataframe(pd.DataFrame(st.session_state.manually_entered_cases))

elif st.session_state.current_view == 'analysis':
    st.markdown("## 📊 Master Analytics Dashboard")
    
    # Combine Data
    df_h = pd.DataFrame(PUBLIC_CASES)
    df_h['Source'] = 'Hospital'
    
    if st.session_state.manually_entered_cases:
        df_c = pd.DataFrame(st.session_state.manually_entered_cases)
        df_c['Source'] = 'Clinic (Manual)'
        df_master = pd.concat([df_h, df_c], ignore_index=True)
    else:
        df_master = df_h
        st.warning("⚠️ Only showing Hospital data. Go to 'Clinic Data' to add more cases.")

    # Show Master Table
    with st.expander("📋 View Master Line List", expanded=True):
        st.dataframe(df_master, use_container_width=True)
    
    st.markdown("---")
    
    # Analytics Tabs
    tab1, tab2, tab3 = st.tabs(["📈 Epi Curve", "👥 Demographics", "🤒 Clinical"])
    
    with tab1:
        st.markdown("### Epidemic Curve")
        if 'Onset' in df_master.columns:
            # Simple aggregation
            epi_data = df_master['Onset'].value_counts().reset_index()
            epi_data.columns = ['Date', 'Count']
            epi_data = epi_data.sort_values('Date')
            
            fig = px.bar(epi_data, x='Date', y='Count', title="Cases by Onset Date", color_discrete_sequence=['#E74C3C'])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("No Onset data found.")

    with tab2:
        st.markdown("### Demographics")
        colA, colB = st.columns(2)
        with colA:
            # Sex
            fig_sex = px.pie(df_master, names='Sex', title="Distribution by Sex")
            st.plotly_chart(fig_sex, use_container_width=True)
        with colB:
            # Age Histogram
            fig_age = px.histogram(df_master, x='Age', nbins=10, title="Age Distribution")
            st.plotly_chart(fig_age, use_container_width=True)
            
        # Occupation
        fig_occ = px.bar(df_master['Occupation'].value_counts().reset_index(), x='Occupation', y='count', title="Cases by Occupation")
        st.plotly_chart(fig_occ, use_container_width=True)

    with tab3:
        st.markdown("### Symptom Frequency")
        # Split comma-separated symptoms and count
        all_symptoms = []
        for s in df_master['Symptoms']:
            if s:
                all_symptoms.extend([x.strip() for x in s.split(',')])
        
        if all_symptoms:
            symptom_counts = pd.Series(all_symptoms).value_counts().reset_index()
            symptom_counts.columns = ['Symptom', 'Count']
            fig_sym = px.bar(symptom_counts, x='Count', y='Symptom', orientation='h', title="Most Common Symptoms")
            st.plotly_chart(fig_sym, use_container_width=True)
        else:
            st.info("No symptom data available yet.")