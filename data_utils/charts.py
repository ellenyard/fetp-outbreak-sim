"""Chart and visualization utilities for outbreak simulation.

Provides functions to generate village maps, initial case line lists,
and epidemiologic curves using Plotly.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from outbreak_logic import apply_case_definition


def _scenario_config_label(scenario_type: str) -> str:
    """Return the disease display name from the active scenario config."""
    scenario_config = st.session_state.get("scenario_config", {}) or {}
    return scenario_config.get("disease_name", "Case")


def make_village_map(truth: dict) -> go.Figure:
    """Simple schematic map of villages with exposure indicators."""
    villages = truth["villages"].copy()
    scenario_type = truth.get("scenario_type", "je")
    # Assign simple coordinates for display
    villages = villages.reset_index(drop=True)
    villages["x"] = np.arange(len(villages))
    villages["y"] = 0

    # Marker size from population
    size = 20 + 5 * (villages["population_size"] / villages["population_size"].max())

    fig = go.Figure()

    if scenario_type == "lepto":
        color_map = {"very_high": "#d73027", "high": "#fc8d59", "medium": "#fee08b", "low": "#91bfdb"}
        symbol_map = {"very_high": "diamond", "high": "square", "medium": "circle", "low": "triangle-up", "minimal": "x"}
        for risk_level, group in villages.groupby("flood_risk"):
            fig.add_trace(
                go.Scatter(
                    x=group["x"],
                    y=group["y"],
                    mode="markers+text",
                    text=group["village_name"],
                    textposition="top center",
                    marker=dict(
                        size=size.loc[group.index],
                        color=color_map.get(str(risk_level).lower(), "gray"),
                        symbol=[symbol_map.get(str(val).lower(), "circle") for val in group["cleanup_intensity"]],
                        line=dict(color="black", width=1),
                    ),
                    name=f"Flood risk: {risk_level}",
                    hovertext=[
                        (
                            f"{row['village_name']}"
                            f"<br>Flood risk: {row['flood_risk']}"
                            f"<br>Flood depth (m): {row['flood_depth_m']}"
                            f"<br>Cleanup intensity: {row['cleanup_intensity']}"
                            f"<br>Rat population: {row['rat_population']}"
                        )
                        for _, row in group.iterrows()
                    ],
                    hoverinfo="text",
                )
            )
        for cleanup_level, symbol in symbol_map.items():
            if cleanup_level in villages["cleanup_intensity"].astype(str).str.lower().unique():
                fig.add_trace(
                    go.Scatter(
                        x=[None],
                        y=[None],
                        mode="markers",
                        marker=dict(size=12, symbol=symbol, color="#8c8c8c", line=dict(color="black", width=1)),
                        name=f"Cleanup: {cleanup_level}",
                        legendgroup="cleanup",
                        showlegend=True,
                    )
                )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            title="Schematic Map of Rivergate Flooding & Cleanup Exposure",
            legend_title_text="Flood risk (color) & Cleanup intensity (symbol)",
            height=300,
            margin=dict(l=10, r=10, t=40, b=10),
        )
    else:
        # Marker size from population, color from pig_density
        color_map = {"high": "red", "medium": "orange", "low": "yellow", "none": "green"}
        colors = [color_map.get(str(d).lower(), "gray") for d in villages["pig_density"]]
        fig.add_trace(
            go.Scatter(
                x=villages["x"],
                y=villages["y"],
                mode="markers+text",
                text=villages["village_name"],
                textposition="top center",
                marker=dict(size=size, color=colors, line=dict(color="black", width=1)),
                hovertext=[
                    f"{row['village_name']}<br>Pigs: {row['pig_density']}<br>Rice paddies: {row['has_rice_paddies']}"
                    for _, row in villages.iterrows()
                ],
                hoverinfo="text",
            )
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            title="Schematic Map of Sidero Valley",
            showlegend=False,
            height=300,
            margin=dict(l=10, r=10, t=40, b=10),
        )
    return fig


def get_initial_cases(truth: dict, n: int = 12) -> pd.DataFrame:
    """Return a small line list of earliest symptomatic cases."""
    individuals = truth["individuals"]
    households = truth["households"]
    villages = truth["villages"][["village_id", "village_name"]]
    case_criteria = {
        "scenario_id": st.session_state.get("current_scenario"),
        "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
        "lab_results": st.session_state.lab_results,
    }

    hh_vil = households.merge(villages, on="village_id", how="left")
    merged = individuals.merge(
        hh_vil[["hh_id", "village_name"]], on="hh_id", how="left"
    )

    cases = apply_case_definition(merged, case_criteria).copy()
    if "onset_date" in cases.columns:
        cases = cases.sort_values("onset_date")

    # Create display column for outcome that includes sequelae info
    if 'has_sequelae' in cases.columns:
        cases['outcome_display'] = cases.apply(
            lambda row: f"{row['outcome']} (with complications)" if row.get('has_sequelae') else row['outcome'],
            axis=1
        )
    else:
        cases['outcome_display'] = cases['outcome']

    return cases.head(n)[
        ["person_id", "age", "sex", "village_name", "onset_date", "severe_neuro", "outcome_display"]
    ].rename(columns={'outcome_display': 'outcome'})


def make_epi_curve(truth: dict) -> go.Figure:
    """Epi curve of cases by onset date."""
    individuals = truth["individuals"]
    scenario_type = truth.get("scenario_type")
    case_label = _scenario_config_label(scenario_type)
    case_criteria = {
        "scenario_id": st.session_state.get("current_scenario"),
        "case_definition_structured": st.session_state.decisions.get("case_definition_structured"),
        "lab_results": st.session_state.lab_results,
    }
    cases = apply_case_definition(individuals, case_criteria).copy()
    if "onset_date" not in cases.columns:
        fig = go.Figure()
        fig.update_layout(title="Epi curve not available")
        return fig

    counts = cases.groupby("onset_date").size().reset_index(name="cases")
    counts = counts.sort_values("onset_date")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=counts["onset_date"],
            y=counts["cases"],
            marker_color='#e74c3c',
            width=0.9  # Make bars touch (histogram style)
        )
    )
    fig.update_layout(
        title=f"{case_label} cases by onset date",
        xaxis_title="Onset date",
        yaxis_title="Number of cases",
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
        bargap=0  # No gap between bars (histogram style)
    )
    return fig
