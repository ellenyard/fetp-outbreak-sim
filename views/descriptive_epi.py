import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import io
import streamlit.components.v1 as components
from i18n.translate import t
from config.locations import get_current_scenario_id
from data_utils.charts import make_epi_curve, make_village_map, get_initial_cases
from data_utils.case_definition import get_symptomatic_column
import outbreak_logic as jl

apply_case_definition = jl.apply_case_definition


def view_descriptive_epi():
    """Interactive descriptive epidemiology dashboard - trainees must run analyses themselves."""
    st.header("Descriptive Epidemiology - Analysis Workspace")

    st.session_state.descriptive_epi_viewed = True

    truth = st.session_state.truth
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"]
    case_criteria = {
        "scenario_id": st.session_state.get("current_scenario"),
        "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
        "lab_results": st.session_state.lab_results,
    }
    cases = apply_case_definition(individuals, case_criteria).copy()

    # Merge with location info
    hh_vil = households.merge(villages[["village_id", "village_name"]], on="village_id", how="left")
    cases = cases.merge(hh_vil[["hh_id", "village_name", "village_id"]], on="hh_id", how="left")

    st.markdown("""
    Use this workspace to characterize the outbreak by **Person**, **Place**, and **Time**.
    You can run analyses here or download the data to analyze on your computer.
    """)

    st.markdown("---")
    st.markdown("### Day 1 Descriptive Epi Worksheet")
    worksheet_line_list = pd.DataFrame(st.session_state.clinic_line_list) if st.session_state.clinic_line_list else None
    if worksheet_line_list is not None and not worksheet_line_list.empty:
        st.caption("Using cleaned clinic line list from abstraction.")
        st.dataframe(worksheet_line_list, use_container_width=True)
    else:
        st.caption("Using initial line list (overview) because a cleaned clinic line list is not available.")

    with st.expander("Epi curve & map reference", expanded=False):
        st.plotly_chart(make_epi_curve(truth), use_container_width=True)
        st.plotly_chart(make_village_map(truth), use_container_width=True)

    with st.form("day1_worksheet_form"):
        person_obs = st.text_area("Person (age/sex distribution observations)", height=80)
        place_obs = st.text_area("Place (geographic clustering observations)", height=80)
        time_obs = st.text_area("Time (onset trends / epi curve observations)", height=80)
        interpretations = st.text_area("Interpretations (3–5 bullet points)", height=120)
        next_steps = st.text_area("Next-step actions (1–2 items)", height=80)

        if st.form_submit_button("Save Worksheet"):
            st.session_state.day1_worksheet = {
                "person_obs": person_obs.strip(),
                "place_obs": place_obs.strip(),
                "time_obs": time_obs.strip(),
                "interpretations": interpretations.strip(),
                "next_steps": next_steps.strip(),
            }
            st.success("✅ Worksheet saved.")

    if st.session_state.day1_worksheet:
        worksheet_md = (
            "# Day 1 Descriptive Epi Worksheet\n\n"
            f"**Person:**\n{st.session_state.day1_worksheet.get('person_obs', '')}\n\n"
            f"**Place:**\n{st.session_state.day1_worksheet.get('place_obs', '')}\n\n"
            f"**Time:**\n{st.session_state.day1_worksheet.get('time_obs', '')}\n\n"
            f"**Interpretations:**\n{st.session_state.day1_worksheet.get('interpretations', '')}\n\n"
            f"**Next steps:**\n{st.session_state.day1_worksheet.get('next_steps', '')}\n"
        )
        st.download_button(
            "Download Worksheet (Markdown)",
            data=worksheet_md,
            file_name="day1_descriptive_epi_worksheet.md",
            mime="text/markdown",
        )

    # Show case sources if case finding has been done
    if st.session_state.get('found_cases_added', False):
        found_cases_count = cases['found_via_case_finding'].sum() if 'found_via_case_finding' in cases.columns else 0
        initial_cases_count = len(cases) - found_cases_count
        st.info(f"📋 **Line List Sources:** {initial_cases_count} initial reported cases + {int(found_cases_count)} cases identified through active case finding = **{len(cases)} total cases**")

    # Data download section
    st.markdown("### 📥 Download Data")
    col1, col2, col3 = st.columns(3)

    with col1:
        # Prepare download data
        # Build column list dynamically — not all scenarios have the same columns
        download_cols = [c for c in ['person_id', 'age', 'sex', 'village_name', 'onset_date',
                                      'severe_neuro', 'clinical_severity', 'outcome']
                         if c in cases.columns]
        download_df = cases[download_cols].copy()

        # Add outcome display column with sequelae info
        if 'has_sequelae' in cases.columns:
            download_df['outcome'] = cases.apply(
                lambda row: f"{row['outcome']} (with complications)" if row.get('has_sequelae') else row['outcome'],
                axis=1
            )

        # Add case source column
        if 'found_via_case_finding' in cases.columns:
            download_df['case_source'] = cases['found_via_case_finding'].apply(
                lambda x: 'case_finding' if x else 'initial_report'
            )
        else:
            download_df['case_source'] = 'initial_report'
        csv_buffer = io.StringIO()
        download_df.to_csv(csv_buffer, index=False)

        scenario_id = st.session_state.get("current_scenario", "outbreak")
        st.download_button(
            label="📊 Download Line List (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"{scenario_id}_line_list.csv",
            mime="text/csv"
        )

    with col2:
        # Tab-separated download as alternative
        tsv_buffer = io.StringIO()
        download_df.to_csv(tsv_buffer, index=False, sep='\t')

        st.download_button(
            label="📊 Download Line List (TSV)",
            data=tsv_buffer.getvalue(),
            file_name=f"{scenario_id}_line_list.tsv",
            mime="text/tab-separated-values"
        )

    with col3:
        st.metric("Total Records", len(cases))

    st.markdown("---")

    # Interactive Analysis Section
    st.markdown("### Run Analyses")
    st.caption("Select the analyses you want to perform. Results will appear below.")

    col1, col2 = st.columns(2)

    with col1:
        run_person = st.checkbox("Person characteristics (age, sex, outcomes)")
        run_place = st.checkbox("Place analysis (cases by village, attack rates)")

    with col2:
        run_time = st.checkbox("Time analysis (epidemic curve)")
        run_crosstab = st.checkbox("Custom cross-tabulation")

    st.markdown("---")

    # PERSON ANALYSIS
    if run_person:
        st.markdown("## Person Analysis")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Age Distribution")

            # Let them choose how to display age
            age_display = st.radio(
                "How to display age?",
                ["Histogram (continuous)", "Age groups (categorical)"],
                key="age_display"
            )

            if age_display == "Histogram (continuous)":
                bin_width = st.slider("Bin width (years)", 1, 10, 5)
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=cases['age'],
                    xbins=dict(size=bin_width),
                    marker_color='#3498db'
                ))
                fig.update_layout(
                    xaxis_title="Age (years)",
                    yaxis_title="Number of cases",
                    height=300,
                    margin=dict(l=10, r=10, t=10, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)

                # Stats
                st.markdown(f"**Mean age:** {cases['age'].mean():.1f} years")
                st.markdown(f"**Median age:** {cases['age'].median():.0f} years")
                st.markdown(f"**Range:** {cases['age'].min()} - {cases['age'].max()} years")
            else:
                # Let them define age groups
                st.markdown("Define age groups:")
                age_cuts = st.text_input("Age breaks (comma-separated)", "0,5,10,15,20,50,100")
                try:
                    bins = [int(x.strip()) for x in age_cuts.split(",")]
                    labels = [f"{bins[i]}-{bins[i+1]-1}" for i in range(len(bins)-1)]
                    cases['age_group'] = pd.cut(cases['age'], bins=bins, labels=labels, right=False)

                    age_table = cases['age_group'].value_counts().sort_index()
                    age_df = pd.DataFrame({
                        'Age Group': age_table.index,
                        'Cases (n)': age_table.values,
                        'Percent (%)': (age_table.values / len(cases) * 100).round(1)
                    })
                    st.dataframe(age_df, hide_index=True)
                except (ValueError, TypeError, KeyError) as e:
                    st.error(f"Invalid age breaks. Use comma-separated numbers like: 0,5,15,50,100 (Error: {str(e)})")

        with col2:
            st.markdown("### Sex Distribution")

            sex_counts = cases['sex'].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=sex_counts.index,
                values=sex_counts.values,
                marker_colors=['#3498db', '#e74c3c']
            )])
            fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

            sex_df = pd.DataFrame({
                'Sex': sex_counts.index,
                'Cases (n)': sex_counts.values,
                'Percent (%)': (sex_counts.values / len(cases) * 100).round(1)
            })
            st.dataframe(sex_df, hide_index=True)

            st.markdown("### Outcomes")
            outcome_counts = cases['outcome'].value_counts()
            outcome_df = pd.DataFrame({
                'Outcome': outcome_counts.index,
                'Cases (n)': outcome_counts.values,
                'Percent (%)': (outcome_counts.values / len(cases) * 100).round(1)
            })
            st.dataframe(outcome_df, hide_index=True)

    # PLACE ANALYSIS
    if run_place:
        st.markdown("## Place Analysis")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Cases by Village")

            village_counts = cases['village_name'].value_counts()

            fig = go.Figure(data=[go.Bar(
                x=village_counts.index,
                y=village_counts.values,
                marker_color=['#e74c3c', '#f39c12', '#27ae60'][:len(village_counts)]
            )])
            fig.update_layout(
                xaxis_title="Village",
                yaxis_title="Number of cases",
                height=300,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### Attack Rates")
            st.caption("Enter population to calculate attack rate")

            # Let them enter populations or use defaults
            village_pops = {}
            for village in village_counts.index:
                default_pop = villages[villages['village_name'] == village]['population_size'].values
                default_pop = default_pop[0] if len(default_pop) > 0 else 1000
                village_pops[village] = st.number_input(
                    f"Population of {village}",
                    min_value=100,
                    value=int(default_pop),
                    key=f"pop_{village}"
                )

            if st.button("Calculate Attack Rates"):
                attack_rates = []
                for village in village_counts.index:
                    cases_n = village_counts[village]
                    pop = village_pops[village]
                    ar = cases_n / pop * 1000
                    attack_rates.append({
                        'Village': village,
                        'Cases': cases_n,
                        'Population': pop,
                        'AR (per 1,000)': round(ar, 1)
                    })

                ar_df = pd.DataFrame(attack_rates)
                st.dataframe(ar_df, hide_index=True)

    # TIME ANALYSIS
    if run_time:
        st.markdown("## Time Analysis - Epidemic Curve")

        if 'onset_date' in cases.columns:
            # Let them choose interval
            interval = st.selectbox(
                "Time interval for epi curve:",
                ["Day", "Week"],
                key="epi_interval"
            )

            if interval == "Day":
                counts = cases.groupby('onset_date').size().reset_index(name='cases')
            else:
                cases['week'] = pd.to_datetime(cases['onset_date']).dt.isocalendar().week
                counts = cases.groupby('week').size().reset_index(name='cases')
                counts = counts.rename(columns={'week': 'onset_date'})

            counts = counts.sort_values('onset_date')

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=counts['onset_date'],
                y=counts['cases'],
                marker_color='#e74c3c',
                width=0.9  # Make bars touch (histogram style)
            ))
            fig.update_layout(
                xaxis_title="Onset Date" if interval == "Day" else "Week",
                yaxis_title="Number of Cases",
                height=350,
                margin=dict(l=10, r=10, t=10, b=10),
                bargap=0  # No gap between bars (histogram style)
            )
            st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Summary:**")
                st.markdown(f"- First case: {cases['onset_date'].min()}")
                st.markdown(f"- Last case: {cases['onset_date'].max()}")
                st.markdown(f"- Peak: {counts.loc[counts['cases'].idxmax(), 'onset_date']}")
            with col2:
                st.markdown("**Interpretation questions:**")
                st.markdown("- What type of curve is this?")
                st.markdown("- Is the outbreak ongoing?")

    # CUSTOM CROSSTAB
    if run_crosstab:
        st.markdown("## Custom Cross-tabulation")

        # Build variable list dynamically based on what columns exist in the data
        available_vars = ['age_group', 'sex', 'village_name']
        if 'severe_neuro' in cases.columns:
            available_vars.append('severe_neuro')
        if 'clinical_severity' in cases.columns:
            available_vars.append('clinical_severity')
        available_vars.append('outcome')

        col1, col2 = st.columns(2)
        with col1:
            row_var = st.selectbox("Row variable:", available_vars, key="row_var")
        with col2:
            col_var = st.selectbox("Column variable:", [v for v in available_vars if v != row_var], key="col_var")

        if st.button("Generate Cross-tabulation"):
            # Make sure age_group exists
            if row_var == 'age_group' or col_var == 'age_group':
                bins = [0, 5, 10, 15, 20, 50, 100]
                labels = ['0-4', '5-9', '10-14', '15-19', '20-49', '50+']
                cases['age_group'] = pd.cut(cases['age'], bins=bins, labels=labels, right=False)

            crosstab = pd.crosstab(cases[row_var], cases[col_var], margins=True, margins_name='Total')
            st.dataframe(crosstab)

    st.markdown("---")

    # Interpretation prompts
    with st.expander("🤔 Descriptive Epi Interpretation Questions"):
        st.markdown("""
        **Person:**
        - What age groups are most affected? What does this suggest?
        - Is there a sex difference? If so, what might explain it?

        **Place:**
        - Which villages have the highest attack rates?
        - What do the affected villages have in common?
        - What might explain the geographic pattern?

        **Time:**
        - What type of epidemic curve does this look like?
        - What does the timing suggest about the incubation period?
        - Is the outbreak ongoing or resolving?

        **Synthesis:**
        - Based on person, place, and time, what hypotheses can you generate?
        - What additional information would help narrow down the cause?
        """)


