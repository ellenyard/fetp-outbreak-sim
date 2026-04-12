"""Location and village profile configuration for the outbreak simulation.

Contains adventure-style location dictionaries for each scenario (AES and
Leptospirosis), area groupings, NPC placement, area metadata for visual
rendering, and village briefing profiles.
"""

import streamlit as st

# ---------------------------------------------------------------------------
# AES (JE / Sidero Valley) locations
# ---------------------------------------------------------------------------

AES_LOCATIONS = {
    # === NALU VILLAGE ===
    "nalu_village_center": {
        "name": "Nalu Village Center",
        "area": "Nalu Village",
        "description": "The heart of Nalu Village - a bustling community with houses clustered near the main road. The weekly market brings traders from surrounding areas. You see goats wandering near homes, chickens in the yards, and water buffalo being led to the paddies.",
        "image_path": "assets/Nalu/nalu_01_village_scene.png",
        "image_thumb": "assets/Nalu/nalu_01_village_scene.png",
        "icon": "🏘️",
        "npcs": ["mama_kofi", "auntie_ama"],
        "available_actions": [],
        "travel_time": 0.5,
    },
    "nalu_health_center": {
        "name": "Nalu Health Center",
        "area": "Nalu Village",
        "description": "A small health center staffed by Nurse Mai and community health workers. The building has a faded paint exterior and a long queue of waiting patients.",
        "image_path": "assets/Nalu/nalu_04_health_center_exterior.png",
        "image_thumb": "assets/Nalu/nalu_04_health_center_exterior.png",
        "icon": "🏥",
        "npcs": ["nurse_joy"],
        "available_actions": ["review_clinic_records", "view_hospital_records", "view_nalu_child_register"],
        "travel_time": 0.5,
    },
    "nalu_pig_coop": {
        "name": "Nalu Livestock Area",
        "area": "Nalu Village",
        "description": "A farming area about 500 meters from the village center where villagers keep various livestock. You see pigs in pens, chickens roaming freely, and a few goats tethered nearby. The smell is strong and mosquitoes swarm in the evening.",
        "image_path": "assets/Nalu/nalu_03_pig_pens.png",
        "image_thumb": "assets/Nalu/nalu_03_pig_pens.png",
        "icon": "🐷",
        "npcs": [],
        "available_actions": ["collect_pig_sample"],
        "travel_time": 0.5,
    },
    "nalu_rice_paddies": {
        "name": "Nalu Rice Paddies",
        "area": "Nalu Village",
        "description": "Extensive irrigated rice fields with standing water year-round. The paddies stretch to the horizon, broken only by narrow raised paths. Water buffalo work the fields.",
        "image_path": "assets/Nalu/nalu_02_rice_paddies.png",
        "image_thumb": "assets/Nalu/nalu_02_rice_paddies.png",
        "icon": "🌾",
        "npcs": [],
        "available_actions": ["collect_water_sample"],
        "travel_time": 0.5,
    },
    "nalu_school": {
        "name": "Nalu Primary School",
        "area": "Nalu Village",
        "description": "The main primary school serving Nalu and surrounding villages. Children from Kabwe walk here daily through the rice paddies.",
        "image_path": "assets/Kabwe/kabwe_03_children_school.png",
        "image_thumb": "assets/Kabwe/kabwe_03_children_school.png",
        "icon": "🏫",
        "npcs": ["teacher_grace"],
        "available_actions": ["review_attendance_records"],
        "travel_time": 0.5,
    },
    "nalu_canal": {
        "name": "Irrigation Canal",
        "area": "Nalu Village",
        "description": "Large pumps move water. You see many water birds and mosquitoes.",
        "image_path": "assets/Nalu/nalu_02_rice_paddies.png",
        "icon": "💧",
        "available_actions": [],
        "travel_time": 0.5,
    },
    "nalu_patient_house": {
        "name": "Patient A's House",
        "area": "Nalu Village",
        "description": "A traditional wooden house on stilts in Nalu Village. The family's livestock - several pigs, chickens, and ducks - are kept underneath and in a small pen nearby. Water jars sit on the porch for drinking and cooking. The house belongs to the family of one of the hospitalized children.",
        "image_path": "assets/Nalu/nalu_03_pig_pens.png",
        "image_thumb": "assets/Nalu/nalu_03_pig_pens.png",
        "icon": "🏠",
        "npcs": [],
        "available_actions": ["collect_household_water_sample"],
        "travel_time": 0.5,
    },
    # === KABWE VILLAGE ===
    "kabwe_village_center": {
        "name": "Kabwe Village Center",
        "area": "Kabwe Village",
        "description": "A medium-sized village on higher ground, 3km northeast of Nalu. Mixed farming community with both rice and upland crops. Chickens, goats, and buffalo are common. A few families keep pigs.",
        "image_path": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "image_thumb": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "icon": "🏡",
        "npcs": [],
        "available_actions": [],
        "travel_time": 0.5,
    },
    "kabwe_school_path": {
        "name": "School Path to Nalu",
        "area": "Kabwe Village",
        "description": "The walking path through rice paddies that Kabwe children use daily to reach school in Nalu. The path passes near irrigation canals.",
        "image_path": "assets/Kabwe/kabwe_02_village_path.png",
        "image_thumb": "assets/Kabwe/kabwe_02_village_path.png",
        "icon": "🚶",
        "npcs": [],
        "available_actions": [],
        "travel_time": 0.5,
    },
    "kabwe_school": {
        "name": "Kabwe Community School",
        "area": "Kabwe Village",
        "description": "A small community school where younger children attend before walking to the main school in Nalu. Teachers observe students for signs of illness.",
        "image_path": "assets/Kabwe/kabwe_03_children_school.png",
        "image_thumb": "assets/Kabwe/kabwe_03_children_school.png",
        "icon": "🏫",
        "npcs": [],
        "available_actions": ["review_attendance_records"],
        "travel_time": 0.5,
    },
    "kabwe_health_center": {
        "name": "Kabwe Health Center",
        "area": "Kabwe Village",
        "description": "A small health center where the visiting nurse holds clinics. Day 1 hub for reviewing clinic registers. Records are kept in a binder.",
        "image_path": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "icon": "🏥",
        "npcs": ["nurse_kabwe"],
        "available_actions": ["review_clinic_records", "review_kabwe_records"],
        "travel_time": 0.2,
    },
    "kabwe_paddies": {
        "name": "Kabwe Rice Fields",
        "area": "Kabwe Village",
        "description": "Smaller fields than Nalu. Farmers use buffalo to plow the fields. You see chickens foraging near the field edges and occasional goats grazing on the bunds.",
        "image_path": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "icon": "🌾",
        "available_actions": [],
        "travel_time": 0.5,
    },
    # === TAMU VILLAGE ===
    "tamu_remote_upland": {
        "name": "Tamu Remote Upland",
        "area": "Tamu Village",
        "description": "A smaller, more remote community in the foothills. Upland farming with cassava and yams. Spring-fed water sources. Goats and chickens are the main livestock - the terrain is too steep for buffalo or pigs.",
        "image_path": "assets/Tamu/tamu_02_village_remote.png",
        "image_thumb": "assets/Tamu/tamu_02_village_remote.png",
        "icon": "⛰️",
        "npcs": [],
        "available_actions": [],
        "travel_time": 1.0,
    },
    "tamu_forest_edge": {
        "name": "Tamu Forest Edge",
        "area": "Tamu Village",
        "description": "The boundary between the village and the surrounding forest. Wildlife occasionally ventures near the community. Goats graze here during the day under supervision.",
        "image_path": "assets/Tamu/tamu_03_forest_edge.png",
        "image_thumb": "assets/Tamu/tamu_03_forest_edge.png",
        "icon": "🌲",
        "npcs": [],
        "available_actions": [],
        "travel_time": 1.0,
    },
    "tamu_forest": {
        "name": "Upland Forest",
        "area": "Tamu Village",
        "description": "Dry and cool. Goats are grazing on the hills. Very few mosquitoes.",
        "image_path": "assets/Tamu/tamu_03_forest_edge.png",
        "icon": "🌲",
        "available_actions": [],
        "travel_time": 0.5,
    },
    "tamu_health_center": {
        "name": "Tamu Health Center",
        "area": "Tamu Village",
        "description": "Volunteer Sarah's home doubles as the village health center. She keeps the village health log here. Day 1 hub for reviewing clinic registers.",
        "icon": "📝",
        "npcs": ["chv_tamu"],
        "available_actions": ["review_clinic_records", "review_tamu_records"],
        "travel_time": 0.2,
    },
    # === DISTRICT HOSPITAL - ADMIN OFFICE ===
    "hospital_ward": {
        "name": "Hospital Ward (Triage)",
        "area": "Admin Office",
        "description": "The AES patients are being treated in this ward. Monitors beep and worried families gather in the corridor.",
        "image_path": "assets/Hospital/hospital_ward.png",
        "image_thumb": "assets/Hospital/hospital_ward.png",
        "icon": "🏥",
        "npcs": ["parent_ward", "parent_general", "dr_reyes", "nurse_maricel"],
        "available_actions": ["review_hospital_records", "collect_csf_sample", "collect_serum_sample", "view_ward_registry"],
        "travel_time": 0.5,
    },
    "hospital_office": {
        "name": "Hospital Admin (Charts)",
        "area": "Admin Office",
        "description": "The hospital director's office. Charts and reports are pinned to the walls. A window overlooks the hospital courtyard. Deep-dive charts are available here showing High Fever (>39C) and Lymphocytosis patterns.",
        "image_path": "assets/Hospital/hospital_admin.png",
        "image_thumb": "assets/Hospital/hospital_admin.png",
        "icon": "📋",
        "npcs": ["dr_chen", "dr_reyes"],
        "available_actions": ["review_hospital_records", "view_deep_dive_charts"],
        "travel_time": 0.0,
        "max_deep_dive_charts": 2,
    },
    # === DISTRICT HOSPITAL - LABORATORY ===
    "hospital_lab": {
        "name": "Hospital Laboratory",
        "area": "Laboratory",
        "description": "A small but functional laboratory. Basic labs are available immediately. Complex PCR and serology tests unlock on Day 4.",
        "image_path": "assets/Hospital/hospital_lab.png",
        "image_thumb": "assets/Hospital/hospital_lab.png",
        "icon": "🔬",
        "npcs": [],
        "available_actions": ["view_lab_results", "submit_lab_samples"],
        "travel_time": 0.0,
        "unlock_day": 1,
        "pcr_serology_unlock_day": 4,
    },
    # === DISTRICT OFFICE ===
    "district_office": {
        "name": "District Health Office",
        "area": "District Office",
        "description": "The administrative hub for district health operations. Officials, technical officers, and the Environmental Officer work from here.",
        "image_path": "assets/Hospital/hospital_admin.png",
        "image_thumb": "assets/Hospital/hospital_admin.png",
        "icon": "🏛️",
        "npcs": ["vet_amina", "mr_osei", "mayor_simon", "env_officer"],
        "available_actions": ["request_data", "plan_interventions", "view_village_profile"],
        "travel_time": 0.5,
    },
    # === MINING AREA ===
    "mining_area": {
        "name": "Mining Compound",
        "area": "Mining Area",
        "description": "The mining operation has expanded recently, creating new irrigation ponds. Worker housing is nearby.",
        "image_path": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "image_thumb": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "icon": "⛏️",
        "npcs": ["foreman_rex"],
        "available_actions": ["collect_water_sample"],
        "travel_time": 1.0,
    },
    # === MARKET ===
    "central_market": {
        "name": "Central Market",
        "area": "Nalu Village",
        "description": "The weekly market where traders from all villages gather. A good place to hear rumors and observe community patterns.",
        "image_path": "assets/Nalu/nalu_01_village_scene.png",
        "image_thumb": "assets/Nalu/nalu_01_village_scene.png",
        "icon": "🛒",
        "npcs": ["auntie_ama"],
        "available_actions": [],
        "travel_time": 0.5,
    },
    # === HEALER ===
    "healer_clinic": {
        "name": "Traditional Healer's Clinic",
        "area": "Nalu Village",
        "description": "A small private clinic run by Healer Somchai. He saw some of the earliest cases before they went to the hospital.",
        "image_path": "assets/Nalu/nalu_01_village_scene.png",
        "image_thumb": "assets/Nalu/nalu_01_village_scene.png",
        "icon": "🌿",
        "npcs": ["healer_marcus"],
        "available_actions": ["review_healer_records"],
        "travel_time": 0.5,
    },
}

