import streamlit as st
import pandas as pd
import base64
import time
import logging
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from i18n.translate import t
from config.locations import (
    get_current_scenario_id, get_locations, get_area_locations,
    get_area_metadata, get_npc_locations, SCENARIO_INITIAL_NPCS
)
from config.scenarios import load_scenario_config
from state.resources import spend_time, spend_budget, format_resource_cost, TIME_COSTS
from npc.engine import get_npc_response, stream_npc_response, get_npc_avatar, lab_test_label
from npc.emotions import get_npc_trust, update_npc_emotion, analyze_user_tone, describe_emotional_state
from npc.unlock import check_npc_unlock_triggers, has_hospital_records_access
from npc.context import investigation_stage
from data_utils.clinic import generate_hospital_records, render_hospital_record
from data_utils.case_definition import get_symptomatic_column
from ui.components import format_area_description, check_and_show_hints
import outbreak_logic as jl


def get_day1_location_unlocks(scenario_id: str) -> list[str]:
    if scenario_id == "lepto_rivergate":
        return ["District Hospital", "Ward Northbend", "RHU"]
    return ["District Hospital", "Nalu Village", "Kabwe Village"]


def unlock_day1_locations():
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    unlocked = get_day1_location_unlocks(scenario_id)
    st.session_state.locations_unlocked = unlocked


def handle_travel(target_location: str) -> bool:
    from state.resources import check_resources, BUDGET_COSTS

    previous_location = st.session_state.get("current_area")
    if previous_location == target_location:
        return True

    travel_time = TIME_COSTS.get("travel_to_village", 0.5)
    travel_cost = BUDGET_COSTS.get("transport_per_trip", 20)

    can_proceed, msg = check_resources(travel_time, travel_cost)
    if not can_proceed:
        st.error(msg)
        return False

    spend_time(travel_time, f"Travel to {target_location}")
    spend_budget(travel_cost, f"Travel to {target_location}")

    jl.log_event(
        event_type="travel",
        location_id=target_location,
        cost_time=travel_time,
        cost_budget=travel_cost,
        payload={"from": previous_location, "to": target_location},
    )

    visited = st.session_state.setdefault("visited_locations", set())
    visited.add(target_location)
    return True

# Location coordinates for interactive map (0-100 scale, 0,0 is bottom-left)
AES_MAP_LOCATIONS = {
    "Nalu Village": {"x": 35, "y": 45, "icon": "🌾", "desc": "Large rice-farming village. Pig cooperative nearby."},
    "Kabwe Village": {"x": 65, "y": 40, "icon": "🌿", "desc": "Medium village on higher ground. Mixed farming."},
    "Tamu Village": {"x": 15, "y": 85, "icon": "⛰️", "desc": "Remote upland community. Cassava farming."},
    "Mining Area": {"x": 20, "y": 15, "icon": "⛏️", "desc": "Recent expansion. New irrigation ponds."},
    "District Hospital": {"x": 85, "y": 80, "icon": "🏥", "desc": "AES patients admitted here. Lab available."},
    "District Office": {"x": 40, "y": 35, "icon": "🏛️", "desc": "Meet officials, veterinary and environmental officers."},
}

LEPTO_MAP_LOCATIONS = {
    # Y-coordinates scaled to 0-70 range for moderately wide map format
    "Ward Northbend": {"x": 30, "y": 49, "icon": "🏘️", "desc": "Flood-prone ward reporting rising cases."},
    "East Terrace": {"x": 70, "y": 32, "icon": "🏘️", "desc": "Riverside ward with livestock exposure."},
    "Southshore": {"x": 35, "y": 14, "icon": "🏘️", "desc": "Low-lying ward with drainage canals."},
    "Highridge": {"x": 15, "y": 39, "icon": "🏘️", "desc": "Upland ward near irrigation channels."},
    "District Hospital": {"x": 80, "y": 53, "icon": "🏥", "desc": "Severe cases are being referred here."},
    "RHU": {"x": 55, "y": 42, "icon": "🏥", "desc": "Rural Health Unit coordinating surveillance."},
    "DRRM Office": {"x": 55, "y": 25, "icon": "🏛️", "desc": "Disaster response coordination office."},
    "Mining Area": {"x": 85, "y": 11, "icon": "⛏️", "desc": "Runoff and pooled water risks."},
}


