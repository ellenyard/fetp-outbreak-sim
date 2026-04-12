import streamlit as st
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from i18n.translate import t
from config.locations import get_current_scenario_id, VILLAGE_PROFILES


def get_village_photos(village_name):
    """
    Get list of photos for a village from the assets directory.

    Returns a dict mapping photo base names to their full paths, or None if no photos exist.
    """
    assets_dir = Path("assets")
    village_dir = assets_dir / village_name.capitalize()

    if not village_dir.exists():
        return None

    # Get all image files
    photo_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg']:
        photo_files.extend(village_dir.glob(ext))

    if not photo_files:
        return None

    # Create a dict mapping base names to paths
    photos = {}
    for photo_path in sorted(photo_files):
        photos[photo_path.stem] = photo_path

    return photos


def view_village_profiles():
    """Display village briefing documents with stats and images."""
    st.header("Village Profiles - Sidero Valley")

    st.markdown("""
    These background documents provide official information about each village in the investigation area.
    Review these to understand the local context before conducting interviews.
    """)

    lang = st.session_state.get("language", "en")

    tabs = st.tabs(["Nalu Village", "Kabwe Village", "Tamu Village"])

    # SVG illustrations for each village
    nalu_rice_svg = '''
    <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
        <!-- Sky -->
        <rect width="400" height="200" fill="#87CEEB"/>
        <!-- Sun -->
        <circle cx="350" cy="40" r="25" fill="#FFD700"/>
        <!-- Mountains in background -->
        <polygon points="0,120 80,60 160,120" fill="#6B8E23"/>
        <polygon points="100,120 200,40 300,120" fill="#556B2F"/>
        <polygon points="250,120 350,70 400,120" fill="#6B8E23"/>
        <!-- Rice paddies (flooded fields) -->
        <rect x="0" y="120" width="400" height="80" fill="#4A7C59"/>
        <!-- Water reflection lines -->
        <rect x="10" y="130" width="80" height="3" fill="#87CEEB" opacity="0.5"/>
        <rect x="100" y="145" width="90" height="3" fill="#87CEEB" opacity="0.5"/>
        <rect x="200" y="135" width="70" height="3" fill="#87CEEB" opacity="0.5"/>
        <rect x="280" y="150" width="100" height="3" fill="#87CEEB" opacity="0.5"/>
        <rect x="50" y="160" width="60" height="3" fill="#87CEEB" opacity="0.5"/>
        <rect x="150" y="170" width="80" height="3" fill="#87CEEB" opacity="0.5"/>
        <!-- Rice plants (small green lines) -->
        <g stroke="#228B22" stroke-width="2">
            <line x1="30" y1="140" x2="30" y2="125"/>
            <line x1="50" y1="145" x2="50" y2="130"/>
            <line x1="70" y1="140" x2="70" y2="125"/>
            <line x1="120" y1="150" x2="120" y2="135"/>
            <line x1="140" y1="145" x2="140" y2="130"/>
            <line x1="160" y1="155" x2="160" y2="140"/>
            <line x1="220" y1="145" x2="220" y2="130"/>
            <line x1="250" y1="150" x2="250" y2="135"/>
            <line x1="300" y1="140" x2="300" y2="125"/>
            <line x1="340" y1="155" x2="340" y2="140"/>
            <line x1="370" y1="145" x2="370" y2="130"/>
        </g>
        <!-- Birds flying -->
        <text x="180" y="50" font-size="10">🐦</text>
        <text x="280" y="45" font-size="8">🐦</text>
        <!-- Label -->
        <text x="200" y="190" text-anchor="middle" font-size="14" fill="white" font-weight="bold">Rice Paddies - Irrigated Fields</text>
    </svg>
    '''

    nalu_pigs_svg = '''
    <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
        <!-- Sky -->
        <rect width="400" height="200" fill="#87CEEB"/>
        <!-- Ground -->
        <rect x="0" y="140" width="400" height="60" fill="#8B4513"/>
        <!-- Mud patches -->
        <ellipse cx="100" cy="160" rx="40" ry="15" fill="#654321"/>
        <ellipse cx="280" cy="165" rx="50" ry="18" fill="#654321"/>
        <!-- Fence -->
        <rect x="20" y="100" width="360" height="5" fill="#8B4513"/>
        <rect x="30" y="60" width="8" height="80" fill="#8B4513"/>
        <rect x="100" y="60" width="8" height="80" fill="#8B4513"/>
        <rect x="170" y="60" width="8" height="80" fill="#8B4513"/>
        <rect x="240" y="60" width="8" height="80" fill="#8B4513"/>
        <rect x="310" y="60" width="8" height="80" fill="#8B4513"/>
        <rect x="20" y="80" width="360" height="4" fill="#8B4513"/>
        <!-- Shelter roof -->
        <polygon points="280,40 350,40 380,70 250,70" fill="#A0522D"/>
        <rect x="260" y="70" width="110" height="50" fill="#DEB887"/>
        <!-- Pigs -->
        <ellipse cx="80" cy="130" rx="25" ry="18" fill="#FFB6C1"/>
        <circle cx="60" cy="125" r="8" fill="#FFB6C1"/>
        <ellipse cx="150" cy="135" rx="22" ry="15" fill="#FFC0CB"/>
        <circle cx="132" cy="130" r="7" fill="#FFC0CB"/>
        <ellipse cx="200" cy="128" rx="20" ry="14" fill="#FFB6C1"/>
        <circle cx="184" cy="123" r="6" fill="#FFB6C1"/>
        <!-- More pigs in background -->
        <ellipse cx="290" cy="115" rx="18" ry="12" fill="#FFA0AB"/>
        <ellipse cx="330" cy="118" rx="16" ry="11" fill="#FFA0AB"/>
        <!-- Flies -->
        <text x="120" y="115" font-size="8">•</text>
        <text x="180" y="110" font-size="8">•</text>
        <text x="250" y="105" font-size="8">•</text>
        <!-- Label -->
        <text x="200" y="190" text-anchor="middle" font-size="14" fill="white" font-weight="bold">Pig Cooperative - ~200 Pigs Near Village</text>
    </svg>
    '''

    kabwe_mixed_svg = '''
    <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
        <!-- Sky -->
        <rect width="400" height="200" fill="#87CEEB"/>
        <!-- Hills -->
        <ellipse cx="100" cy="140" rx="120" ry="50" fill="#6B8E23"/>
        <ellipse cx="300" cy="150" rx="140" ry="45" fill="#556B2F"/>
        <!-- Ground -->
        <rect x="0" y="140" width="400" height="60" fill="#8B7355"/>
        <!-- Rice paddy section (left) -->
        <rect x="0" y="140" width="150" height="40" fill="#4A7C59"/>
        <rect x="10" y="150" width="40" height="2" fill="#87CEEB" opacity="0.5"/>
        <rect x="60" y="155" width="50" height="2" fill="#87CEEB" opacity="0.5"/>
        <!-- Maize/upland section (right) -->
        <g stroke="#DAA520" stroke-width="2">
            <line x1="200" y1="140" x2="200" y2="110"/>
            <line x1="220" y1="140" x2="220" y2="115"/>
            <line x1="240" y1="140" x2="240" y2="105"/>
            <line x1="260" y1="140" x2="260" y2="112"/>
            <line x1="280" y1="140" x2="280" y2="108"/>
            <line x1="300" y1="140" x2="300" y2="115"/>
            <line x1="320" y1="140" x2="320" y2="110"/>
            <line x1="340" y1="140" x2="340" y2="118"/>
            <line x1="360" y1="140" x2="360" y2="105"/>
        </g>
        <!-- Corn tops -->
        <g fill="#FFD700">
            <circle cx="200" cy="105" r="4"/>
            <circle cx="240" cy="100" r="4"/>
            <circle cx="280" cy="103" r="4"/>
            <circle cx="320" cy="105" r="4"/>
            <circle cx="360" cy="100" r="4"/>
        </g>
        <!-- Path dividing -->
        <rect x="155" y="140" width="30" height="60" fill="#C4A76C"/>
        <!-- Small pig pen -->
        <rect x="380" y="150" width="15" height="15" fill="#8B4513"/>
        <ellipse cx="387" cy="160" rx="5" ry="4" fill="#FFB6C1"/>
        <!-- Label -->
        <text x="200" y="190" text-anchor="middle" font-size="14" fill="white" font-weight="bold">Mixed Farming - Rice Paddies & Upland Crops</text>
    </svg>
    '''

    kabwe_path_svg = '''
    <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
        <!-- Sky -->
        <rect width="400" height="200" fill="#87CEEB"/>
        <!-- Rice paddies (green with water) -->
        <rect x="0" y="100" width="400" height="100" fill="#4A7C59"/>
        <!-- Water reflections -->
        <rect x="20" y="120" width="60" height="3" fill="#87CEEB" opacity="0.4"/>
        <rect x="100" y="140" width="80" height="3" fill="#87CEEB" opacity="0.4"/>
        <rect x="250" y="130" width="70" height="3" fill="#87CEEB" opacity="0.4"/>
        <rect x="50" y="160" width="90" height="3" fill="#87CEEB" opacity="0.4"/>
        <rect x="300" y="155" width="80" height="3" fill="#87CEEB" opacity="0.4"/>
        <!-- Path through paddies -->
        <path d="M 0,180 Q 100,150 200,160 Q 300,170 400,140" stroke="#C4A76C" stroke-width="20" fill="none"/>
        <!-- Children walking -->
        <text x="120" y="155" font-size="16">👧</text>
        <text x="150" y="160" font-size="14">👦</text>
        <text x="180" y="158" font-size="15">👧</text>
        <!-- School building in distance -->
        <rect x="350" y="80" width="40" height="40" fill="#CD853F"/>
        <polygon points="350,80 370,60 390,80" fill="#8B0000"/>
        <rect x="365" y="95" width="10" height="25" fill="#8B4513"/>
        <!-- Sign -->
        <text x="370" y="75" font-size="8" text-anchor="middle">SCHOOL</text>
        <!-- Village houses in background -->
        <rect x="20" y="70" width="25" height="25" fill="#DEB887"/>
        <polygon points="20,70 32,55 45,70" fill="#8B4513"/>
        <rect x="60" y="75" width="20" height="20" fill="#DEB887"/>
        <polygon points="60,75 70,62 80,75" fill="#8B4513"/>
        <!-- Label -->
        <text x="200" y="195" text-anchor="middle" font-size="12" fill="white" font-weight="bold">Children Walk Through Paddies to School in Nalu</text>
    </svg>
    '''

    tamu_upland_svg = '''
    <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
        <!-- Sky -->
        <rect width="400" height="200" fill="#87CEEB"/>
        <!-- Sun -->
        <circle cx="350" cy="35" r="25" fill="#FFD700"/>
        <!-- Hills/mountains -->
        <polygon points="0,130 100,50 200,130" fill="#228B22"/>
        <polygon points="150,130 280,30 400,130" fill="#2E8B57"/>
        <!-- Dry ground -->
        <rect x="0" y="130" width="400" height="70" fill="#C4A76C"/>
        <!-- Cassava/yam plants -->
        <g fill="#228B22">
            <ellipse cx="50" cy="140" rx="20" ry="15"/>
            <ellipse cx="120" cy="145" rx="25" ry="18"/>
            <ellipse cx="200" cy="138" rx="22" ry="16"/>
            <ellipse cx="280" cy="142" rx="20" ry="14"/>
            <ellipse cx="350" cy="140" rx="25" ry="17"/>
        </g>
        <!-- Goats instead of pigs -->
        <text x="100" y="165" font-size="16">🐐</text>
        <text x="250" y="160" font-size="14">🐐</text>
        <!-- Chickens -->
        <text x="180" y="170" font-size="12">🐔</text>
        <text x="320" y="168" font-size="11">🐔</text>
        <!-- No mosquitoes - dry terrain -->
        <!-- Trees -->
        <rect x="30" y="100" width="8" height="30" fill="#8B4513"/>
        <circle cx="34" cy="90" r="20" fill="#228B22"/>
        <rect x="370" y="95" width="8" height="35" fill="#8B4513"/>
        <circle cx="374" cy="85" r="22" fill="#2E8B57"/>
        <!-- Label -->
        <text x="200" y="190" text-anchor="middle" font-size="14" fill="#333" font-weight="bold">Upland Terrain - Cassava & Yam Farming</text>
    </svg>
    '''

    tamu_forest_svg = '''
    <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
        <!-- Sky -->
        <rect width="400" height="200" fill="#87CEEB"/>
        <!-- Forest background -->
        <rect x="0" y="80" width="400" height="120" fill="#228B22"/>
        <!-- Multiple trees -->
        <g>
            <!-- Tree 1 -->
            <rect x="30" y="60" width="12" height="80" fill="#8B4513"/>
            <circle cx="36" cy="45" r="30" fill="#2E8B57"/>
            <!-- Tree 2 -->
            <rect x="90" y="50" width="15" height="90" fill="#8B4513"/>
            <circle cx="97" cy="35" r="35" fill="#228B22"/>
            <!-- Tree 3 -->
            <rect x="160" y="70" width="10" height="70" fill="#8B4513"/>
            <circle cx="165" cy="55" r="28" fill="#2E8B57"/>
            <!-- Tree 4 -->
            <rect x="220" y="55" width="14" height="85" fill="#8B4513"/>
            <circle cx="227" cy="40" r="32" fill="#228B22"/>
            <!-- Tree 5 -->
            <rect x="290" y="65" width="11" height="75" fill="#8B4513"/>
            <circle cx="295" cy="50" r="30" fill="#2E8B57"/>
            <!-- Tree 6 -->
            <rect x="350" y="45" width="16" height="95" fill="#8B4513"/>
            <circle cx="358" cy="30" r="38" fill="#228B22"/>
        </g>
        <!-- Ground/path -->
        <rect x="0" y="160" width="400" height="40" fill="#C4A76C"/>
        <!-- Well (spring water) -->
        <ellipse cx="200" cy="175" rx="25" ry="10" fill="#4169E1"/>
        <ellipse cx="200" cy="170" rx="28" ry="8" fill="#696969" fill-opacity="0.5"/>
        <!-- Village houses -->
        <rect x="100" y="145" width="20" height="20" fill="#DEB887"/>
        <polygon points="100,145 110,132 120,145" fill="#8B4513"/>
        <rect x="280" y="148" width="18" height="18" fill="#DEB887"/>
        <polygon points="280,148 289,136 298,148" fill="#8B4513"/>
        <!-- Label -->
        <text x="200" y="195" text-anchor="middle" font-size="13" fill="#333" font-weight="bold">Forested Area - Spring-Fed Water, Less Standing Water</text>
    </svg>
    '''

    for i, (village_key, village) in enumerate(VILLAGE_PROFILES.items()):
        with tabs[i]:
            col1, col2 = st.columns([2, 1])

            with col1:
                # Get description in current language, fallback to English
                desc = village["description"].get(lang, village["description"]["en"])
                st.markdown(desc)

            with col2:
                # Check for photos first, fall back to SVG illustrations
                village_photos = get_village_photos(village_key)

                if village_photos:
                    st.markdown("### 📸 Village Photos")
                else:
                    st.markdown("### 📸 Scene Illustrations")

                if village_key == "nalu":
                    # Use real photos if available, otherwise use SVG illustrations
                    if village_photos:
                        # Display village scene
                        if "nalu_01_village_scene" in village_photos:
                            st.markdown("**Village Scene**")
                            st.image(str(village_photos["nalu_01_village_scene"]), use_container_width=True)
                            st.caption("Nalu village center")
                            st.markdown("---")

                        # Display rice paddies
                        if "nalu_02_rice_paddies" in village_photos:
                            st.markdown("**Rice Paddies Near Village**")
                            st.image(str(village_photos["nalu_02_rice_paddies"]), use_container_width=True)
                            st.caption("Irrigated rice fields with standing water year-round")
                            st.markdown("---")

                        # Display pig pens
                        if "nalu_03_pig_pens" in village_photos:
                            st.markdown("**Pig Cooperative**")
                            st.image(str(village_photos["nalu_03_pig_pens"]), use_container_width=True)
                            st.caption("~200 pigs housed 500m from village center")
                            st.markdown("---")

                        # Display health center
                        if "nalu_04_health_center_exterior" in village_photos:
                            st.markdown("**Health Center**")
                            st.image(str(village_photos["nalu_04_health_center_exterior"]), use_container_width=True)
                            st.caption("Nalu Health Center - main facility for the area")
                            st.markdown("---")

                        # Display market day
                        if "nalu_05_market_day" in village_photos:
                            st.markdown("**Market Day**")
                            st.image(str(village_photos["nalu_05_market_day"]), use_container_width=True)
                            st.caption("Weekly market brings people together from surrounding villages")
                    else:
                        # Fallback to SVG illustrations
                        st.markdown("**Rice Paddies Near Village**")
                        st.markdown(nalu_rice_svg, unsafe_allow_html=True)
                        st.caption("Irrigated rice fields with standing water year-round")

                        st.markdown("---")
                        st.markdown("**Pig Cooperative**")
                        st.markdown(nalu_pigs_svg, unsafe_allow_html=True)
                        st.caption("~200 pigs housed 500m from village center")

                elif village_key == "kabwe":
                    # Use real photos if available, otherwise use SVG illustrations
                    if village_photos:
                        # Display photos for Kabwe when added
                        # For now, just display any photos found
                        for photo_key, photo_path in village_photos.items():
                            # Create a nice title from the filename
                            title = photo_key.replace("kabwe_", "").replace("_", " ").title()
                            st.markdown(f"**{title}**")
                            st.image(str(photo_path), use_container_width=True)
                            st.markdown("---")
                    else:
                        # Fallback to SVG illustrations
                        st.markdown("**Mixed Farming Area**")
                        st.markdown(kabwe_mixed_svg, unsafe_allow_html=True)
                        st.caption("Combination of rice paddies and upland maize")

                        st.markdown("---")
                        st.markdown("**Path to Nalu School**")
                        st.markdown(kabwe_path_svg, unsafe_allow_html=True)
                        st.caption("Children walk through paddy fields daily")

                elif village_key == "tamu":
                    # Use real photos if available, otherwise use SVG illustrations
                    if village_photos:
                        # Display photos for Tamu when added
                        # For now, just display any photos found
                        for photo_key, photo_path in village_photos.items():
                            # Create a nice title from the filename
                            title = photo_key.replace("tamu_", "").replace("_", " ").title()
                            st.markdown(f"**{title}**")
                            st.image(str(photo_path), use_container_width=True)
                            st.markdown("---")
                    else:
                        # Fallback to SVG illustrations
                        st.markdown("**Upland Terrain**")
                        st.markdown(tamu_upland_svg, unsafe_allow_html=True)
                        st.caption("Higher elevation with cassava and yam farming")

                        st.markdown("---")
                        st.markdown("**Forested Areas**")
                        st.markdown(tamu_forest_svg, unsafe_allow_html=True)
                        st.caption("Spring-fed wells, less standing water")

            # Quick stats summary
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Population", f"{village['population']:,}")
            with col2:
                st.metric("Households", f"{village['households']:,}")
            with col3:
                # Main livelihood
                if village_key == "nalu":
                    st.metric("Main Livelihood", "Rice farming")
                elif village_key == "kabwe":
                    st.metric("Main Livelihood", "Mixed farming")
                else:
                    st.metric("Main Livelihood", "Upland crops")
            with col4:
                # Health facility
                if village_key == "nalu":
                    st.metric("Health Facility", "Health Center")
                elif village_key == "kabwe":
                    st.metric("Health Facility", "None")
                else:
                    st.metric("Health Facility", "CHV only")