# ---------------------------------------------------------------------------
# Leptospirosis (Rivergate) locations
# ---------------------------------------------------------------------------

LEPTO_LOCATIONS = {
    # === WARD NORTHBEND ===
    "malinao_ward_hall": {
        "name": "Ward Northbend Hall",
        "area": "Ward Northbend",
        "description": "The ward hall for Northbend. Community leaders meet here to discuss recent cases and flooding in nearby rice fields.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "icon": "🏘️",
        "npcs": ["kapitana_gloria", "mang_tonyo", "luz_fernandez"],
        "available_actions": [],
        "travel_time": 0.5,
    },
    # === WARD EAST TERRACE ===
    "san_rafael_ward_hall": {
        "name": "East Terrace Ward Hall",
        "area": "East Terrace",
        "description": "The ward hall where local leaders share updates on recent illnesses and sanitation concerns.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "icon": "🏘️",
        "npcs": ["pastor_elijah"],
        "available_actions": [],
        "travel_time": 0.5,
    },
    # === WARD SOUTHSHORE ===
    "bagong_silang_ward_hall": {
        "name": "Southshore Ward Hall",
        "area": "Southshore",
        "description": "A busy ward hall where residents report illness clusters after heavy rains.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "icon": "🏘️",
        "npcs": [],
        "available_actions": [],
        "travel_time": 0.5,
    },
    # === WARD HIGHRIDGE ===
    "santa_cruz_ward_hall": {
        "name": "Highridge Ward Hall",
        "area": "Highridge",
        "description": "A modest ward office near low-lying farms where floodwaters tend to linger.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "icon": "🏘️",
        "npcs": [],
        "available_actions": [],
        "travel_time": 0.5,
    },
    # === DISTRICT HOSPITAL ===
    "lepto_district_hospital": {
        "name": "District Hospital Ward",
        "area": "District Hospital",
        "description": "The district hospital ward where severe cases are being managed.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_district_hospital_ward.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_district_hospital_ward.png",
        "icon": "🏥",
        "npcs": ["dr_reyes", "nurse_maricel"],
        "available_actions": ["review_hospital_records"],
        "travel_time": 0.5,
    },
    # === RHU ===
    "rhu_office": {
        "name": "Rural Health Unit (RHU) Office",
        "area": "RHU",
        "description": "The RHU office coordinating ward surveillance and case reporting.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_health_center_northbend.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_health_center_northbend.png",
        "icon": "🏥",
        "npcs": ["dr_mendoza", "dr_villareal", "dr_lacson"],
        "available_actions": ["request_data"],
        "travel_time": 0.5,
    },
    # === DRRM OFFICE ===
    "drrm_office": {
        "name": "DRRM Office",
        "area": "DRRM Office",
        "description": "Disaster Risk Reduction and Management office coordinating flood response and environmental cleanup.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_disaster_office_interior.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_disaster_office_interior.png",
        "icon": "🏛️",
        "npcs": ["engr_ramon", "mayor_villanueva"],
        "available_actions": ["plan_interventions"],
        "travel_time": 0.5,
    },
    # === MINING AREA ===
    "lepto_mining_area": {
        "name": "Mining Area",
        "area": "Mining Area",
        "description": "Mining runoff and standing water create potential exposure risks.",
        "image_path": "scenarios/lepto_rivergate/assets/loc_riverside_village_street.png",
        "image_thumb": "scenarios/lepto_rivergate/assets/loc_riverside_village_street.png",
        "icon": "⛏️",
        "npcs": ["mr_chen_wei"],
        "available_actions": ["collect_water_sample"],
        "travel_time": 1.0,
    },
}

