import streamlit as st
import anthropic
from datetime import datetime
import json

# Page config
st.set_page_config(
    page_title="FETP Outbreak Investigation Simulation",
    page_icon="🦠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for FETP branding
st.markdown("""
<style>
    .main-header {
        background-color: #FF6B35;
        color: white;
        padding: 20px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .case-marker {
        color: #D32F2F;
        font-size: 24px;
    }
    .character-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        border-left: 4px solid #FF6B35;
    }
    .interview-bubble {
        background-color: #E3F2FD;
        padding: 12px;
        border-radius: 10px;
        margin: 8px 0;
    }
    .user-bubble {
        background-color: #FFF3E0;
        padding: 12px;
        border-radius: 10px;
        margin: 8px 0;
    }
    .objective-complete {
        color: #4CAF50;
    }
    .objective-pending {
        color: #9E9E9E;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'map'
if 'interview_history' not in st.session_state:
    st.session_state.interview_history = {}
if 'current_character' not in st.session_state:
    st.session_state.current_character = None
if 'notes' not in st.session_state:
    st.session_state.notes = []
if 'day' not in st.session_state:
    st.session_state.day = 1
if 'interviewed_characters' not in st.session_state:
    st.session_state.interviewed_characters = set()

# Character database with truth documents
CHARACTERS = {
    "dr_mensah": {
        "name": "Dr. Kwame Mensah",
        "role": "District Health Officer",
        "emoji": "👨‍⚕️",
        "personality": "Professional, knowledgeable, somewhat formal. Provides clear medical information.",
        "truth_document": """
        - District Health Officer for Riverside District for 8 years
        - First case reported on March 3rd at the health center
        - Total of 15 confirmed cases as of March 10th
        - All cases present with severe watery diarrhea (described as "rice water"), vomiting, and dehydration
        - 3 deaths so far (case fatality rate ~20%)
        - Most severe cases are children under 5 and elderly
        - Cases are clustered in the northern part of Riverside Village, primarily Neighborhood A
        - Health center has limited supplies of ORS and IV fluids
        - No laboratory confirmation yet - samples sent to National Lab 3 days ago
        - Suspects it might be cholera based on clinical presentation
        - Village has two main water sources: Well #1 (north) and Well #2 (south)
        - Well #1 serves about 60 households in Neighborhood A
        - Well #2 serves about 40 households in Neighborhood B
        - Most cases are from families using Well #1
        - No cases reported from Neighborhood B (Well #2 users)
        - Village has no piped water system
        - Last cholera outbreak in district was 5 years ago
        - Concerned about spread during upcoming market day (2 days away)
        """,
        "initial_greeting": "Welcome to Riverside Village. I'm Dr. Mensah, the District Health Officer. We've been dealing with a serious outbreak of severe diarrheal illness. I'm very glad the FETP team is here to help us investigate."
    },
    "mrs_abena": {
        "name": "Mrs. Abena Osei",
        "role": "Community Health Worker",
        "emoji": "👩‍⚕️",
        "personality": "Warm, talkative, very familiar with the community. Knows personal details about families.",
        "truth_document": """
        - Community health worker in Riverside Village for 15 years
        - Lives in Neighborhood A, uses Well #1 herself
        - Knows most of the affected families personally
        - First case was 4-year-old Sarah Mensah (no relation to Dr. Mensah) on March 3rd
        - Sarah's mother brought her to health center with severe diarrhea and vomiting
        - By March 5th, Sarah's two siblings also became ill
        - Most cases are children, but some adults affected too
        - Noticed that affected families all live within 200 meters of Well #1
        - Her own family drinks boiled water, hasn't gotten sick
        - Some families drink water directly from the well without treatment
        - Well #1 is an open well (no proper cover) about 15 meters deep
        - During last month's heavy rains, she noticed the well water looked cloudy for a few days
        - Saw children playing near the well and animals (goats) drinking from buckets nearby
        - One family reported their well water "tasted different" starting in late February
        - Well #2 is deeper (25 meters) and has a concrete cover with hand pump
        - Families using Well #2 have not reported any illness
        - Village women usually collect water early morning and evening
        - Some families store water in containers for several days
        """,
        "initial_greeting": "Hello! I'm Abena, the community health worker here. I've lived in this village my whole life. This outbreak has been terrible - I know many of these families personally. How can I help?"
    },
    "chief_okoye": {
        "name": "Chief Adebayo Okoye",
        "role": "Village Chief",
        "emoji": "👴",
        "personality": "Respected elder, speaks carefully, concerned about village reputation. Protective of community.",
        "truth_document": """
        - Village chief for 20 years
        - Very concerned about outbreak affecting village's reputation and economy
        - Market day is in 2 days - worried about canceling it (major income source for village)
        - Well #1 was dug 30 years ago by his father
        - Well #2 was built 10 years ago with NGO support (why it's better constructed)
        - Knows there have been problems with Well #1 for years
        - Last year during rainy season, noticed the area around Well #1 floods
        - Village latrine is located about 30 meters uphill from Well #1
        - The latrine is old (15 years) and in poor condition - cracks visible in structure
        - After heavy rains in February, the latrine pit overflowed slightly
        - He wanted to relocate the latrine but village couldn't afford it
        - Some community members complained about Well #1 water quality but continued using it (free, close to homes)
        - Well #2 requires small payment for maintenance (10 shillings per bucket)
        - Poorer families prefer free Well #1 despite quality concerns
        - Willing to close Well #1 if investigators recommend it, but worried about water access for poor families
        - Can help organize community meeting to discuss interventions
        - Village has about 100 households total
        """,
        "initial_greeting": "Welcome, welcome. I am Chief Okoye. This outbreak troubles me deeply. Our village has always been healthy. I hope you can help us quickly - we have important market day coming soon."
    },
    "mohammed": {
        "name": "Mohammed Hassan",
        "role": "Water Vendor",
        "emoji": "🚰",
        "personality": "Young, entrepreneurial, observant. Slightly defensive about his business.",
        "truth_document": """
        - 25-year-old water vendor, sells treated water from Well #2
        - Charges 10 shillings per 20-liter container
        - Business has been slow because most families use free Well #1
        - Since outbreak started, more families are buying his water (business is up)
        - He treats water from Well #2 with chlorine tablets before selling
        - Never gotten sick himself, none of his customers have gotten sick
        - Has been warning people for months that Well #1 water isn't safe
        - Noticed several concerning things about Well #1:
          * Water sometimes has brown tinge after rains
          * Frogs and insects often found in the well
          * No cover - leaves, dirt, and debris fall in
          * Children sometimes drop buckets in the water while playing
          * Saw a dead rat floating in the well once (about 3 months ago)
        - After February rains, he noticed the area around Well #1 was muddy and smelled bad
        - Suspects runoff from the latrine might be seeping into Well #1
        - The ground slopes from the latrine toward the well
        - Offered to sell chlorine tablets to Well #1 users but they said too expensive
        - Knows basic water treatment from NGO training 2 years ago
        - Can demonstrate proper chlorination if asked
        - Willing to help distribute safe water during outbreak if paid fairly
        - His water source (Well #2) has never had any problems
        """,
        "initial_greeting": "Good morning. I'm Mohammed, I sell water here. I've been saying for months that Well #1 isn't safe, but people don't want to pay for clean water. Now look what's happened."
    }
}

# Case data
CASES = [
    {"id": 1, "name": "Sarah M.", "age": 4, "sex": "F", "onset": "Mar 3", "neighborhood": "A", "well": 1},
    {"id": 2, "name": "David K.", "age": 6, "sex": "M", "onset": "Mar 4", "neighborhood": "A", "well": 1},
    {"id": 3, "name": "Grace O.", "age": 3, "sex": "F", "onset": "Mar 4", "neighborhood": "A", "well": 1},
    {"id": 4, "name": "Mama Esi", "age": 67, "sex": "F", "onset": "Mar 5", "neighborhood": "A", "well": 1},
    {"id": 5, "name": "Kofi A.", "age": 8, "sex": "M", "onset": "Mar 5", "neighborhood": "A", "well": 1},
    {"id": 6, "name": "Baby Ama", "age": 1, "sex": "F", "onset": "Mar 5", "neighborhood": "A", "well": 1},
    {"id": 7, "name": "Peter M.", "age": 5, "sex": "M", "onset": "Mar 6", "neighborhood": "A", "well": 1},
    {"id": 8, "name": "Ruth N.", "age": 7, "sex": "F", "onset": "Mar 6", "neighborhood": "A", "well": 1},
    {"id": 9, "name": "Samuel O.", "age": 45, "sex": "M", "onset": "Mar 6", "neighborhood": "A", "well": 1},
    {"id": 10, "name": "Mary K.", "age": 4, "sex": "F", "onset": "Mar 7", "neighborhood": "A", "well": 1},
    {"id": 11, "name": "James T.", "age": 6, "sex": "M", "onset": "Mar 7", "neighborhood": "A", "well": 1},
    {"id": 12, "name": "Fatima A.", "age": 35, "sex": "F", "onset": "Mar 8", "neighborhood": "A", "well": 1},
    {"id": 13, "name": "Ibrahim S.", "age": 9, "sex": "M", "onset": "Mar 8", "neighborhood": "A", "well": 1},
    {"id": 14, "name": "Blessing M.", "age": 2, "sex": "F", "onset": "Mar 9", "neighborhood": "A", "well": 1},
    {"id": 15, "name": "Joseph K.", "age": 72, "sex": "M", "onset": "Mar 9", "neighborhood": "A", "well": 1},
]

def get_ai_response(character_key, user_question, conversation_history):
    """Get response from Claude API based on character's truth document"""
    
    character = CHARACTERS[character_key]
    
    # Build the system prompt
    system_prompt = f"""You are roleplaying as {character['name']}, a {character['role']} in Riverside Village during a cholera outbreak investigation.

PERSONALITY: {character['personality']}

TRUTH DOCUMENT (information you know):
{character['truth_document']}

INSTRUCTIONS:
1. Stay in character at all times
2. Only share information from your truth document
3. Answer based on what this character would realistically know
4. If asked something not in your truth document, respond naturally as the character would:
   - "I'm not sure about that"
   - "You'd need to ask [other character] about that"
   - Or make a reasonable inference that doesn't contradict the truth document
5. Be conversational and natural
6. Reveal information progressively - don't dump everything at once
7. Some information should only come out if specifically asked
8. Show appropriate emotion (concern for outbreak, etc.)

Remember: You are being interviewed by an FETP epidemiologist investigating this outbreak."""

    # Get API key from secrets
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        return "⚠️ API key not configured. Please add ANTHROPIC_API_KEY to Streamlit secrets."
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Build messages from conversation history
        messages = []
        for entry in conversation_history:
            messages.append({"role": "user", "content": entry["question"]})
            messages.append({"role": "assistant", "content": entry["response"]})
        
        # Add current question
        messages.append({"role": "user", "content": user_question})
        
        # Get response from Claude
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        
        return response.content[0].text
        
    except Exception as e:
        return f"⚠️ Error communicating with AI: {str(e)}"

# Header
st.markdown("""
<div class="main-header">
    <h1>🦠 FETP Outbreak Investigation Simulation</h1>
    <p style="margin:0;">Day 1: Initial Investigation | Riverside Village Cholera Outbreak | March 10, 2025</p>
</div>
""", unsafe_allow_html=True)

# Top bar info
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Day", f"Day {st.session_state.day}")
with col2:
    st.metric("Confirmed Cases", "15")
with col3:
    st.metric("Deaths", "3")
with col4:
    st.metric("Characters Interviewed", len(st.session_state.interviewed_characters))

# Sidebar navigation
with st.sidebar:
    st.markdown("### 📊 Navigation")
    
    if st.button("📍 Map View", use_container_width=True):
        st.session_state.current_view = 'map'
        st.rerun()
    
    if st.button("👥 Contacts", use_container_width=True):
        st.session_state.current_view = 'contacts'
        st.rerun()
    
    if st.button("📋 Case List", use_container_width=True):
        st.session_state.current_view = 'cases'
        st.rerun()
    
    if st.button("✍️ Investigation Notes", use_container_width=True):
        st.session_state.current_view = 'notes'
        st.rerun()
    
    if st.button("🎯 Objectives", use_container_width=True):
        st.session_state.current_view = 'objectives'
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 🔬 Quick Stats")
    st.info(f"""
    **Attack Rate (Well #1 users):** ~25%
    
    **Attack Rate (Well #2 users):** 0%
    
    **Case Fatality Rate:** 20%
    """)

# Main content area based on current view
if st.session_state.current_view == 'map':
    st.markdown("## 📍 Riverside Village Map")
    
    st.markdown("""
    <div style="background-color: #E8F5E9; padding: 20px; border-radius: 10px; margin: 20px 0;">
        <h3 style="margin-top: 0;">🗺️ Village Layout</h3>
    """, unsafe_allow_html=True)
    
    # Create a text-based map (in real version, this would be interactive)
    map_col1, map_col2 = st.columns([2, 1])
    
    with map_col1:
        st.markdown("""
        ```
        ═══════════════════════════════════════════════════════
                        RIVERSIDE VILLAGE
        ═══════════════════════════════════════════════════════
        
                          🏥 Health Center
                                 |
                                 |
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        │   NEIGHBORHOOD A       │    NEIGHBORHOOD B      │
        │   (Well #1 users)      │    (Well #2 users)     │
        │                        │                        │
        │   🔴🔴🔴 (Cases)        │    (No cases)          │
        │   🔴🔴🔴               │                        │
        │   🔴🔴🔴               │                        │
        │   🔴🔴🔴🔴🔴           │                        │
        │                        │                        │
        │     💧 Well #1         │      💧 Well #2        │
        │     (Open well)        │      (Covered/pump)    │
        │        |               │                        │
        │        |               │                        │
        │     🚽 Latrine         │                        │
        │   (30m uphill)         │                        │
        │                        │                        │
        └────────────────────────┴────────────────────────┘
        
        Legend:
        🔴 = Case location
        💧 = Water source
        🚽 = Sanitation facility
        🏥 = Health facility
        ```
        """)
    
    with map_col2:
        st.markdown("### 🔍 Key Observations")
        st.warning("""
        **All 15 cases** are located in Neighborhood A
        
        **Well #1 characteristics:**
        - Open well (no cover)
        - Serves ~60 households
        - 15 meters deep
        - Located 30m downhill from latrine
        
        **Well #2 characteristics:**
        - Covered with hand pump
        - Serves ~40 households  
        - 25 meters deep
        - Zero cases among users
        """)
        
        st.success("""
        💡 **Spatial Pattern:**
        
        Clear clustering around Well #1. This is a classic waterborne outbreak pattern!
        """)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Add quick action buttons
    st.markdown("### 🎯 Next Steps")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗣️ Interview Community Members", use_container_width=True):
            st.session_state.current_view = 'contacts'
            st.rerun()
    with col2:
        if st.button("📊 Review Case Data", use_container_width=True):
            st.session_state.current_view = 'cases'
            st.rerun()

elif st.session_state.current_view == 'contacts':
    st.markdown("## 👥 People You Can Interview")
    
    # Show all characters
    for char_key, char_data in CHARACTERS.items():
        with st.container():
            st.markdown(f"""
            <div class="character-card">
                <h3>{char_data['emoji']} {char_data['name']}</h3>
                <p><strong>{char_data['role']}</strong></p>
            </div>
            """, unsafe_allow_html=True)
            
            status = "✅ Interviewed" if char_key in st.session_state.interviewed_characters else "⭕ Not yet contacted"
            st.caption(f"Status: {status}")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button(f"Interview {char_data['name'].split()[0]}", key=f"interview_{char_key}"):
                    st.session_state.current_character = char_key
                    st.session_state.current_view = 'interview'
                    st.rerun()
            
            with col2:
                if char_key in st.session_state.interviewed_characters:
                    if st.button(f"View Notes from {char_data['name'].split()[0]}", key=f"notes_{char_key}"):
                        st.info("Feature coming in full version: View previous interview notes")

elif st.session_state.current_view == 'interview':
    character_key = st.session_state.current_character
    character = CHARACTERS[character_key]
    
    # Interview header
    st.markdown(f"## {character['emoji']} Interview with {character['name']}")
    st.caption(f"**Role:** {character['role']}")
    
    if st.button("← Back to Contacts"):
        st.session_state.current_view = 'contacts'
        st.rerun()
    
    st.markdown("---")
    
    # Initialize interview history for this character
    if character_key not in st.session_state.interview_history:
        st.session_state.interview_history[character_key] = []
        st.session_state.interviewed_characters.add(character_key)
    
    # Show conversation history
    conversation = st.session_state.interview_history[character_key]
    
    # Initial greeting if first interaction
    if len(conversation) == 0:
        st.markdown(f"""
        <div class="interview-bubble">
            <strong>{character['emoji']} {character['name']}:</strong><br>
            {character['initial_greeting']}
        </div>
        """, unsafe_allow_html=True)
    
    # Show previous conversation
    for entry in conversation:
        st.markdown(f"""
        <div class="user-bubble">
            <strong>You:</strong><br>
            {entry['question']}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="interview-bubble">
            <strong>{character['emoji']} {character['name']}:</strong><br>
            {entry['response']}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Question input area
    st.markdown("### 💬 Ask a Question")
    
    # Suggested questions (only show if no questions asked yet)
    if len(conversation) == 0:
        st.markdown("**💡 Suggested starter questions:**")
        suggestions = {
            "dr_mensah": [
                "Can you tell me about the outbreak so far?",
                "What are the main symptoms patients are showing?",
                "When did the first case occur?"
            ],
            "mrs_abena": [
                "What have you observed in the community?",
                "Do you know the affected families?",
                "Have you noticed any patterns?"
            ],
            "chief_okoye": [
                "Can you tell me about the village water sources?",
                "When was the last time you had a health problem like this?",
                "What are your concerns about this outbreak?"
            ],
            "mohammed": [
                "Tell me about your water business",
                "What have you noticed about the water sources?",
                "Why do you think some people got sick and others didn't?"
            ]
        }
        
        cols = st.columns(3)
        for i, suggestion in enumerate(suggestions.get(character_key, [])):
            with cols[i]:
                if st.button(suggestion, key=f"suggest_{i}"):
                    # Auto-fill the question
                    st.session_state['auto_question'] = suggestion

    # Question input
    user_question = st.text_area(
        "Type your question:",
        value=st.session_state.get('auto_question', ''),
        height=100,
        key="question_input",
        placeholder="What would you like to ask?"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        ask_button = st.button("🗣️ Ask Question", type="primary")
    with col2:
        if st.button("📝 Save Important Info to Notes"):
            if len(conversation) > 0:
                last_exchange = conversation[-1]
                note = f"**{character['name']}** ({datetime.now().strftime('%H:%M')}): {last_exchange['response'][:200]}..."
                st.session_state.notes.append(note)
                st.success("✅ Added to investigation notes!")
    
    if ask_button and user_question.strip():
        with st.spinner(f"💭 {character['name']} is responding..."):
            # Get AI response
            response = get_ai_response(character_key, user_question, conversation)
            
            # Add to conversation history
            st.session_state.interview_history[character_key].append({
                "question": user_question,
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Clear auto question if it exists
            if 'auto_question' in st.session_state:
                del st.session_state['auto_question']
            
            st.rerun()

elif st.session_state.current_view == 'cases':
    st.markdown("## 📋 Case Line List")
    
    import pandas as pd
    
    df = pd.DataFrame(CASES)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Epidemic Curve")
        # Simple text-based epi curve
        st.markdown("""
        ```
        Cases by Date of Onset
        
        6 |              🔴🔴
        5 |           🔴🔴🔴
        4 |        🔴🔴🔴🔴
        3 |     🔴🔴🔴
        2 |  🔴🔴
        1 | 🔴
          |________________
            3  4  5  6  7  8  9
               March 2025
        ```
        
        📈 Pattern: Point-source outbreak
        Peak on March 6-7
        """)
    
    with col2:
        st.markdown("### 🔍 Key Patterns")
        st.info("""
        **Demographics:**
        - 60% children under 10
        - 20% elderly (>60)
        - 20% working-age adults
        
        **Geographic:**
        - 100% from Neighborhood A
        - All households use Well #1
        
        **Clinical:**
        - Severe watery diarrhea (100%)
        - Vomiting (93%)
        - Dehydration (100%)
        - 3 deaths (CFR: 20%)
        """)

elif st.session_state.current_view == 'notes':
    st.markdown("## ✍️ Investigation Notes")
    
    if len(st.session_state.notes) == 0:
        st.info("📝 No notes yet. During interviews, click 'Save Important Info to Notes' to capture key findings here.")
    else:
        st.success(f"You have {len(st.session_state.notes)} saved notes")
        
        for i, note in enumerate(st.session_state.notes):
            with st.expander(f"Note {i+1}", expanded=(i == len(st.session_state.notes)-1)):
                st.markdown(note)
                if st.button(f"🗑️ Delete", key=f"delete_{i}"):
                    st.session_state.notes.pop(i)
                    st.rerun()
    
    st.markdown("---")
    st.markdown("### ➕ Add Manual Note")
    new_note = st.text_area("Type your observation or finding:")
    if st.button("💾 Save Note"):
        if new_note.strip():
            timestamp = datetime.now().strftime('%H:%M')
            st.session_state.notes.append(f"**Manual Note** ({timestamp}): {new_note}")
            st.success("✅ Note saved!")
            st.rerun()

elif st.session_state.current_view == 'objectives':
    st.markdown("## 🎯 Day 1 Learning Objectives")
    
    objectives = [
        {
            "obj": "Understand the outbreak context and timeline",
            "complete": len(st.session_state.interviewed_characters) > 0
        },
        {
            "obj": "Identify the population at risk",
            "complete": 'dr_mensah' in st.session_state.interviewed_characters or 'mrs_abena' in st.session_state.interviewed_characters
        },
        {
            "obj": "Conduct hypothesis-generating interviews",
            "complete": len(st.session_state.interviewed_characters) >= 2
        },
        {
            "obj": "Recognize spatial clustering of cases",
            "complete": True  # They've seen the map
        },
        {
            "obj": "Form initial hypotheses about outbreak source",
            "complete": len(st.session_state.interviewed_characters) >= 3
        }
    ]
    
    for obj in objectives:
        status = "✅" if obj["complete"] else "⭕"
        color_class = "objective-complete" if obj["complete"] else "objective-pending"
        st.markdown(f"<p class='{color_class}'>{status} {obj['obj']}</p>", unsafe_allow_html=True)
    
    completed = sum(1 for obj in objectives if obj["complete"])
    st.progress(completed / len(objectives))
    st.caption(f"{completed} of {len(objectives)} objectives completed")
    
    if completed == len(objectives):
        st.success("🎉 Congratulations! You've completed all Day 1 objectives. In the full simulation, you'd move on to Day 2: Questionnaire Design.")
    
    st.markdown("---")
    st.markdown("### 📚 What Comes Next (Full Simulation)")
    
    st.info("""
    **Day 2:** Design questionnaire and study
    - Define case and control criteria
    - Design data collection form
    - Determine sample size
    - Plan sampling strategy
    
    **Day 3:** Collect and analyze data
    - System generates your custom dataset
    - Perform statistical analysis
    - Create tables and figures
    
    **Day 4:** Environmental investigation
    - Collect water/environmental samples
    - Request lab tests
    - Triangulate all evidence
    
    **Day 5:** Interventions and outcomes
    - Propose control measures
    - Present to MOH Director
    - See epidemic curve response
    """)

# Footer
st.markdown("---")
st.caption("FETP Intermediate 2.0 - Outbreak Investigation Simulation | Demo Version")