def render_interactive_map():
    """
    Render an interactive point-and-click map of Sidero Valley using Plotly.
    Clicking a location updates st.session_state.current_area and reruns.
    """
    import plotly.graph_objects as go

    # Load the background map image
    scenario_id = get_current_scenario_id()
    if scenario_id == "lepto_rivergate":
        map_image_path = Path(__file__).resolve().parent.parent / "scenarios" / scenario_id / "assets" / "map_background.png"
        map_locations = LEPTO_MAP_LOCATIONS
    else:
        map_image_path = Path(__file__).resolve().parent.parent / "assets" / "map_background.png"
        map_locations = AES_MAP_LOCATIONS

    fallback_path = Path(__file__).resolve().parent.parent / "assets" / "map_background.png"
    if not map_image_path.exists():
        if fallback_path.exists():
            map_image_path = fallback_path
        else:
            st.error(f"Map background image not found at {map_image_path}")
            return

    try:
        with Image.open(map_image_path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError):
        if map_image_path != fallback_path and fallback_path.exists():
            try:
                with Image.open(fallback_path) as img:
                    img.verify()
                map_image_path = fallback_path
            except (UnidentifiedImageError, OSError):
                st.error("Map background image could not be loaded.")
                return
        else:
            st.error("Map background image could not be loaded.")
            return
    with map_image_path.open("rb") as map_file:
        map_image_base64 = base64.b64encode(map_file.read()).decode("utf-8")
    map_image_uri = f"data:image/png;base64,{map_image_base64}"

    # Create figure with the background image
    fig = go.Figure()

    # Add the background image (sized to match moderately wide aspect ratio)
    fig.add_layout_image(
        dict(
            source=map_image_uri,
            xref="x",
            yref="y",
            x=0,
            y=70,  # Match the y-axis range
            sizex=100,
            sizey=70,  # Match the y-axis range for correct aspect ratio
            sizing="stretch",
            opacity=1,
            layer="below"
        )
    )

    # Prepare data for scatter points, separating unlocked and locked locations
    unlocked_x = []
    unlocked_y = []
    unlocked_names = []
    unlocked_descriptions = []

    locked_x = []
    locked_y = []
    locked_names = []
    locked_descriptions = []

    for loc_name, loc_data in map_locations.items():
        # Check if location is unlocked
        is_unlocked = True
        if jl.is_location_unlocked and hasattr(st.session_state, 'game_state'):
            is_unlocked = jl.is_location_unlocked(loc_name, st.session_state)

        if is_unlocked:
            unlocked_x.append(loc_data["x"])
            unlocked_y.append(loc_data["y"])
            unlocked_names.append(loc_name)
            unlocked_descriptions.append(f"{loc_data['icon']} {loc_name}<br>{loc_data['desc']}")
        else:
            locked_x.append(loc_data["x"])
            locked_y.append(loc_data["y"])
            locked_names.append(loc_name)
            locked_descriptions.append(f"🔒 {loc_name}<br>Location locked")

    # Add clickable scatter points for UNLOCKED locations with a subtle glow effect
    if unlocked_x:
        # First add a larger, semi-transparent marker for the glow/halo effect
        fig.add_trace(go.Scatter(
            x=unlocked_x,
            y=unlocked_y,
            mode='markers',
            marker=dict(
                size=28,
                color='rgba(255, 255, 255, 0.4)',
                line=dict(width=0)
            ),
            hoverinfo='skip',
            showlegend=False
        ))

        # Add the main marker points for unlocked locations
        fig.add_trace(go.Scatter(
            x=unlocked_x,
            y=unlocked_y,
            mode='markers',
            marker=dict(
                size=18,
                color='#FF6B35',  # Orange-red color for visibility
                line=dict(width=3, color='white'),
                symbol='circle'
            ),
            text=unlocked_descriptions,
            hovertemplate='%{text}<extra></extra>',
            customdata=unlocked_names,
            showlegend=False
        ))

    # Add LOCKED locations (greyed out, not clickable)
    if locked_x:
        fig.add_trace(go.Scatter(
            x=locked_x,
            y=locked_y,
            mode='markers',
            marker=dict(
                size=18,
                color='rgba(128, 128, 128, 0.5)',  # Grey for locked locations
                line=dict(width=3, color='rgba(200, 200, 200, 0.5)'),
                symbol='circle'
            ),
            text=locked_descriptions,
            hovertemplate='%{text}<extra></extra>',
            hoverinfo='text',
            showlegend=False
        ))

    # Add text labels with shadow effect for readability
    # First add shadow/outline (slightly offset dark text)
    label_offset = 4  # Adjusted for moderately wide map format
    for loc_name, loc_data in map_locations.items():
        # Shadow offset positions
        for dx, dy in [(1, -1), (-1, -1), (1, 1), (-1, 1)]:
            fig.add_annotation(
                x=loc_data["x"] + dx * 0.5,
                y=loc_data["y"] + label_offset + dy * 0.3,
                text=f"<b>{loc_name}</b>",
                showarrow=False,
                font=dict(size=11, color='rgba(0,0,0,0.8)'),
                xanchor='center',
                yanchor='bottom'
            )

    # Add the main white text labels on top
    for loc_name, loc_data in map_locations.items():
        fig.add_annotation(
            x=loc_data["x"],
            y=loc_data["y"] + label_offset,
            text=f"<b>{loc_name}</b>",
            showarrow=False,
            font=dict(size=11, color='white'),
            xanchor='center',
            yanchor='bottom'
        )

    # Configure the layout to look like a clean map
    # Use moderately wide aspect ratio (1.4:1)
    fig.update_layout(
        xaxis=dict(
            range=[0, 100],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showline=False,
            fixedrange=True
        ),
        yaxis=dict(
            range=[0, 70],  # Adjusted for ~1.4:1 aspect ratio
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showline=False,
            fixedrange=True
            # Removed scaleanchor to allow wide format
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=500,  # Restored height
        dragmode=False,
        clickmode='event+select'
    )

    # Display the map with click handling
    st.markdown("### Click a location to travel there")
    from state.resources import BUDGET_COSTS
    st.caption(
        f"Travel costs {TIME_COSTS.get('travel_to_village', 0.5)}h and "
        f"${BUDGET_COSTS.get('transport_per_trip', 20)} per trip."
    )

    # Use plotly_events for click detection
    selected_point = st.plotly_chart(
        fig,
        use_container_width=True,
        key="interactive_map",
        on_select="rerun",
        selection_mode="points"
    )

    # Handle click/selection events (only for unlocked locations)
    if selected_point and selected_point.selection and selected_point.selection.points:
        point_data = selected_point.selection.points[0]
        point_index = point_data.get("point_index", None)
        if point_index is not None and 0 <= point_index < len(unlocked_names):
            selected_location = unlocked_names[point_index]
            # Check if location is unlocked before allowing navigation
            is_unlocked = True
            if jl.is_location_unlocked and hasattr(st.session_state, 'game_state'):
                is_unlocked = jl.is_location_unlocked(selected_location, st.session_state)

            if is_unlocked:
                if handle_travel(selected_location):
                    st.session_state.current_area = selected_location
                    st.session_state.current_view = "area"
                    st.rerun()
            else:
                st.warning("🔒 This location is locked. Complete previous objectives to unlock.")

    # Show location legend/quick reference below the map
    st.markdown("---")
    st.markdown("**Locations:**")
    cols = st.columns(3)
    for i, (loc_name, loc_data) in enumerate(map_locations.items()):
        with cols[i % 3]:
            # Check if location is unlocked
            is_unlocked = True
            if jl.is_location_unlocked and hasattr(st.session_state, 'game_state'):
                is_unlocked = jl.is_location_unlocked(loc_name, st.session_state)

            button_label = f"{loc_data['icon']} {loc_name}" if is_unlocked else f"🔒 {loc_name}"
            button_disabled = not is_unlocked

            if st.button(button_label, key=f"map_btn_{loc_name}", use_container_width=True, disabled=button_disabled):
                if is_unlocked:
                    if handle_travel(loc_name):
                        st.session_state.current_area = loc_name
                        st.session_state.current_view = "area"
                        st.rerun()
            st.caption(loc_data['desc'])


# =========================
# CONTEXTUAL HINTS SYSTEM
# =========================

HINT_RULES = [
    {
        "id": "hint_first_interview",
        "condition": lambda ss: (
            ss.get("current_day", 1) == 1
            and len(ss.get("interview_history", {})) == 0
            and len(ss.get("visited_locations", set())) >= 1
        ),
        "hint": "You've traveled to a location but haven't interviewed anyone yet. Try talking to the hospital staff -- they often have the earliest observations about case patterns.",
    },
    {
        "id": "hint_one_health",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and not ss.get("vet_unlocked", False)
            and not ss.get("env_officer_unlocked", False)
            and len(ss.get("interview_history", {})) >= 2
        ),
        "hint": "Some outbreaks have animal or environmental connections. Try asking NPCs about livestock, rats, or flooding. A One Health approach could reveal hidden transmission pathways.",
    },
    {
        "id": "hint_case_definition",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and not ss.get("case_definition_written", False)
        ),
        "hint": "You should establish a working case definition before advancing further. Visit the Overview tab to build one using the WHO template.",
    },
    {
        "id": "hint_lab_orders",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and len(ss.get("lab_orders", [])) == 0
        ),
        "hint": "Laboratory confirmation strengthens your investigation. Consider ordering diagnostic tests at the hospital -- early orders mean results arrive sooner.",
    },
    {
        "id": "hint_environment",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 3
            and len(ss.get("environment_findings", [])) == 0
        ),
        "hint": "Environmental sampling can reveal contamination sources. Visit locations to look for water, soil, or animal reservoir testing opportunities.",
    },
    {
        "id": "hint_more_locations",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and len(ss.get("visited_locations", set())) <= 2
        ),
        "hint": "There are more locations to explore on the map. Each location has unique NPCs and data sources. Consider visiting wards with high case counts.",
    },
    {
        "id": "hint_evidence_board",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 2
            and len(ss.get("evidence_board", [])) <= 3
        ),
        "hint": "Don't forget to update your Evidence Board with clues you discover. Tracking evidence helps you connect the dots between interviews, lab results, and field observations.",
    },
    {
        "id": "hint_study_design",
        "condition": lambda ss: (
            ss.get("current_day", 1) >= 3
            and not ss.get("questionnaire_submitted", False)
        ),
        "hint": "Designing a study and questionnaire will let you systematically collect data from the affected population. Visit the Study Design tool to get started.",
    },
]