# ---------------------------------------------------------------------------
# Area -> sub-location mappings
# ---------------------------------------------------------------------------

AES_AREA_LOCATIONS = {
    "Nalu Village": ["nalu_village_center", "nalu_health_center", "nalu_pig_coop", "nalu_rice_paddies", "nalu_school", "nalu_canal", "central_market", "healer_clinic"],
    "Kabwe Village": ["kabwe_village_center", "kabwe_school_path", "kabwe_school", "kabwe_health_center", "kabwe_paddies"],
    "Tamu Village": ["tamu_remote_upland", "tamu_forest_edge", "tamu_forest", "tamu_health_center"],
    "District Hospital": ["hospital_office", "hospital_ward", "hospital_lab"],
    "Admin Office": ["hospital_ward", "hospital_office"],
    "Laboratory": ["hospital_lab"],
    "District Office": ["district_office"],
    "Mining Area": ["mining_area"],
}

LEPTO_AREA_LOCATIONS = {
    "Ward Northbend": ["malinao_ward_hall"],
    "East Terrace": ["san_rafael_ward_hall"],
    "Southshore": ["bagong_silang_ward_hall"],
    "Highridge": ["santa_cruz_ward_hall"],
    "District Hospital": ["lepto_district_hospital"],
    "RHU": ["rhu_office"],
    "DRRM Office": ["drrm_office"],
    "Mining Area": ["lepto_mining_area"],
}

