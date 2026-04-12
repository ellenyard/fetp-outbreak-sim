"""Scenario detection, content loading, and truth/population initialisation.

Provides helpers to detect scenario type from a data directory path,
load markdown content files, load storyline excerpts, and bootstrap
the truth + full population data used throughout the simulation.
"""

from pathlib import Path
from typing import Optional

import streamlit as st

import outbreak_logic as jl

# Re-export the two core functions used by load_truth_and_population so
# that callers who previously imported them from app.py still work.
load_truth_data = jl.load_truth_data
generate_full_population = jl.generate_full_population
load_scenario_config = jl.load_scenario_config

# ---------------------------------------------------------------------------
# Scenario detection
# ---------------------------------------------------------------------------


def detect_scenario_type(data_dir: str) -> str:
    """Detect scenario type from data directory path.

    Args:
        data_dir: Path to scenario data directory

    Returns:
        Scenario type string: "je" or "lepto"
    """
    data_dir_lower = data_dir.lower()
    if "lepto" in data_dir_lower or "maharlika" in data_dir_lower:
        return "lepto"
    # Default to JE for AES/Sidero Valley or unrecognized scenarios
    return "je"


# ---------------------------------------------------------------------------
# Content / storyline loading
# ---------------------------------------------------------------------------


def load_scenario_content(scenario_id: str, content_type: str) -> str:
    """Load scenario-specific content file.

    Args:
        scenario_id: Scenario identifier (e.g., 'aes_sidero_valley', 'lepto_rivergate')
        content_type: Type of content file to load (e.g., 'alert', 'day1_briefing')

    Returns:
        Content as markdown string, or error message if file not found
    """
    content_path = Path(f"scenarios/{scenario_id}/content/{content_type}.md")
    if content_path.exists():
        return content_path.read_text()
    else:
        return f"\u26a0\ufe0f Content file not found: {content_path}"


def load_storyline_excerpt(scenario_id: str, max_lines: int = 6) -> Optional[str]:
    storyline_path = Path(f"scenarios/{scenario_id}/storyline.md")
    if not storyline_path.exists():
        return None
    lines = [line.strip() for line in storyline_path.read_text().splitlines()]
    excerpt = []
    for line in lines:
        if not line:
            if excerpt:
                break
            continue
        excerpt.append(line)
        if len(excerpt) >= max_lines:
            break
    return "\n".join(excerpt) if excerpt else None


# ---------------------------------------------------------------------------
# Truth data + population generation
# ---------------------------------------------------------------------------


def load_truth_and_population(data_dir: str = ".", scenario_type: str = None):
    """Load truth data and generate a full population.

    Args:
        data_dir: Path to scenario data directory
        scenario_type: Type of outbreak scenario ("je" or "lepto").
                      If None, auto-detected from data_dir path.

    Returns:
        Dictionary containing truth data with generated population.
    """
    # Auto-detect scenario type if not provided
    if scenario_type is None:
        scenario_type = detect_scenario_type(data_dir)

    truth = load_truth_data(data_dir=data_dir)
    villages_df = truth["villages"]
    households_seed = truth["households_seed"]
    individuals_seed = truth["individuals_seed"]

    households_full, individuals_full = generate_full_population(
        villages_df, households_seed, individuals_seed, scenario_type=scenario_type
    )
    truth["households"] = households_full
    truth["individuals"] = individuals_full
    truth["scenario_type"] = scenario_type
    return truth