def view_spot_map():
    """Geographic spot map of cases using a custom fictional map."""
    st.header("Spot Map - Geographic Distribution of Cases")

    truth = st.session_state.truth
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"]

    case_criteria = {
        "scenario_id": st.session_state.get("current_scenario"),
        "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
        "lab_results": st.session_state.lab_results,
    }
    cases = apply_case_definition(individuals, case_criteria).copy()

    # Also include found cases from clinic records if any
    found_cases_count = 0
    if st.session_state.get('found_cases_added') and st.session_state.case_finding_score:
        found_cases_count = st.session_state.case_finding_score.get('true_positives', 0)

    if len(cases) == 0:
        st.warning("No cases to display on map.")
        return

    # Merge with household info
    hh_with_village = households.merge(
        villages[["village_id", "village_name"]],
        on="village_id",
        how="left"
    )

    cases = cases.merge(
        hh_with_village[["hh_id", "village_id", "village_name"]],
        on="hh_id",
        how="left",
        suffixes=('', '_hh')
    )

    if 'village_id_hh' in cases.columns:
        cases['village_id'] = cases['village_id_hh']
        cases = cases.drop(columns=['village_id_hh'])

    # Count cases by village
    village_counts = cases['village_name'].value_counts().to_dict()
    scenario_type = st.session_state.truth.get("scenario_type")
    if scenario_type == "lepto":
        st.markdown("### Village-level case counts")
        summary = pd.DataFrame(
            [{"village": k, "cases": v} for k, v in village_counts.items()]
        ).sort_values("cases", ascending=False)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        fig = px.scatter(
            villages,
            x="longitude",
            y="latitude",
            size=villages["village_id"].map(village_counts).fillna(0),
            color=villages["village_id"].map(village_counts).fillna(0),
            hover_name="village_name",
            title="Spot map (cases by village)",
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    nalu_cases = village_counts.get('Nalu Village', 0)
    kabwe_cases = village_counts.get('Kabwe Village', 0)
    tamu_cases = village_counts.get('Tamu Village', 0)

    # Generate case dots for SVG
    np.random.seed(42)

    def generate_case_dots(n_cases, cx, cy, radius=25):
        """Generate SVG circles for cases clustered around a point."""
        dots = []
        for i in range(n_cases):
            # Random position within radius
            angle = np.random.uniform(0, 2 * np.pi)
            r = np.random.uniform(5, radius)
            x = cx + r * np.cos(angle)
            y = cy + r * np.sin(angle)
            # Determine severity color
            is_severe = np.random.random() < 0.3
            color = '#e74c3c' if is_severe else '#f39c12'
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="white" stroke-width="1"/>')
        return '\n'.join(dots)

    # Generate dots for each village
    nalu_dots = generate_case_dots(nalu_cases, 200, 280, 30)
    kabwe_dots = generate_case_dots(kabwe_cases, 340, 200, 25)
    tamu_dots = generate_case_dots(tamu_cases, 120, 120, 20)

    # Custom SVG map (JE/Sidero Valley fallback when lat/lon not available)
    svg_setting = st.session_state.get('scenario_config', {}).get('setting_name', 'Investigation Area')
    map_svg = f'''
    <svg viewBox="0 0 500 400" xmlns="http://www.w3.org/2000/svg" style="background: #f0f8ff;">
        <!-- Title -->
        <text x="250" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">{svg_setting} - Case Distribution Map</text>

        <!-- River -->
        <path d="M 50,350 Q 150,300 200,280 Q 250,260 300,250 Q 350,240 400,200 Q 450,160 480,100"
              stroke="#4a90d9" stroke-width="12" fill="none" opacity="0.7"/>
        <path d="M 50,350 Q 150,300 200,280 Q 250,260 300,250 Q 350,240 400,200 Q 450,160 480,100"
              stroke="#6ab0ff" stroke-width="6" fill="none"/>
        <text x="420" y="130" font-size="10" fill="#4a90d9" font-style="italic">Sidero River</text>

        <!-- Rice Paddies (near Nalu and Kabwe) -->
        <rect x="140" y="240" width="80" height="60" fill="#7cb342" opacity="0.5" rx="5"/>
        <rect x="230" y="220" width="60" height="50" fill="#7cb342" opacity="0.5" rx="5"/>
        <rect x="280" y="180" width="50" height="40" fill="#7cb342" opacity="0.4" rx="5"/>
        <text x="180" y="235" font-size="8" fill="#33691e">Rice Paddies</text>

        <!-- Pig Farm marker near Nalu -->
        <rect x="160" y="310" width="30" height="20" fill="#8d6e63" opacity="0.7" rx="3"/>
        <text x="175" y="323" font-size="7" fill="white" text-anchor="middle">🐷</text>
        <text x="175" y="340" font-size="7" fill="#5d4037" text-anchor="middle">Pig Coop</text>

        <!-- Upland/Forest area (near Tamu) -->
        <ellipse cx="100" cy="100" rx="60" ry="50" fill="#2e7d32" opacity="0.3"/>
        <text x="100" y="70" font-size="8" fill="#1b5e20" text-anchor="middle">Forested Uplands</text>

        <!-- VILLAGES -->

        <!-- Nalu Village (largest, near river and paddies) -->
        <circle cx="200" cy="280" r="35" fill="#ffcc80" stroke="#e65100" stroke-width="2"/>
        <text x="200" y="275" text-anchor="middle" font-size="11" font-weight="bold" fill="#e65100">Nalu</text>
        <text x="200" y="288" text-anchor="middle" font-size="8" fill="#bf360c">Pop: 480</text>

        <!-- Kabwe Village (medium, between Nalu and uplands) -->
        <circle cx="340" cy="200" r="28" fill="#ffe0b2" stroke="#ff6f00" stroke-width="2"/>
        <text x="340" y="196" text-anchor="middle" font-size="10" font-weight="bold" fill="#ff6f00">Kabwe</text>
        <text x="340" y="208" text-anchor="middle" font-size="7" fill="#e65100">Pop: 510</text>

        <!-- Tamu Village (smallest, in uplands away from paddies) -->
        <circle cx="120" cy="120" r="22" fill="#fff3e0" stroke="#ff9800" stroke-width="2"/>
        <text x="120" y="117" text-anchor="middle" font-size="9" font-weight="bold" fill="#ff9800">Tamu</text>
        <text x="120" y="128" text-anchor="middle" font-size="7" fill="#e65100">Pop: 390</text>

        <!-- Path from Kabwe to Nalu (through paddies) -->
        <path d="M 315,210 Q 280,240 230,265" stroke="#a1887f" stroke-width="3" fill="none" stroke-dasharray="5,3"/>
        <text x="270" y="250" font-size="7" fill="#6d4c41" transform="rotate(-20 270 250)">path to school</text>

        <!-- District Hospital -->
        <rect x="420" y="300" width="40" height="30" fill="#e3f2fd" stroke="#1976d2" stroke-width="2" rx="3"/>
        <text x="440" y="315" text-anchor="middle" font-size="8" fill="#1976d2">🏥</text>
        <text x="440" y="325" text-anchor="middle" font-size="6" fill="#1565c0">Hospital</text>
        <text x="440" y="340" font-size="6" fill="#666" text-anchor="middle">12 km →</text>

        <!-- CASE DOTS -->
        {nalu_dots}
        {kabwe_dots}
        {tamu_dots}

        <!-- Legend -->
        <rect x="10" y="350" width="150" height="45" fill="white" stroke="#ccc" rx="5"/>
        <text x="20" y="365" font-size="9" font-weight="bold">Legend</text>
        <circle cx="25" cy="378" r="4" fill="#e74c3c"/>
        <text x="35" y="381" font-size="8">Severe case</text>
        <circle cx="90" cy="378" r="4" fill="#f39c12"/>
        <text x="100" y="381" font-size="8">Mild case</text>
        <rect x="20" y="386" width="10" height="6" fill="#7cb342" opacity="0.5"/>
        <text x="35" y="392" font-size="7">Rice paddies</text>

        <!-- Scale -->
        <line x1="380" y="380" x2="430" y2="380" stroke="#333" stroke-width="2"/>
        <text x="405" y="375" font-size="7" text-anchor="middle">~1 km</text>

        <!-- Compass -->
        <text x="460" y="60" font-size="12" text-anchor="middle">↑ N</text>
    </svg>
    '''

    # Use components.html for reliable SVG rendering
    components.html(map_svg, height=450)

    # Summary statistics
    st.markdown("---")
    st.markdown("#### Geographic Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Nalu Village", f"{nalu_cases} cases")

    with col2:
        st.metric("Kabwe Village", f"{kabwe_cases} cases")

    with col3:
        st.metric("Tamu Village", f"{tamu_cases} cases")

    if found_cases_count > 0:
        st.info(f"📋 Note: {found_cases_count} additional case(s) identified through clinic record review have been included in the case counts.")

    # Interpretation prompts
    with st.expander("🤔 Spot Map Interpretation Questions"):
        st.markdown("""
        Consider these questions as you review the geographic distribution:

        1. **Clustering:** Do cases cluster in specific areas? What might explain this?
        2. **Village comparison:** Why might some villages have more cases than others?
        3. **Environmental features:** What is located near the case clusters?
        4. **Hypothesis generation:** What geographic exposures might explain this pattern?
        """)