# ---------------------------------------------------------------------------
# Scenario initial NPCs (unlocked at start)
# ---------------------------------------------------------------------------

SCENARIO_INITIAL_NPCS = {
    "aes_sidero_valley": ["dr_chen", "nurse_joy", "mama_kofi", "foreman_rex", "teacher_grace"],
    "lepto_rivergate": ["dr_reyes", "nurse_maricel", "kapitana_gloria", "dr_mendoza"],
}

# ---------------------------------------------------------------------------
# Area metadata (hero images, descriptions for visual rendering)
# ---------------------------------------------------------------------------

AES_AREA_METADATA = {
    "Admin Office": {
        "image_exterior": "assets/Hospital/hospital_exterior.png",
        "description": "The hospital ward and administrative office where AES patients are treated. {contact_name} oversees triage and patient charts. Deep-dive clinical data is available here.",
        "icon": "🏥",
    },
    "Laboratory": {
        "image_exterior": "assets/Hospital/hospital_lab.png",
        "description": "The hospital laboratory. Basic tests are available immediately. Complex PCR and serology tests unlock on Day 4.",
        "icon": "🔬",
    },
    "District Hospital": {
        "image_exterior": "assets/Hospital/hospital_exterior.png",
        "description": "The district hospital where AES patients are being treated. Contains the administrative office, patient ward, and laboratory facilities. {contact_name} oversees operations.",
        "icon": "🏥",
    },
    "Nalu Village": {
        "image_exterior": "assets/Nalu/nalu_01_village_scene.png",
        "description": "The largest settlement in Sidero Valley. The economy centers on rice cultivation and pig farming. Most AES cases come from here.",
        "icon": "🏘️",
    },
    "Kabwe Village": {
        "image_exterior": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "description": "Located 3km northeast of Nalu on higher ground. Children walk through rice paddies to attend school in Nalu.",
        "icon": "🏡",
    },
    "Tamu Village": {
        "image_exterior": "assets/Tamu/tamu_02_village_remote.png",
        "description": "A smaller, more remote community in the foothills. Upland farming with less standing water.",
        "icon": "⛰️",
    },
    "District Office": {
        "image_exterior": "assets/Hospital/hospital_admin.png",
        "description": "The administrative hub of district health operations. Houses the public health, veterinary, and environmental health teams. Key officials coordinate outbreak response from here.",
        "icon": "🏛️",
    },
    "Mining Area": {
        "image_exterior": "assets/Kabwe/kabwe_01_mixed_farming.png",
        "description": "The mining operation has expanded recently, creating new irrigation ponds and disrupting local ecosystems. Worker housing and canteen facilities are located nearby.",
        "icon": "⛏️",
    },
}