def view_travel_map():
    """Main travel map showing all areas and allowing navigation."""
    from config.scenarios import load_scenario_content
    from npc.unlock import get_hospital_records_contact_name

    scenario_name = st.session_state.get("current_scenario_name", "Investigation")
    st.title(f"{scenario_name} - Investigation Map")

    # Serious Mode: Show outbreak summary metrics prominently on Day 1
    if st.session_state.current_day == 1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #d32f2f 0%, #c62828 100%);
                    padding: 1.5rem;
                    border-radius: 10px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                    margin-bottom: 1.5rem;'>
            <h3 style='color: white; margin: 0 0 1rem 0; text-align: center;'>🚨 Outbreak Summary</h3>
            <div style='display: flex; justify-content: space-around; text-align: center;'>
                <div>
                    <div style='font-size: 2.5rem; color: #ffeb3b; font-weight: bold;'>2</div>
                    <div style='color: white; font-size: 1.1rem;'>Severe Cases</div>
                </div>
                <div>
                    <div style='font-size: 2.5rem; color: #ffeb3b; font-weight: bold;'>1</div>
                    <div style='color: white; font-size: 1.1rem;'>Death</div>
                </div>
                <div>
                    <div style='font-size: 2.5rem; color: #ffeb3b; font-weight: bold;'>Day 1</div>
                    <div style='color: white; font-size: 1.1rem;'>Investigation Start</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Show current status
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(f"{t('day')}", f"{st.session_state.current_day} / 5")
    with col2:
        time_display = f":red[{st.session_state.time_remaining}h]" if st.session_state.time_remaining < 0 else f"{st.session_state.time_remaining}h"
        st.markdown(f"**{t('time_remaining')}**  \n{time_display}")
    with col3:
        st.metric(f"{t('budget')}", f"${st.session_state.budget}")
    with col4:
        st.metric(f"{t('lab_credits')}", st.session_state.lab_credits)

    st.markdown("---")

    # Day briefing
    if st.session_state.current_day == 1:
        with st.expander("Day 1 Briefing - Situation Assessment", expanded=True):
            contact_name = get_hospital_records_contact_name()
            st.markdown(f"""
            **Your tasks today:**
            - Visit the **District Hospital** to meet {contact_name} and review cases
            - Travel to **Nalu Village** to interview residents and review clinic records
            - Document your initial hypotheses about the outbreak source

            *Click on a location below to travel there.*
            """)

    # About the selected scenario
    scenario_id = st.session_state.get("current_scenario", "aes_sidero_valley")
    scenario_about_meta = {
        "aes_sidero_valley": {
            "title": "Sidero District",
            "fallback": (
                "Sidero District is a rural agricultural region known for extensive rice farming. "
                "Recent irrigation projects have expanded the paddy fields closer to residential areas. "
                "The population is approximately 15,000, spread across 3 main villages (Nalu, Tamu, Kabwe). "
                "Livestock farming (pigs, ducks) is common in backyard settings."
            ),
        },
        "lepto_rivergate": {
            "title": "Rivergate Municipality",
            "fallback": (
                "Rivergate Municipality sits in the Kantara River basin of northern Aruvia, "
                "spanning the town center and four surrounding wards (Northbend, East Terrace, "
                "Southshore, Highridge). Recent typhoon flooding left standing water and widespread "
                "cleanup exposure across urban and peri-urban areas. The local economy blends rice and "
                "corn farming, fishing, small businesses, and a major mining operation, with many households "
                "keeping pigs and water buffalo."
            ),
        },
    }
    about_meta = scenario_about_meta.get(scenario_id, {
        "title": "Outbreak Setting",
        "fallback": "Scenario overview is not available yet.",
    })
    about_content = load_scenario_content(scenario_id, "about")
    if about_content.startswith("⚠️ Content file not found"):
        about_content = about_meta["fallback"]
    with st.expander(f"ℹ️ About {about_meta['title']}"):
        st.markdown(about_content)

    # Render the interactive satellite map for destination selection
    render_interactive_map()

    # Contextual hints from HQ
    check_and_show_hints()

    # Quick access to data views
    st.markdown("### Investigation Tools")
    cols = st.columns(4)
    with cols[0]:
        if st.button("Epi Curve & Line List", use_container_width=True):
            st.session_state.current_view = "descriptive"
            st.rerun()
    with cols[1]:
        if st.button("Spot Map", use_container_width=True):
            st.session_state.current_view = "spotmap"
            st.rerun()
    with cols[2]:
        if st.button("Study Design", use_container_width=True):
            st.session_state.current_view = "study"
            st.rerun()
    with cols[3]:
        if st.button("Final Report", use_container_width=True):
            st.session_state.current_view = "outcome"
            st.rerun()


