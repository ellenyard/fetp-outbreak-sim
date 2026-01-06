#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from outbreak_logic import load_truth_data, generate_full_population


LEPTO_REQUIRED_HOUSEHOLD_COLUMNS = [
    "hh_id",
    "village_id",
    "household_size",
    "sanitation_type",
    "water_source",
    "flood_depth_category",
    "cleanup_participation",
    "rat_sightings_post_flood",
    "distance_to_river_m",
    "pig_ownership",
    "chicken_ownership",
]

LEPTO_REQUIRED_INDIVIDUAL_COLUMNS = [
    "person_id",
    "hh_id",
    "village_id",
    "age",
    "sex",
    "occupation",
    "symptoms_fever",
    "symptoms_headache",
    "symptoms_myalgia",
    "symptoms_conjunctival_suffusion",
    "symptoms_jaundice",
    "symptoms_renal_failure",
    "outcome",
    "days_to_hospital",
    "exposure_cleanup_work",
    "exposure_barefoot_water",
    "exposure_skin_wounds",
    "exposure_animal_contact",
    "exposure_rat_contact",
    "reported_to_hospital",
    "clinical_severity",
    "onset_date",
]


def validate_population(households_df, individuals_df, village_ids):
    issues = []

    missing_household_cols = [c for c in LEPTO_REQUIRED_HOUSEHOLD_COLUMNS if c not in households_df.columns]
    if missing_household_cols:
        issues.append(f"missing_household_columns:{','.join(missing_household_cols)}")

    missing_individual_cols = [c for c in LEPTO_REQUIRED_INDIVIDUAL_COLUMNS if c not in individuals_df.columns]
    if missing_individual_cols:
        issues.append(f"missing_individual_columns:{','.join(missing_individual_cols)}")

    if households_df["village_id"].nunique() < len(village_ids):
        issues.append("missing_villages_in_households")

    if individuals_df["village_id"].nunique() < len(village_ids):
        issues.append("missing_villages_in_individuals")

    symptomatic = individuals_df[individuals_df.get("symptomatic_lepto", False)]
    if symptomatic.empty:
        issues.append("no_symptomatic_lepto_cases")
    else:
        missing_onset = symptomatic["onset_date"].isna().sum()
        if missing_onset:
            issues.append(f"symptomatic_missing_onset_dates:{missing_onset}")

    v4_symptomatic = symptomatic[symptomatic["village_id"] == "V4"]
    if not v4_symptomatic.empty:
        issues.append(f"unexpected_v4_symptomatic_cases:{len(v4_symptomatic)}")

    return issues


def summarize_cases(individuals_df):
    symptomatic = individuals_df[individuals_df.get("symptomatic_lepto", False)]
    severe = symptomatic[symptomatic.get("severe_lepto", False)]
    summary = {
        "symptomatic_total": int(symptomatic.shape[0]),
        "severe_total": int(severe.shape[0]),
        "symptomatic_by_village": symptomatic["village_id"].value_counts().to_dict(),
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Batch run the Leptospirosis scenario.")
    parser.add_argument("--data-dir", default="scenarios/lepto_rivergate/data", help="Scenario data directory.")
    parser.add_argument("--runs", type=int, default=100, help="Number of simulation runs.")
    parser.add_argument("--seed", type=int, default=42, help="Seed offset for reproducibility.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    truth = load_truth_data(args.data_dir)
    villages_df = truth["villages"]
    village_ids = set(villages_df["village_id"].tolist())

    issue_counter = Counter()
    summaries = []

    for i in range(args.runs):
        seed = args.seed + i
        np.random.seed(seed)
        households_df, individuals_df = generate_full_population(
            villages_df=truth["villages"],
            households_seed=truth["households_seed"],
            individuals_seed=truth["individuals_seed"],
            random_seed=seed,
            scenario_type="lepto",
        )

        issues = validate_population(households_df, individuals_df, village_ids)
        issue_counter.update(issues)
        summaries.append(summarize_cases(individuals_df))

    totals = defaultdict(int)
    for summary in summaries:
        totals["symptomatic_total"] += summary["symptomatic_total"]
        totals["severe_total"] += summary["severe_total"]

    output_payload = {
        "runs": args.runs,
        "issues": dict(issue_counter),
        "average_symptomatic": totals["symptomatic_total"] / max(args.runs, 1),
        "average_severe": totals["severe_total"] / max(args.runs, 1),
    }

    if args.output:
        args.output.write_text(json.dumps(output_payload, indent=2))
    else:
        print(json.dumps(output_payload, indent=2))


if __name__ == "__main__":
    main()
