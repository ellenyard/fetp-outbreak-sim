"""Quick analysis workspace for Day 3+.

Provides lightweight in-app epidemiological analysis tools:
- Frequency tables and variable exploration
- Cross-tabulation (exposure x outcome)
- 2x2 table with OR, RR, and 95% CI calculators
- Epi curve visualization
- Export to EpiKit for deeper analysis
"""

import math

import pandas as pd
import plotly.express as px
import streamlit as st

from config.locations import get_current_scenario_id
from i18n.translate import t


# ---------------------------------------------------------------------------
# Statistical helpers (no scipy needed)
# ---------------------------------------------------------------------------

def _frequency_table(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Frequency + percentage for a categorical variable."""
    counts = df[column].value_counts(dropna=False)
    pcts = df[column].value_counts(normalize=True, dropna=False) * 100
    return pd.DataFrame({"Count": counts, "Percent": pcts.round(1)})


def _cross_tabulation(df: pd.DataFrame, exposure_col: str, outcome_col: str) -> pd.DataFrame:
    """2x2 cross-tabulation with row/column totals."""
    ct = pd.crosstab(df[exposure_col], df[outcome_col], margins=True, margins_name="Total")
    return ct


def _odds_ratio(a: int, b: int, c: int, d: int) -> dict:
    """Calculate odds ratio with 95% CI (Woolf logit method).

    2x2 table:
        |          | Disease+ | Disease- |
        | Exposed+ |    a     |    b     |
        | Exposed- |    c     |    d     |
    """
    if 0 in (a, b, c, d):
        # Add 0.5 continuity correction
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5

    or_val = (a * d) / (b * c)
    se_ln = math.sqrt(1/a + 1/b + 1/c + 1/d)
    ci_lower = math.exp(math.log(or_val) - 1.96 * se_ln)
    ci_upper = math.exp(math.log(or_val) + 1.96 * se_ln)

    return {
        "or": round(or_val, 2),
        "ci_lower": round(ci_lower, 2),
        "ci_upper": round(ci_upper, 2),
    }


def _relative_risk(a: int, b: int, c: int, d: int) -> dict:
    """Calculate relative risk with 95% CI.

    RR = (a/(a+b)) / (c/(c+d))
    """
    n1 = a + b
    n0 = c + d

    if n1 == 0 or n0 == 0 or c == 0:
        return {"rr": None, "ci_lower": None, "ci_upper": None}

    p1 = a / n1
    p0 = c / n0

    if p0 == 0:
        return {"rr": None, "ci_lower": None, "ci_upper": None}

    rr = p1 / p0

    # Log-method CI
    se_ln = math.sqrt((1 - p1) / (a if a > 0 else 0.5) + (1 - p0) / (c if c > 0 else 0.5))
    ci_lower = math.exp(math.log(rr) - 1.96 * se_ln) if rr > 0 else 0
    ci_upper = math.exp(math.log(rr) + 1.96 * se_ln) if rr > 0 else 0

    return {
        "rr": round(rr, 2),
        "ci_lower": round(ci_lower, 2),
        "ci_upper": round(ci_upper, 2),
    }


def _attack_rate(cases: int, total: int) -> float:
    """Attack rate as percentage."""
    if total == 0:
        return 0.0
    return round(100 * cases / total, 1)


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------

def view_quick_analysis():
    """Quick analysis workspace with frequency tables, cross-tabs, and measures of association."""
    st.header("Quick Analysis Workspace")

    dataset = st.session_state.get("generated_dataset")
    if dataset is None:
        st.warning("No dataset available yet. Generate a dataset on the Data & Study Design page first (Day 2).")
        if st.button("Go to Study Design"):
            st.session_state.current_view = "study"
            st.rerun()
        return

    df = dataset if isinstance(dataset, pd.DataFrame) else pd.DataFrame(dataset)
    st.caption(f"Dataset: {len(df)} records, {len(df.columns)} variables")

    # EpiKit export
    st.markdown("---")
    col_export1, col_export2 = st.columns([2, 3])
    with col_export1:
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download dataset as CSV",
            data=csv_data,
            file_name="outbreak_dataset.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_export2:
        st.markdown(
            "For deeper analysis (stratified tables, spot maps, epi curve annotations), "
            "import this CSV into [EpiKit](https://ellenyard.github.io/epikit/)."
        )

    st.markdown("---")

    # Three analysis tabs
    tab1, tab2, tab3 = st.tabs(["Describe Cases", "Compare Exposures", "Measures of Association"])

    with tab1:
        _tab_describe(df)

    with tab2:
        _tab_crosstab(df)

    with tab3:
        _tab_measures(df)


def _tab_describe(df: pd.DataFrame):
    """Descriptive analysis: frequency tables and epi curve."""
    st.subheader("Variable Explorer")

    # Select variable
    cols = [c for c in df.columns if df[c].nunique() < 50]
    if not cols:
        cols = list(df.columns)

    selected = st.selectbox("Select variable to explore:", cols, key="describe_var")

    if selected:
        freq = _frequency_table(df, selected)
        st.dataframe(freq, use_container_width=True)

    # Epi curve
    date_cols = [c for c in df.columns if "date" in c.lower() or "onset" in c.lower()]
    if date_cols:
        st.subheader("Epidemic Curve")
        date_col = st.selectbox("Date variable:", date_cols, key="epi_curve_date")
        if date_col:
            date_series = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not date_series.empty:
                fig = px.histogram(
                    x=date_series,
                    nbins=max(10, len(date_series.unique())),
                    labels={"x": "Onset Date", "y": "Number of Cases"},
                    title="Epidemic Curve",
                )
                fig.update_layout(bargap=0.1)
                st.plotly_chart(fig, use_container_width=True)


def _tab_crosstab(df: pd.DataFrame):
    """Cross-tabulation builder."""
    st.subheader("Cross-Tabulation")
    st.caption("Compare exposure variables against outcome to identify potential risk factors.")

    categorical_cols = [c for c in df.columns if df[c].nunique() < 20]
    if len(categorical_cols) < 2:
        st.warning("Not enough categorical variables for cross-tabulation.")
        return

    col1, col2 = st.columns(2)
    with col1:
        exposure = st.selectbox("Exposure variable:", categorical_cols, key="xtab_exposure")
    with col2:
        outcome_options = [c for c in categorical_cols if c != exposure]
        outcome = st.selectbox("Outcome variable:", outcome_options, key="xtab_outcome")

    if exposure and outcome:
        ct = _cross_tabulation(df, exposure, outcome)
        st.dataframe(ct, use_container_width=True)

        # Attack rates if outcome is binary
        if df[outcome].nunique() == 2:
            st.subheader("Attack Rates")
            outcome_vals = sorted(df[outcome].unique())
            positive_val = outcome_vals[-1]  # assume higher value is positive
            for group in df[exposure].unique():
                subset = df[df[exposure] == group]
                cases = (subset[outcome] == positive_val).sum()
                total = len(subset)
                ar = _attack_rate(cases, total)
                st.metric(f"Attack rate: {exposure}={group}", f"{ar}%", f"{cases}/{total}")


def _tab_measures(df: pd.DataFrame):
    """2x2 table and measures of association."""
    st.subheader("2x2 Table & Measures of Association")

    st.markdown("""
    Enter values from your cross-tabulation, or use the auto-fill from your dataset.
    """)

    # Auto-fill option
    categorical_cols = [c for c in df.columns if df[c].nunique() == 2]
    if len(categorical_cols) >= 2:
        with st.expander("Auto-fill from dataset"):
            af_col1, af_col2 = st.columns(2)
            with af_col1:
                af_exposure = st.selectbox("Exposure:", categorical_cols, key="af_exp")
            with af_col2:
                af_outcome_options = [c for c in categorical_cols if c != af_exposure]
                af_outcome = st.selectbox("Outcome:", af_outcome_options, key="af_out")

            if st.button("Auto-fill 2x2 table"):
                exp_vals = sorted(df[af_exposure].unique())
                out_vals = sorted(df[af_outcome].unique())
                exp_pos, exp_neg = exp_vals[-1], exp_vals[0]
                out_pos, out_neg = out_vals[-1], out_vals[0]

                st.session_state["cell_a"] = int(((df[af_exposure] == exp_pos) & (df[af_outcome] == out_pos)).sum())
                st.session_state["cell_b"] = int(((df[af_exposure] == exp_pos) & (df[af_outcome] == out_neg)).sum())
                st.session_state["cell_c"] = int(((df[af_exposure] == exp_neg) & (df[af_outcome] == out_pos)).sum())
                st.session_state["cell_d"] = int(((df[af_exposure] == exp_neg) & (df[af_outcome] == out_neg)).sum())
                st.rerun()

    # 2x2 input
    st.markdown("#### 2x2 Table")
    st.markdown("|  | Disease+ | Disease- |")
    st.markdown("|--|----------|----------|")

    col1, col2 = st.columns(2)
    with col1:
        a = st.number_input("Exposed + Disease (a)", min_value=0, value=st.session_state.get("cell_a", 0), key="input_a")
        c = st.number_input("Unexposed + Disease (c)", min_value=0, value=st.session_state.get("cell_c", 0), key="input_c")
    with col2:
        b = st.number_input("Exposed + No Disease (b)", min_value=0, value=st.session_state.get("cell_b", 0), key="input_b")
        d = st.number_input("Unexposed + No Disease (d)", min_value=0, value=st.session_state.get("cell_d", 0), key="input_d")

    if st.button("Calculate", type="primary"):
        if a + b + c + d == 0:
            st.error("Enter at least some values in the 2x2 table.")
            return

        col_or, col_rr = st.columns(2)

        or_result = _odds_ratio(a, b, c, d)
        rr_result = _relative_risk(a, b, c, d)

        with col_or:
            st.metric("Odds Ratio", f"{or_result['or']}")
            st.caption(f"95% CI: {or_result['ci_lower']} - {or_result['ci_upper']}")

        with col_rr:
            if rr_result["rr"] is not None:
                st.metric("Relative Risk", f"{rr_result['rr']}")
                st.caption(f"95% CI: {rr_result['ci_lower']} - {rr_result['ci_upper']}")
            else:
                st.metric("Relative Risk", "N/A")
                st.caption("Cannot calculate (division by zero)")

        # Attack rates
        ar_exposed = _attack_rate(a, a + b)
        ar_unexposed = _attack_rate(c, c + d)
        st.markdown(f"**Attack rate (exposed):** {ar_exposed}%  |  **Attack rate (unexposed):** {ar_unexposed}%")

        # Interpretation
        if or_result["or"] > 1 and or_result["ci_lower"] > 1:
            st.success(f"The exposure is significantly associated with disease (OR={or_result['or']}, CI does not include 1).")
        elif or_result["or"] < 1 and or_result["ci_upper"] < 1:
            st.info(f"The exposure appears protective (OR={or_result['or']}, CI does not include 1).")
        else:
            st.warning(f"The association is not statistically significant (OR={or_result['or']}, 95% CI includes 1).")