def get_location_status(loc_key: str) -> dict:
    """Get the status of a location (visited, actions completed, etc.)."""
    status = {
        "visited": False,
        "clinic_reviewed": False,
        "environment_inspected": False,
        "samples_collected": False,
        "npcs_interviewed": [],
    }

    # Check if location was visited (if they went to this location view)
    visited_locations = st.session_state.get("visited_locations", set())
    status["visited"] = loc_key in visited_locations

    # Check specific action completions
    if loc_key in ["nalu_health_center"]:
        status["clinic_reviewed"] = st.session_state.get("clinic_records_reviewed", False)

    # Check environment inspections
    env_findings = st.session_state.get("environment_findings", [])
    for finding in env_findings:
        if finding.get("location") == loc_key:
            status["environment_inspected"] = True
            break

    # Check samples collected at this location
    lab_samples = st.session_state.get("lab_samples_submitted", [])
    for sample in lab_samples:
        if sample.get("location") == loc_key:
            status["samples_collected"] = True
            break

    # Check NPCs interviewed at this location
    loc = get_locations().get(loc_key, {})
    for npc_key in loc.get("npcs", []):
        if npc_key in st.session_state.get("interview_history", {}):
            status["npcs_interviewed"].append(npc_key)

    return status


def render_breadcrumb(area: str = None, location: str = None):
    """Render a breadcrumb navigation bar."""
    area_meta = get_area_metadata().get(area, {}) if area else {}
    area_icon = area_meta.get("icon", "📍")

    loc_data = get_locations().get(location, {}) if location else {}
    loc_icon = loc_data.get("icon", "📍")
    loc_name = loc_data.get("name", location) if location else None

    # Build breadcrumb elements
    crumbs = []

    # Map is always first
    crumbs.append(("🗺️ Map", "map", None))

    if area:
        crumbs.append((f"{area_icon} {area}", "area", area))

    if location and loc_name:
        crumbs.append((f"{loc_icon} {loc_name}", "location", location))

    # Render breadcrumb with clickable buttons
    cols = st.columns(len(crumbs) * 2 - 1)
    col_idx = 0

    for i, (label, view_type, data) in enumerate(crumbs):
        with cols[col_idx]:
            # Don't make the last crumb clickable (it's current location)
            if i < len(crumbs) - 1:
                if st.button(label, key=f"breadcrumb_{view_type}_{i}", use_container_width=True):
                    if view_type == "map":
                        st.session_state.current_area = None
                        st.session_state.current_location = None
                        st.session_state.current_view = "map"
                    elif view_type == "area":
                        st.session_state.current_area = data
                        st.session_state.current_location = None
                        st.session_state.current_view = "area"
                    st.rerun()
            else:
                st.markdown(f"**{label}**")
        col_idx += 1

        # Add separator
        if i < len(crumbs) - 1:
            with cols[col_idx]:
                st.markdown("<div style='text-align: center; padding-top: 8px;'>›</div>", unsafe_allow_html=True)
            col_idx += 1


