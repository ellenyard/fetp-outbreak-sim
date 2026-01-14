"""Lightweight Day 1 self-check for schema and asset integrity."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import day1_utils


def assert_range(value: int, low: int, high: int, label: str) -> None:
    if not (low <= value <= high):
        raise AssertionError(f"{label} must be between {low} and {high}. Got {value}.")


def check_assets(scenario_id: str) -> None:
    assets = day1_utils.load_day1_assets(scenario_id)
    clinic_entries = assets.get("clinic_log_entries", [])
    case_cards = assets.get("case_cards", [])
    lab_brief = assets.get("lab_brief", {})

    assert_range(len(clinic_entries), 12, 20, f"{scenario_id} clinic log entries")
    assert_range(len(case_cards), 5, 8, f"{scenario_id} case cards")
    if not lab_brief.get("results"):
        raise AssertionError(f"{scenario_id} lab brief results missing")

    for entry in clinic_entries:
        if "entry_id" not in entry or "raw_text" not in entry or "answer_key" not in entry:
            raise AssertionError(f"{scenario_id} clinic entry missing required keys")


def check_templates(scenario_id: str) -> None:
    template_path = Path(f"scenarios/{scenario_id}/content/case_definition_template.md")
    if not template_path.exists():
        raise AssertionError(f"Missing case definition template for {scenario_id}")
    sections = day1_utils.parse_case_definition_template(template_path.read_text())
    if not sections.get("suspected"):
        raise AssertionError(f"{scenario_id} suspected case template missing")


def check_app_views() -> None:
    sys.modules["streamlit"] = MagicMock()
    import app  # noqa: WPS433

    for view_name in [
        "view_clinic_log_abstraction",
        "view_case_finding_debrief",
        "view_day1_lab_brief",
        "view_triangulation_checkpoint",
    ]:
        if not hasattr(app, view_name):
            raise AssertionError(f"App missing {view_name}")


if __name__ == "__main__":
    for scenario in ["aes_sidero_valley", "lepto_rivergate"]:
        check_assets(scenario)
        check_templates(scenario)

    check_app_views()
    print("✓ Day 1 self-check passed")