LEPTO_AREA_METADATA = {
    "Ward Northbend": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "description": "Flood-prone farming community reporting fevers and muscle pain after heavy rains.",
        "icon": "🏘️",
    },
    "East Terrace": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_municipal_hall_exterior.png",
        "description": "A riverside ward with recent standing water and livestock exposure.",
        "icon": "🏘️",
    },
    "Southshore": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "description": "Low-lying ward where residents report flooding in rice fields and drainage canals.",
        "icon": "🏘️",
    },
    "Highridge": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_ward_hall_northbend.png",
        "description": "Ward near the irrigation system with stagnant water and rodent activity.",
        "icon": "🏘️",
    },
    "District Hospital": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_district_hospital_ward.png",
        "description": "Referral hospital managing severe cases from the district.",
        "icon": "🏥",
    },
    "RHU": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_health_center_northbend.png",
        "description": "Rural Health Unit coordinating ward surveillance and reporting.",
        "icon": "🏥",
    },
    "DRRM Office": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_disaster_office_interior.png",
        "description": "Disaster response office coordinating flood mitigation and cleanup.",
        "icon": "🏛️",
    },
    "Mining Area": {
        "image_exterior": "scenarios/lepto_rivergate/assets/loc_riverside_village_street.png",
        "description": "Mining area with runoff and pooled water creating potential exposure risks.",
        "icon": "⛏️",
    },
}