def travel_with_animation(destination_name: str, travel_time: float = 0.5):
    """Show a travel animation/spinner when moving to a new location."""
    with st.spinner(f"🚶 Traveling to {destination_name}..."):
        time.sleep(min(travel_time, 1.0))  # Cap animation at 1 second


def render_location_card(loc_key: str, loc: dict, npcs_here: list, npc_truth: dict, col_key: str = ""):
    """Render a styled card for a sub-location with status badges and NPC avatars."""

    loc_name = loc.get("name", loc_key)
    loc_icon = loc.get("icon", "📍")
    loc_desc = loc.get("description", "")
    travel_time = loc.get("travel_time", 0.5)

    # Get location status
    status = get_location_status(loc_key)

    # Build status badge HTML
    status_badges = []
    if status["clinic_reviewed"] and loc_key == "nalu_health_center":
        status_badges.append('<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 5px;">✅ Records Reviewed</span>')
    if status["environment_inspected"]:
        status_badges.append('<span style="background: #3b82f6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 5px;">🔍 Inspected</span>')
    if status["samples_collected"]:
        status_badges.append('<span style="background: #8b5cf6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 5px;">🧪 Sampled</span>')
    if status["npcs_interviewed"]:
        status_badges.append('<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 5px;">💬 Interviewed</span>')

    badge_html = " ".join(status_badges) if status_badges else ""

    # Card container with border styling
    st.markdown(f"""
    <div style="border: 1px solid #e5e7eb; border-radius: 12px; padding: 15px; margin-bottom: 10px; background: white;">
        <h4 style="margin: 0 0 5px 0;">{loc_icon} {loc_name}</h4>
        <div style="margin-bottom: 8px;">{badge_html}</div>
    </div>
    """, unsafe_allow_html=True)

    # Thumbnail image
    image_path = loc.get("image_thumb") or loc.get("image_path")
    if image_path:
        path = Path(image_path)
        if not path.suffix:
            for ext in ['.png', '.jpg', '.jpeg']:
                test_path = Path(str(path) + ext)
                if test_path.exists():
                    st.image(str(test_path), use_container_width=True)
                    break
        elif path.exists():
            st.image(str(path), use_container_width=True)
    else:
        # Placeholder
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    border-radius: 8px; padding: 30px; text-align: center; margin-bottom: 10px;">
            <span style="font-size: 2.5em;">{loc_icon}</span>
        </div>
        """, unsafe_allow_html=True)

    # Short description removed (caption)

    # === NPCs Present with Avatar Overlay ===
    if npcs_here:
        # Create avatar row with overlapping style
        avatar_html = '<div style="display: flex; margin: 8px 0;">'
        for idx, (npc_key, npc) in enumerate(npcs_here):
            avatar_path = npc.get("image_path")
            npc_name = npc.get("name", "Unknown")

            # Check if avatar image exists
            if avatar_path and Path(avatar_path).exists():
                # We'll render this with st.image below
                pass
            else:
                avatar_emoji = npc.get("avatar", "👤")
                avatar_html += f'''
                <div style="width: 36px; height: 36px; border-radius: 50%; background: #e5e7eb;
                            display: flex; align-items: center; justify-content: center;
                            margin-left: {-10 if idx > 0 else 0}px; border: 2px solid white;
                            font-size: 1.2em;" title="{npc_name}">
                    {avatar_emoji}
                </div>
                '''
        avatar_html += '</div>'

        st.markdown(avatar_html, unsafe_allow_html=True)

        # Show NPC names removed (caption)

    # Travel time removed (caption)

    # Go to button
    if st.button(f"Go to {loc_name}", key=f"go_{col_key}_{loc_key}", use_container_width=True):
        # Check if enough time
        if st.session_state.time_remaining >= travel_time:
            # Show travel animation
            travel_with_animation(loc_name, travel_time)

            spend_time(travel_time, f"Travel to {loc_name}")

            # Mark location as visited
            if "visited_locations" not in st.session_state:
                st.session_state.visited_locations = set()
            st.session_state.visited_locations.add(loc_key)

            # Clear chat history when changing locations
            if st.session_state.get("current_npc"):
                npc_to_clear = st.session_state.current_npc
                if npc_to_clear in st.session_state.interview_history:
                    st.session_state.interview_history[npc_to_clear] = []
                st.session_state.current_npc = None

            st.session_state.current_location = loc_key
            st.session_state.current_view = "location"
            st.rerun()
        else:
            st.error(f"Not enough time! Need {travel_time}h")

    st.markdown("---")


def render_area_hero_image(area: str) -> bool:
    """Render the hero/exterior image for an area if available."""
    area_meta = get_area_metadata().get(area, {})
    image_path = area_meta.get("image_exterior")

    if not image_path:
        return False

    path = Path(image_path)

    # Try with common extensions if no extension
    if not path.suffix:
        for ext in ['.png', '.jpg', '.jpeg']:
            test_path = Path(str(path) + ext)
            if test_path.exists():
                st.image(str(test_path), use_container_width=True)
                return True
    elif path.exists():
        st.image(str(path), use_container_width=True)
        return True

    return False


def render_location_thumbnail(loc_key: str, width: int = 200) -> bool:
    """Render a thumbnail image for a sub-location if available."""
    loc = get_locations().get(loc_key, {})

    # Try thumbnail first, then fall back to main image
    image_path = loc.get("image_thumb") or loc.get("image_path")

    if not image_path:
        return False

    path = Path(image_path)

    # Try with common extensions if no extension
    if not path.suffix:
        for ext in ['.png', '.jpg', '.jpeg']:
            test_path = Path(str(path) + ext)
            if test_path.exists():
                st.image(str(test_path), use_container_width=True)
                return True
    elif path.exists():
        st.image(str(path), use_container_width=True)
        return True

    return False


def view_area_visual(area: str):
    """Render an area with immersive visual grid layout.

    Features:
    - Breadcrumb navigation at top
    - Hero exterior image
    - 3-column grid of sub-location cards with status badges
    - Each card shows: thumbnail, name, status badges, NPCs present, Go button
    """

    area_meta = get_area_metadata().get(area, {})
    area_icon = area_meta.get("icon", "📍")

    # === BREADCRUMB NAVIGATION ===
    render_breadcrumb(area=area)

    st.markdown("---")

    st.title(f"{area_icon} {area}")

    # === HERO IMAGE ===
    if not render_area_hero_image(area):
        # Show placeholder if no image available
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 12px; padding: 60px; text-align: center; color: white;
                    margin-bottom: 20px;">
            <h1 style="font-size: 3em; margin: 0;">{area_icon}</h1>
            <h2 style="margin: 10px 0 0 0;">{area}</h2>
        </div>
        """, unsafe_allow_html=True)

    # Area description
    description = format_area_description(area_meta.get("description", ""))
    if description:
        st.markdown(f"*{description}*")

    st.markdown("---")
    st.markdown("### 🚪 Locations to Explore")

    # Get locations in this area
    location_keys = get_area_locations().get(area, [])

    if not location_keys:
        st.warning("No locations available in this area.")
        return

    # Get NPC truth data
    npc_truth = st.session_state.truth.get("npc_truth", {})

    # === SUB-LOCATION GRID (3 columns) ===
    num_cols = min(3, len(location_keys))  # Use up to 3 columns
    cols = st.columns(num_cols)

    for i, loc_key in enumerate(location_keys):
        loc = get_locations().get(loc_key, {})

        # Find NPCs at this location
        npcs_here = []
        for npc_key in loc.get("npcs", []):
            if npc_key in st.session_state.npcs_unlocked and npc_key in npc_truth:
                npcs_here.append((npc_key, npc_truth[npc_key]))

        with cols[i % num_cols]:
            # Use the consolidated card rendering function
            render_location_card(loc_key, loc, npcs_here, npc_truth, col_key=f"area_{area}")


def view_area_map(area: str):
    """[DEPRECATED] Show sub-locations within an area.

    Note: This function has been deprecated in favor of view_area_visual()
    which provides a more immersive experience with hero images, status badges,
    and improved NPC avatar display. Kept for backwards compatibility.
    """
    from npc.unlock import get_hospital_records_contact_name

    st.title(f"{area}")

    # Return to main map button
    if st.button("Return to Main Map", key="return_to_main"):
        st.session_state.current_area = None
        st.session_state.current_view = "map"
        st.rerun()

    st.markdown("---")

    # Get locations in this area
    location_keys = get_area_locations().get(area, [])

    if not location_keys:
        st.warning("No locations available in this area.")
        return

    # Show description for the area
    if area == "Nalu Village":
        st.markdown("""
        **Nalu Village** is the largest settlement in Sidero Valley. The economy centers on
        rice cultivation and pig farming. Most AES cases come from here.
        """)
    elif area == "Kabwe Village":
        st.markdown("""
        **Kabwe Village** is located 3km northeast of Nalu on higher ground. Children walk
        through rice paddies to attend school in Nalu.
        """)
    elif area == "Tamu Village":
        st.markdown("""
        **Tamu Village** is a smaller, more remote community in the foothills. Upland farming
        with less standing water.
        """)
    elif area == "Ward Northbend":
        st.markdown("""
        **Ward Northbend** is the most severely flood-affected area. Located at a river bend
        where floodwaters accumulated deepest. Most leptospirosis cases originate here.
        """)
    elif area == "Ward East Terrace":
        st.markdown("""
        **Ward East Terrace** is a mixed residential and commercial area with moderate flooding.
        Some residents participated in Northbend cleanup activities.
        """)
    elif area == "Ward Southshore":
        st.markdown("""
        **Ward Southshore** is a fishing community along the southern riverbank with moderate
        flood exposure during the typhoon.
        """)
    elif area == "Ward Highridge":
        st.markdown("""
        **Ward Highridge** is an upland area that served as an evacuation site. Minimal flooding
        makes it a useful control area for comparison.
        """)
    elif area == "District Hospital":
        contact_name = get_hospital_records_contact_name()
        scenario_type = st.session_state.get("current_scenario_type", "je")
        disease_label = "leptospirosis" if scenario_type == "lepto" else "AES"
        st.markdown(f"""
        **District Hospital** is where the {disease_label} cases have been admitted. {contact_name} oversees
        patient care and the laboratory can process some samples.
        """)
    elif area == "District Office":
        st.markdown("""
        **District Office** houses the public health, veterinary, and environmental health
        teams. Key officials work from here.
        """)

    st.markdown("### Locations to Visit")

    # Display locations in grid
    cols = st.columns(2)

    for i, loc_key in enumerate(location_keys):
        loc = get_locations().get(loc_key, {})

        # Check if location has unlocked NPCs
        npcs_here = []
        npc_truth = st.session_state.truth.get("npc_truth", {})
        for npc_key in loc.get("npcs", []):
            if npc_key in st.session_state.npcs_unlocked and npc_key in npc_truth:
                npcs_here.append(npc_truth[npc_key])

        with cols[i % 2]:
            with st.container():
                st.markdown(f"**{loc.get('name', loc_key)}**")

                # Show NPCs available removed (caption)

                # Show available actions
                actions = loc.get("available_actions", [])
                if actions:
                    # Actions removed (caption)
                    pass

                travel_time = loc.get("travel_time", 0.5)

                if st.button(f"Go to {loc.get('name', loc_key)}", key=f"loc_{loc_key}", use_container_width=True):
                    # Check if enough time
                    if st.session_state.time_remaining >= travel_time:
                        spend_time(travel_time, f"Travel to {loc.get('name', loc_key)}")

                        # Clear chat history when changing locations
                        if st.session_state.get("current_npc"):
                            npc_to_clear = st.session_state.current_npc
                            if npc_to_clear in st.session_state.interview_history:
                                st.session_state.interview_history[npc_to_clear] = []
                            st.session_state.current_npc = None

                        st.session_state.current_location = loc_key
                        st.session_state.current_view = "location"
                        st.rerun()
                    else:
                        st.error(f"Not enough time to travel (need {travel_time}h)")

                st.markdown("---")