# ---------------------------------------------------------------------------
# NPC -> primary location mappings
# ---------------------------------------------------------------------------

AES_NPC_LOCATIONS = {
    # JE scenario NPCs
    "dr_chen": "hospital_ward",
    "dr_reyes": "hospital_ward",  # Leptospirosis scenario
    "patient_parent": "hospital_ward",
    "ward_parent": "hospital_ward",
    "nurse_joy": "nalu_health_center",
    "healer_marcus": "healer_clinic",
    "mama_kofi": "nalu_village_center",
    "teacher_grace": "nalu_school",
    "foreman_rex": "mining_area",
    "auntie_ama": "central_market",
    "vet_amina": "district_office",
    "env_officer": "district_office",
    "mr_osei": "district_office",
    "mayor_simon": "district_office",
    "nurse_kabwe": "kabwe_health_center",
    "chv_tamu": "tamu_health_center",
}

LEPTO_NPC_LOCATIONS = {
    "dr_reyes": "lepto_district_hospital",
    "nurse_maricel": "lepto_district_hospital",
    "kapitana_gloria": "malinao_ward_hall",
    "dr_mendoza": "rhu_office",
    "dr_villareal": "rhu_office",
    "mang_tonyo": "malinao_ward_hall",
    "luz_fernandez": "malinao_ward_hall",
    "pastor_elijah": "san_rafael_ward_hall",
    "mayor_villanueva": "drrm_office",
    "engr_ramon": "drrm_office",
    "mr_chen_wei": "lepto_mining_area",
    "dr_lacson": "rhu_office",
}

# ---------------------------------------------------------------------------
# Accessor helpers
# ---------------------------------------------------------------------------


def get_current_scenario_id() -> str:
    return st.session_state.get("current_scenario", "aes_sidero_valley")


def get_locations(scenario_id: str | None = None) -> dict:
    scenario_id = scenario_id or get_current_scenario_id()
    if scenario_id == "lepto_rivergate":
        return LEPTO_LOCATIONS
    return AES_LOCATIONS


def get_area_locations(scenario_id: str | None = None) -> dict:
    scenario_id = scenario_id or get_current_scenario_id()
    if scenario_id == "lepto_rivergate":
        return LEPTO_AREA_LOCATIONS
    return AES_AREA_LOCATIONS


def get_area_metadata(scenario_id: str | None = None) -> dict:
    scenario_id = scenario_id or get_current_scenario_id()
    if scenario_id == "lepto_rivergate":
        return LEPTO_AREA_METADATA
    return AES_AREA_METADATA


def get_npc_locations(scenario_id: str | None = None) -> dict:
    scenario_id = scenario_id or get_current_scenario_id()
    if scenario_id == "lepto_rivergate":
        return LEPTO_NPC_LOCATIONS
    return AES_NPC_LOCATIONS