def render_location_image(loc_key: str):
    """Render the image for a location if available."""
    loc = get_locations().get(loc_key, {})
    image_path = loc.get("image_path")

    if not image_path:
        return False

    # Handle paths with or without extension
    path = Path(image_path)

    # Try with common extensions if no extension
    if not path.suffix:
        for ext in ['.png', '.jpg', '.jpeg']:
            test_path = Path(str(path) + ext)
            if test_path.exists():
                st.image(str(test_path), use_container_width=True)
                return True
    elif path.exists():
        st.image(str(path), use_container_width=True)
        return True

    return False


def view_location(loc_key: str):
    """Render a specific location with NPCs and actions."""
    from views.interviews import render_location_actions, render_interview_modal

    loc = get_locations().get(loc_key, {})

    if not loc:
        st.error("Location not found!")
        st.session_state.current_location = None
        st.session_state.current_view = "map"
        return

    area = loc.get('area', 'Unknown Area')
    loc_icon = loc.get('icon', '📍')

    # === BREADCRUMB NAVIGATION ===
    render_breadcrumb(area=area, location=loc_key)

    st.markdown("---")

    # Header with location name
    st.title(f"{loc_icon} {loc.get('name', loc_key)}")

    # Layout: Image on left, description and NPCs on right
    col1, col2 = st.columns([1, 2])

    with col1:
        # Try to render location image
        if not render_location_image(loc_key):
            # Show placeholder SVG
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 10px; padding: 40px; text-align: center; color: white;">
                <h2>📍</h2>
                <p>Location Image</p>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        # NPCs at this location
        npc_truth = st.session_state.truth.get("npc_truth", {})
        npcs_here = []

        for npc_key in loc.get("npcs", []):
            if npc_key in st.session_state.npcs_unlocked and npc_key in npc_truth:
                npcs_here.append((npc_key, npc_truth[npc_key]))

        if npcs_here:
            st.markdown("### 👥 People Here")
            for npc_key, npc in npcs_here:
                interviewed = npc_key in st.session_state.interview_history

                with st.container():
                    cols = st.columns([1, 3, 1])
                    with cols[0]:
                        # Show avatar image if available, otherwise emoji
                        avatar_path = npc.get("image_path")
                        if avatar_path and Path(avatar_path).exists():
                            st.image(avatar_path, width=60)
                        else:
                            st.markdown(f"## {npc.get('avatar', '🧑')}")
                    with cols[1]:
                        status = "✓ Interviewed" if interviewed else ""
                        st.markdown(f"**{npc['name']}** {status}")
                    with cols[2]:
                        btn_label = "Continue Chat" if interviewed else "Talk"
                        if st.button(btn_label, key=f"talk_{npc_key}"):
                            st.session_state.current_npc = npc_key
                            st.session_state.interview_history.setdefault(npc_key, [])
                            st.session_state.action_modal = "interview"
                            st.rerun()
        else:
            st.info("No one is here to talk to right now.")

        st.markdown("---")

        # Available actions
        st.markdown("### Available Actions")
        actions = loc.get("available_actions", [])

        if actions:
            render_location_actions(loc_key, actions)

    # Handle action modals (including interview modal)
    action_modal = st.session_state.get("action_modal")
    if action_modal:
        st.markdown("---")
        if action_modal == "ward_registry":
            render_ward_registry_modal()
        elif action_modal == "hospital_charts":
            render_hospital_charts_modal()
        elif action_modal == "deep_dive_charts":
            render_deep_dive_charts_modal()
        elif action_modal == "interview":
            render_interview_modal()


def render_ward_registry_modal():
    """Render Ward Registry modal with case finding functionality."""
    from npc.unlock import get_hospital_records_contact_name

    st.subheader("📋 District Hospital - Ward Registry (Last 30 Days)")

    # Check permission
    if not has_hospital_records_access():
        contact_name = get_hospital_records_contact_name()
        st.error(f"⛔ Access Denied: You need {contact_name}'s permission to access hospital records.")
        st.info(
            f"💡 **Hint:** Talk to {contact_name} and ask for 'permission' to access medical records and the laboratory."
        )
        if st.button("Close", key="close_ward_registry"):
            st.session_state.action_modal = None
            st.rerun()
        return

    # Generate or retrieve ward registry
    if 'ward_registry' not in st.session_state:
        st.session_state.ward_registry = jl.generate_ward_registry()

    registry = st.session_state.ward_registry

    st.markdown("""
    This is the hospital's admission log for the past 30 days. Review the Chief Complaints and
    select patients whose charts you want to examine more closely in the Office.
    """)

    if st.button("✖ Close Registry", key="close_ward_registry"):
        st.session_state.action_modal = None
        st.rerun()

    st.markdown("---")

    # Initialize unlocked charts if not exists
    if 'unlocked_charts' not in st.session_state:
        # Start with the 2 known cases
        st.session_state.unlocked_charts = ['WARD-001', 'WARD-002']

    # Display registry with checkboxes
    st.markdown("### Select Patients to Pull Charts")

    # Create a selection state
    if 'selected_charts' not in st.session_state:
        st.session_state.selected_charts = []

    # Show table with selection
    selected_ids = st.multiselect(
        "Select patients to pull charts for:",
        options=registry['Patient_ID'].tolist(),
        default=st.session_state.selected_charts,
        format_func=lambda x: f"{x} - {registry[registry['Patient_ID']==x]['Chief_Complaint'].iloc[0][:50]}...",
        key="ward_registry_select"
    )

    # Display registry table
    st.dataframe(
        registry[['Patient_ID', 'Admission_Date', 'Age', 'Sex', 'Chief_Complaint', 'Diagnosis', 'Outcome']],
        use_container_width=True,
        height=400
    )

    # Pull charts button
    if len(selected_ids) > 0:
        if st.button(f"📄 Pull {len(selected_ids)} Charts", key="pull_charts", type="primary"):
            # Add selected IDs to unlocked charts
            for pid in selected_ids:
                if pid not in st.session_state.unlocked_charts:
                    st.session_state.unlocked_charts.append(pid)

            st.session_state.selected_charts = []
            st.success(f"✅ {len(selected_ids)} charts retrieved. View them in the Hospital Office.")
            st.rerun()


def render_hospital_charts_modal():
    """Render Hospital Charts modal showing unlocked patient charts."""
    from npc.unlock import get_hospital_records_contact_name

    st.subheader("📄 District Hospital - Medical Charts")

    # Check permission
    if not has_hospital_records_access():
        contact_name = get_hospital_records_contact_name()
        st.error(f"⛔ Access Denied: You need {contact_name}'s permission to access hospital records.")
        st.info(
            f"💡 **Hint:** Talk to {contact_name} and ask for 'permission' to access medical records and the laboratory."
        )
        if st.button("Close", key="close_charts"):
            st.session_state.action_modal = None
            st.rerun()
        return

    if st.button("✖ Close Charts", key="close_charts"):
        st.session_state.action_modal = None
        st.rerun()

    st.markdown("---")

    # Get unlocked charts
    unlocked_charts = st.session_state.get('unlocked_charts', ['WARD-001', 'WARD-002'])

    if len(unlocked_charts) == 0:
        st.info("No charts have been pulled yet. Visit the Ward Registry to select patient charts.")
        return

    st.markdown(f"**Available Charts:** {len(unlocked_charts)}")
    st.caption("These charts contain ONLY clinical data - no exposure history or risk factors.")

    # Chart selector
    selected_chart = st.selectbox(
        "Select a patient chart to review:",
        options=unlocked_charts,
        format_func=lambda x: f"Patient {x}",
        key="chart_selector"
    )

    if selected_chart:
        # Get chart text
        chart_text = jl.get_paper_chart_text(selected_chart)

        # Display chart in monospace font
        st.markdown(f"```\n{chart_text}\n```")


def render_deep_dive_charts_modal():
    """Render Deep Dive Charts modal (placeholder for future implementation)."""
    st.subheader("📊 Hospital Deep-Dive Charts")

    if st.button("✖ Close", key="close_deep_dive"):
        st.session_state.action_modal = None
        st.rerun()

    st.markdown("---")

    st.info("🚧 Deep-dive charts feature coming soon. This will show aggregate patterns across hospitalized cases.")