# ---------------------------------------------------------------------------
# Village briefing profiles
# ---------------------------------------------------------------------------

VILLAGE_PROFILES = {
    "nalu": {
        "name": "Nalu Village",
        "population": 1850,
        "households": 340,
        "description": {
            "en": """
**Nalu Village** is the largest settlement in Sidero Valley, located along the main river
that feeds the extensive rice paddy system. The village economy is centered on rice
cultivation and pig farming.

**Key Facts:**
- **Population:** 1,850 (2024 census)
- **Households:** ~340
- **Main livelihoods:** Rice farming (65%), pig rearing (45%), fishing (20%)
- **Health facility:** Nalu Health Center (1 nurse, 2 community health workers)
- **Schools:** 1 primary school (enrollment: 380)
- **Water source:** River, hand-dug wells, 2 boreholes
- **Sanitation:** Mix of pit latrines and open defecation

**Geographic Features:**
- Located along the main river
- Surrounded by irrigated rice paddies on three sides
- Pig cooperative located near village center

**Health Information (District Health Office, 2024):**
- Under-5 mortality: 45 per 1,000 live births
- Top health concerns: Malaria, diarrheal diseases
- Nearest hospital: District Hospital (12 km)
""",
            "es": """
**Aldea de Nalu** es el asentamiento más grande del Valle de Sidero...
""",
            "fr": """
**Village de Nalu** est le plus grand établissement de la Vallée de Sidero...
"""
        },
        "images": ["rice_paddies", "pig_farm", "village_scene"]
    },
    "kabwe": {
        "name": "Kabwe Village",
        "population": 920,
        "households": 175,
        "description": {
            "en": """
**Kabwe Village** is a medium-sized farming community located 3 km northeast of Nalu,
on slightly higher ground. Many residents work in both Kabwe and Nalu.

**Key Facts:**
- **Population:** 920 (2024 census)
- **Households:** ~175
- **Main livelihoods:** Mixed farming (maize, vegetables), some rice, pig rearing
- **Health facility:** None (served by Nalu Health Center)
- **Schools:** 1 primary school (enrollment: 165), children attend secondary in Nalu
- **Water source:** 3 boreholes, seasonal stream
- **Sanitation:** Pit latrines (60%), open defecation (40%)

**Geographic Features:**
- Higher elevation than Nalu
- Mixed agricultural zone with both rice and upland crops
- Path to Nalu passes through agricultural areas

**Health Information:**
- Residents use Nalu Health Center
- Top health concerns: Malaria, respiratory infections
""",
            "es": "**Aldea de Kabwe** es una comunidad agrícola de tamaño mediano...",
            "fr": "**Village de Kabwe** est une communauté agricole de taille moyenne..."
        },
        "images": ["mixed_farming", "village_path", "children_school"]
    },
    "tamu": {
        "name": "Tamu Village",
        "population": 650,
        "households": 125,
        "description": {
            "en": """
**Tamu Village** is a smaller, more remote community located 5 km west of Nalu,
in the foothills away from the main rice-growing areas.

**Key Facts:**
- **Population:** 650 (2024 census)
- **Households:** ~125
- **Main livelihoods:** Upland farming (cassava, yams), small-scale livestock, charcoal
- **Health facility:** Community health volunteer only
- **Schools:** 1 small primary school (enrollment: 95)
- **Water source:** Spring-fed wells, rainwater collection
- **Sanitation:** Pit latrines (45%), open defecation (55%)

**Geographic Features:**
- Higher elevation, drier terrain
- Upland farming area (no rice cultivation)
- Primarily goats and chickens for livestock
- More forested areas nearby

**Health Information:**
- Residents occasionally travel to Nalu for market/health services
- Top health concerns: Respiratory infections, malnutrition
- Community health volunteer provides basic care
""",
            "es": "**Aldea de Tamu** es una comunidad más pequeña y remota...",
            "fr": "**Village de Tamu** est une communauté plus petite et plus éloignée..."
        },
        "images": ["upland_farming", "village_remote", "forest_edge"]
    },
    # === LEPTO RIVERGATE WARDS ===
    "ward_northbend": {
        "name": "Ward Northbend",
        "population": 480,
        "households": 95,
        "description": {
            "en": """
**Ward Northbend** is the most severely flood-affected area of Rivergate municipality,
located at a bend in the Kantara River tributary where floodwaters accumulated deepest.

**Key Facts:**
- **Population:** ~480 residents in ~95 households
- **Main livelihoods:** Rice farming (70%), fishing (15%), day labor (15%)
- **Health facility:** Small barangay health station (1 midwife)
- **Ward Captain:** Captain Gloria Ramos (8 years in office)
- **Water source:** Community wells, river access
- **Sanitation:** Pit latrines, some open defecation near river

**Typhoon Halcyon Impact (Oct 8-10, 2024):**
- Chest-to-head-deep flooding in low-lying areas
- Riverside Hamlet most severely affected
- Rice paddies completely submerged - harvest destroyed
- Extensive flood cleanup work required Oct 10-15
- High rat displacement from flooded burrows

**Epidemiologic Significance:**
- **OUTBREAK EPICENTER** - 28 of 34 confirmed cases
- Highest cleanup work exposure
- Most barefoot wading in contaminated floodwater
- Dense pig farming near residential areas
""",
        },
        "images": ["flood_cleanup", "rice_paddies", "ward_hall"]
    },
    "ward_east_terrace": {
        "name": "Ward East Terrace",
        "population": 620,
        "households": 130,
        "description": {
            "en": """
**Ward East Terrace** is a mixed residential and commercial area east of the town center,
with moderate flooding during Typhoon Halcyon.

**Key Facts:**
- **Population:** ~620 residents in ~130 households
- **Main livelihoods:** Market vendors, construction workers, small businesses
- **Health facility:** None (uses District Hospital or RHU)
- **Water source:** Municipal water system, some private wells
- **Market:** Local market with drainage issues

**Typhoon Halcyon Impact:**
- Moderate flooding in low-lying market area
- Drainage systems overwhelmed
- Some flood cleanup work required

**Epidemiologic Significance:**
- Secondary case cluster (4 cases)
- Less extensive flood exposure than Northbend
- Some residents participated in Northbend cleanup
""",
        },
        "images": ["market_area", "residential_street"]
    },
    "ward_southshore": {
        "name": "Ward Southshore",
        "population": 350,
        "households": 75,
        "description": {
            "en": """
**Ward Southshore** is a fishing community along the southern riverbank,
with moderate flood exposure during Typhoon Halcyon.

**Key Facts:**
- **Population:** ~350 residents in ~75 households
- **Main livelihoods:** Fishing (60%), small farming (25%), labor (15%)
- **Health facility:** Community health volunteer
- **Water source:** Communal well, river access
- **Notable:** Fishing dock, boat storage area

**Typhoon Halcyon Impact:**
- Moderate flooding near river
- Fishing equipment damaged
- Some flood cleanup activities

**Epidemiologic Significance:**
- Few cases (2 confirmed)
- Lower flood cleanup participation than Northbend
""",
        },
        "images": ["fishing_dock", "river_access"]
    },
    "ward_highridge": {
        "name": "Ward Highridge",
        "population": 420,
        "households": 85,
        "description": {
            "en": """
**Ward Highridge** is an upland farming community on higher ground west of town center.
Served as evacuation site during Typhoon Halcyon due to minimal flooding.

**Key Facts:**
- **Population:** ~420 residents in ~85 households
- **Main livelihoods:** Upland farming (vegetables, fruits), small livestock
- **Health facility:** None (uses RHU in town center)
- **Water source:** Protected spring, municipal water connection
- **Notable:** Evacuation center at ward hall

**Typhoon Halcyon Impact:**
- MINIMAL FLOODING due to elevation
- Served as evacuation site for Northbend residents
- Clean water source remained uncontaminated

**Epidemiologic Significance:**
- CONTROL AREA - No confirmed leptospirosis cases
- Residents did not participate in flood cleanup
- Can serve as comparison group for exposure analysis
""",
        },
        "images": ["upland_farming", "evacuation_site", "protected_spring"]
    }
}
