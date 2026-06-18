from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
)

from src.config import (
    PROJECT_TITLE,
    PROJECT_SUBTITLE,
    AUTHOR_NAME,
    AUTHOR_EMAIL,
    REPORT_FILE,
    RISK_RANKINGS_FILE,
    SCENARIO_FILE,
    CHARTS_DIR,
    MODEL_MATURITY_FILE,
    MODEL_COMPONENT_MATURITY_FILE,
    MODEL_COMPONENT_COVERAGE_FILE,
    MISSING_VALUES_FILE,
    SENSITIVITY_SUMMARY_FILE,
    SENSITIVITY_OVERLAP_FILE,
    SENSITIVITY_TOP20_FILE,
    SCENARIO_TOP_COUNTRIES_FILE,
    SCENARIO_SUMMARY_FILE,
    FORWARD_2026_RISK_FILE,
    FORWARD_2026_TOP_CHANGES_FILE,
    RISK_SCORE_CHANGES_FILE,
    RISK_BUCKET_CHANGES_FILE,
    TOP_RANK_MOVERS_FILE,
    MODEL_GOVERNANCE_FILE,
    MODEL_ASSUMPTIONS_FILE,
    MONTE_CARLO_COUNTRY_SUMMARY_FILE,
    MONTE_CARLO_TOP20_PROBABILITY_FILE,
    MONTE_CARLO_SCORE_DISTRIBUTION_CHART,
    MONTE_CARLO_TOP20_PROBABILITY_CHART,
    REGIONAL_SPILLOVER_FILE,
    REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE,
    REGIONAL_SPILLOVER_CHART,
    INTELLIGENCE_SIGNAL_FILE,
    INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE,
    INTELLIGENCE_SIGNAL_CHART,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CITY_EP_RISK_FEATURES_FILE = (
    PROJECT_ROOT / "data" / "processed" / "city_ep_risk_features.csv"
)

TOP_CITY_EP_RISK_RANKINGS_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "top_25_city_ep_risk_rankings.csv"
)

CITY_ACCESS_PROXY_FILE = (
    PROJECT_ROOT / "data" / "processed" / "city_access_proxy_features.csv"
)

TOP_OPERATIONAL_RISK_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "top_25_city_operational_risk_rankings.csv"
)

CITY_TOP_20_CHART = (
    PROJECT_ROOT / "outputs" / "charts" / "top_20_city_ep_risk_rankings.png"
)

CITY_COMPONENT_BREAKDOWN_CHART = (
    PROJECT_ROOT / "outputs" / "charts" / "top_15_city_risk_component_breakdown.png"
)

CITY_RISK_MAP_FILE = (
    PROJECT_ROOT / "outputs" / "maps" / "city_ep_risk_map.html"
)

PROTECTIVE_INTELLIGENCE_TRIP_SCORES_FILE = (
    PROJECT_ROOT / "data" / "processed" / "protective_intelligence_trip_scores.csv"
)

TOP_PROTECTIVE_INTELLIGENCE_PRIORITIES_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "top_protective_intelligence_priorities.csv"
)

PROTECTIVE_INTELLIGENCE_DECISION_SUPPORT_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "protective_intelligence_decision_support.csv"
)

TOP_DECISION_ESCALATIONS_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "top_decision_escalations.csv"
)

DECISION_RULE_AUDIT_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "decision_rule_audit.csv"
)


REPORT_SUBTITLE = (
    "Country, city, support-access, and protective intelligence posture modeling "
    "for executive travel, site visits, corporate events, and energy-sector "
    "security planning"
)


OPERATIONAL_SIGNAL_SHORT_LABELS = {
    "Severe Operational Concern": "Severe Op. Concern",
    "High Operational Concern": "High Op. Concern",
    "Elevated Operational Concern": "Elevated Op. Concern",
    "Moderate Operational Concern": "Moderate Op. Concern",
    "Lower Operational Concern": "Lower Op. Concern",
}


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    """
    Read a CSV if it exists. Return an empty DataFrame otherwise.
    """

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:
        print(f"Warning: could not read {path}: {exc}")
        return pd.DataFrame()


def format_value(value):
    """
    Format table values for PDF display.
    """

    if pd.isna(value):
        return ""

    if isinstance(value, float):
        return round(value, 2)

    return value


def shorten_operational_signal(value) -> str:
    """
    Shorten long operational signal labels for narrow PDF tables.
    """

    if pd.isna(value):
        return ""

    value = str(value)
    return OPERATIONAL_SIGNAL_SHORT_LABELS.get(value, value)


def safe_paragraph(value, font_size: int = 6):
    """
    Convert long text values into wrapped ReportLab Paragraph cells.
    """

    if pd.isna(value):
        value = ""

    value = str(format_value(value))
    value = escape(value)

    style = ParagraphStyle(
        "TableCellStyle",
        parent=getSampleStyleSheet()["BodyText"],
        fontSize=font_size,
        leading=font_size + 2,
    )

    return Paragraph(value, style)


def build_table(
    dataframe: pd.DataFrame,
    columns: list,
    max_rows: int = 10,
    font_size: int = 7,
    header_labels: dict | None = None,
    wrap_text: bool = True,
):
    """
    Build a ReportLab table from selected dataframe columns.
    """

    if dataframe.empty:
        return Paragraph("No data available.", getSampleStyleSheet()["BodyText"])

    available_columns = [column for column in columns if column in dataframe.columns]

    if not available_columns:
        return Paragraph(
            "No matching table columns available.",
            getSampleStyleSheet()["BodyText"],
        )

    display = dataframe[available_columns].head(max_rows).copy()

    headers = [
        header_labels.get(column, column) if header_labels else column
        for column in available_columns
    ]

    table_data = [headers]

    for _, row in display.iterrows():
        row_values = []

        for column in available_columns:
            value = format_value(row[column])

            if wrap_text and isinstance(value, str) and len(value) > 24:
                row_values.append(safe_paragraph(value, font_size=font_size))
            else:
                row_values.append(value)

        table_data.append(row_values)

    table = Table(table_data, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f3f4f6")],
                ),
            ]
        )
    )

    return table



def build_key_findings_table(findings: list, font_size: int = 7):
    """
    Build a polished two-column key findings table for the executive summary.
    """

    if not findings:
        return Paragraph("No key findings available.", getSampleStyleSheet()["BodyText"])

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "KeyFindingHeader",
        parent=styles["BodyText"],
        fontSize=font_size,
        leading=font_size + 2,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )

    cell_style = ParagraphStyle(
        "KeyFindingCell",
        parent=styles["BodyText"],
        fontSize=font_size,
        leading=font_size + 2,
        textColor=colors.HexColor("#111827"),
    )

    label_style = ParagraphStyle(
        "KeyFindingLabel",
        parent=styles["BodyText"],
        fontSize=font_size,
        leading=font_size + 2,
        textColor=colors.HexColor("#111827"),
        fontName="Helvetica-Bold",
    )

    table_data = [
        [
            Paragraph("Finding", header_style),
            Paragraph("Current Output", header_style),
        ]
    ]

    for label, detail in findings:
        table_data.append(
            [
                Paragraph(escape(str(label)), label_style),
                Paragraph(escape(str(detail)), cell_style),
            ]
        )

    table = Table(
        table_data,
        colWidths=[150, 360],
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.HexColor("#ffffff"), colors.HexColor("#f9fafb")],
                ),
            ]
        )
    )

    return table

def add_chart(story, chart_path: Path, width: int = 500, height: int = 320):
    """
    Add chart image if it exists.
    """

    if chart_path.exists():
        story.append(Spacer(1, 8))
        story.append(Image(str(chart_path), width=width, height=height))
        story.append(Spacer(1, 10))
    else:
        print(f"Chart not found, skipping: {chart_path}")


def make_styles():
    """
    Build custom ReportLab styles.
    """

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        spaceAfter=12,
    )

    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=14,
    )

    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        spaceBefore=14,
        spaceAfter=8,
    )

    subheading_style = ParagraphStyle(
        "SubheadingStyle",
        parent=styles["Heading3"],
        fontSize=10,
        leading=13,
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        spaceAfter=8,
    )

    small_style = ParagraphStyle(
        "SmallStyle",
        parent=styles["BodyText"],
        fontSize=7,
        leading=10,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=6,
    )

    key_finding_style = ParagraphStyle(
        "KeyFindingStyle",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        leftIndent=8,
        rightIndent=8,
        spaceBefore=4,
        spaceAfter=4,
        borderColor=colors.HexColor("#d1d5db"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.HexColor("#f9fafb"),
    )

    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "heading": heading_style,
        "subheading": subheading_style,
        "body": body_style,
        "small": small_style,
        "key_finding": key_finding_style,
    }


def is_forward_data_unavailable(forward_scores: pd.DataFrame) -> bool:
    """
    Detect whether the 2026 forward layer retained baseline because 2026 ACLED
    data was unavailable.
    """

    if forward_scores.empty:
        return False

    if "target_year_data_status" in forward_scores.columns:
        status = forward_scores["target_year_data_status"].fillna("").astype(str)

        if status.str.contains(
            "Target-year ACLED data unavailable",
            case=False,
            regex=False,
        ).all():
            return True

    if "forward_adjustment_note" in forward_scores.columns:
        notes = forward_scores["forward_adjustment_note"].fillna("").astype(str)

        if notes.str.contains("2026 ACLED data unavailable", case=False).any():
            return True

    if "2026_ytd_events" in forward_scores.columns:
        events = pd.to_numeric(
            forward_scores["2026_ytd_events"],
            errors="coerce",
        ).fillna(0)

        if events.sum() == 0:
            return True

    return False


def has_nonzero_forward_changes(forward_scores: pd.DataFrame) -> bool:
    """
    Return True if at least one forward score change is materially non-zero.
    """

    if forward_scores.empty or "forward_score_change" not in forward_scores.columns:
        return False

    changes = pd.to_numeric(
        forward_scores["forward_score_change"],
        errors="coerce",
    ).fillna(0)

    return bool((changes.abs() > 0.01).any())


def has_material_change_detection(
    score_changes: pd.DataFrame,
    bucket_changes: pd.DataFrame,
    top_rank_movers: pd.DataFrame,
) -> bool:
    """
    Determine whether run-to-run change detection found meaningful movement.
    """

    if not bucket_changes.empty:
        return True

    if not score_changes.empty and "score_change" in score_changes.columns:
        score_delta = pd.to_numeric(
            score_changes["score_change"],
            errors="coerce",
        ).fillna(0)

        if bool((score_delta.abs() > 0.01).any()):
            return True

    if not top_rank_movers.empty and "rank_change" in top_rank_movers.columns:
        rank_delta = pd.to_numeric(
            top_rank_movers["rank_change"],
            errors="coerce",
        ).fillna(0)

        if bool((rank_delta.abs() > 0).any()):
            return True

    return False


def get_forward_status_text(forward_scores: pd.DataFrame) -> str:
    """
    Return analyst-friendly forward-layer status language.
    """

    if forward_scores.empty:
        return "Forward layer not available."

    if is_forward_data_unavailable(forward_scores):
        return (
            "Forward layer initialized; target-year ACLED data unavailable, "
            "so forward scores are baseline-retained."
        )

    return "Forward layer populated with target-year ACLED trend data."


def add_title_section(story, styles):
    story.append(Paragraph(PROJECT_TITLE, styles["title"]))
    story.append(Paragraph(REPORT_SUBTITLE, styles["subtitle"]))
    story.append(
        Paragraph(
            f"{AUTHOR_NAME} | {AUTHOR_EMAIL} | Generated "
            f"{datetime.now().strftime('%B %d, %Y')}",
            styles["subtitle"],
        )
    )


def add_executive_summary(
    story,
    styles,
    rankings,
    maturity_summary,
    sensitivity_summary,
    forward_scores,
    intelligence_signals,
):
    story.append(Paragraph("Executive Summary", styles["heading"]))

    top_country_text = ""
    if not rankings.empty:
        top = rankings.iloc[0]
        top_country_text = (
            f"The highest-ranked country in the current model output is "
            f"{top['country']} with an Executive Protection Risk Score of "
            f"{round(top['executive_protection_risk_score'], 2)}."
        )

    intelligence_text = ""
    if (
        not intelligence_signals.empty
        and "ep_intelligence_signal_score" in intelligence_signals.columns
        and "ep_intelligence_signal" in intelligence_signals.columns
    ):
        signal_top = intelligence_signals.iloc[0]
        intelligence_text = (
            f" The top Executive Protection Intelligence Signal is "
            f"{signal_top['country']}, classified as "
            f"{signal_top['ep_intelligence_signal']} with a signal score of "
            f"{round(signal_top['ep_intelligence_signal_score'], 2)}."
        )

    maturity_text = ""
    if not maturity_summary.empty and "model_maturity" in maturity_summary.columns:
        row = maturity_summary.iloc[0]
        maturity_text = (
            f" Baseline model maturity is classified as {row['model_maturity']}, "
            f"with {row['live_components']} of {row['total_components']} "
            f"major baseline components populated."
        )

        maturity_text += f" {get_forward_status_text(forward_scores)}"

    stability_text = ""
    if (
        not sensitivity_summary.empty
        and "stability_interpretation" in sensitivity_summary.columns
    ):
        stability_text = (
            f" Sensitivity analysis indicates: "
            f"{sensitivity_summary.iloc[0]['stability_interpretation']}"
        )

    forward_text = ""
    if (
        not forward_scores.empty
        and "forward_2026_ep_risk_score" in forward_scores.columns
    ):
        forward_top = forward_scores.iloc[0]

        if is_forward_data_unavailable(forward_scores):
            forward_text = (
                " The 2026 forward layer is included, but current-run 2026 ACLED "
                "YTD data was unavailable for the forward-country set; therefore, "
                "forward scores retain the calibrated 2024 baseline until valid "
                "2026 ACLED data is available."
            )
        else:
            forward_text = (
                f" The 2026 forward update currently ranks {forward_top['country']} "
                f"highest, with a forward-adjusted EP risk score of "
                f"{round(forward_top['forward_2026_ep_risk_score'], 2)}."
            )

    story.append(
        Paragraph(
            "This report presents a quantitative OSINT model for estimating executive "
            "protection risk in global energy operations. The model combines ACLED "
            "event data, World Bank governance and macro indicators, a homicide-rate "
            "violent-crime proxy, energy-sector exposure indicators, recent risk "
            "momentum features, city/location-level protective intelligence, airport "
            "and medical support-access proxies, regional spillover analysis, Monte "
            "Carlo robustness testing, an executive-facing intelligence signal layer, "
            "and a trip-level Protective Intelligence posture model with a COA-oriented decision-support layer. The output is "
            "designed to support strategic thinking around executive travel, site visits, "
            "public events, operating-environment risk, and intelligence-led protective "
            "planning. "
            + top_country_text
            + intelligence_text
            + maturity_text
            + stability_text
            + forward_text,
            styles["body"],
        )
    )


def add_key_findings_section(
    story,
    styles,
    rankings,
    intelligence_signals,
    forward_scores,
    sensitivity_summary,
    monte_carlo_top20,
    spillover_top,
    top_pi_priorities=None,
    top_decision_escalations=None,
):
    """
    Add polished key findings table near the front of the report.
    """

    story.append(Paragraph("Key Findings", styles["heading"]))

    findings = []

    if not rankings.empty:
        top = rankings.iloc[0]
        findings.append(
            (
                "Highest baseline EP risk country",
                f"{top['country']} "
                f"({round(top['executive_protection_risk_score'], 2)}, "
                f"{top.get('risk_bucket', 'N/A')})",
            )
        )

    if (
        not intelligence_signals.empty
        and "ep_intelligence_signal" in intelligence_signals.columns
    ):
        signal_top = intelligence_signals.iloc[0]
        findings.append(
            (
                "Top intelligence signal",
                f"{signal_top['country']} "
                f"({signal_top['ep_intelligence_signal']}, "
                f"{round(signal_top['ep_intelligence_signal_score'], 2)})",
            )
        )

    if not monte_carlo_top20.empty and "top20_probability" in monte_carlo_top20.columns:
        stable_count = (
            pd.to_numeric(monte_carlo_top20["top20_probability"], errors="coerce")
            .fillna(0)
            .ge(0.90)
            .sum()
        )
        findings.append(
            (
                "Monte Carlo robustness",
                f"{stable_count} countries show at least 90% simulated top-20 probability",
            )
        )

    if not spillover_top.empty:
        spillover_top_row = spillover_top.iloc[0]
        findings.append(
            (
                "Highest regional spillover exposure",
                f"{spillover_top_row['country']} "
                f"({round(spillover_top_row['regional_spillover_score'], 2)})",
            )
        )

    if (
        not sensitivity_summary.empty
        and "stability_interpretation" in sensitivity_summary.columns
    ):
        findings.append(
            (
                "Sensitivity interpretation",
                str(sensitivity_summary.iloc[0]["stability_interpretation"]),
            )
        )

    if is_forward_data_unavailable(forward_scores):
        findings.append(
            (
                "2026 forward layer",
                "Target-year ACLED data unavailable; forward scores are baseline-retained",
            )
        )

    if top_pi_priorities is not None and not top_pi_priorities.empty:
        if "protective_intelligence_risk_score" in top_pi_priorities.columns:
            top_pi = top_pi_priorities.sort_values(
                "protective_intelligence_risk_score",
                ascending=False,
            ).iloc[0]

            findings.append(
                (
                    "Top Protective Intelligence posture priority",
                    f"{top_pi.get('trip_id', 'N/A')} / "
                    f"{top_pi.get('city', 'N/A')}, "
                    f"{top_pi.get('country', 'N/A')} "
                    f"({round(float(top_pi.get('protective_intelligence_risk_score', 0)), 2)}, "
                    f"{top_pi.get('protective_intelligence_signal', 'N/A')})",
                )
            )

    if top_decision_escalations is not None and not top_decision_escalations.empty:
        if (
            "protective_intelligence_risk_score" in top_decision_escalations.columns
            and "coa_level" in top_decision_escalations.columns
        ):
            top_decision = top_decision_escalations.sort_values(
                "protective_intelligence_risk_score",
                ascending=False,
            ).iloc[0]

            findings.append(
                (
                    "Top COA decision-support priority",
                    f"{top_decision.get('trip_id', 'N/A')} / "
                    f"{top_decision.get('city', 'N/A')}, "
                    f"{top_decision.get('country', 'N/A')} "
                    f"({round(float(top_decision.get('protective_intelligence_risk_score', 0)), 2)}, "
                    f"{top_decision.get('coa_level', 'N/A')} - "
                    f"{top_decision.get('protective_intelligence_recommendation', 'N/A')})",
                )
            )

    story.append(build_key_findings_table(findings))

    story.append(
        Paragraph(
            "These findings should be interpreted as strategic screening outputs "
            "rather than tactical protective decisions.",
            styles["small"],
        )
    )

    story.append(Spacer(1, 10))



def add_model_framework(story, styles):
    story.append(Paragraph("Model Framework", styles["heading"]))
    story.append(
        Paragraph(
            "The Executive Protection Risk Score is constructed from five weighted "
            "components: civil unrest and political violence, governance and rule-of-law "
            "risk, violent-crime proxy risk, energy-sector exposure, and recent risk "
            "momentum. The civil unrest component incorporates event volume, fatality "
            "intensity, event composition, geographic spread, coordinate spread, and "
            "high-relevance ACLED sub-event types.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "After the weighted component score is calculated, the model applies a "
            "bounded severity calibration layer. This uplift is designed to reduce "
            "score compression in countries with extreme conflict exposure, high "
            "fatality intensity, broad geographic spread of violence, fragile governance "
            "combined with violence, strategic energy exposure combined with instability, "
            "or elevated recent momentum. The calibration is capped so that it improves "
            "operational interpretability without overwhelming the underlying data-driven "
            "component scores.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "The model does not represent any internal corporate security methodology. "
            "It is an open-source analytical framework intended for portfolio, research, "
            "and strategic risk-intelligence purposes.",
            styles["body"],
        )
    )


def add_top_risk_section(story, styles, rankings):
    story.append(Paragraph("Top Countries by Executive Protection Risk", styles["heading"]))

    story.append(
        build_table(
            rankings,
            [
                "country",
                "executive_protection_risk_score",
                "risk_bucket",
                "civil_unrest_political_violence_score",
                "governance_risk_score",
                "violent_crime_score",
                "energy_exposure_score",
                "recent_risk_momentum_score",
            ],
            max_rows=12,
            font_size=6,
            header_labels={
                "country": "Country",
                "executive_protection_risk_score": "EP Score",
                "risk_bucket": "Bucket",
                "civil_unrest_political_violence_score": "Unrest",
                "governance_risk_score": "Gov.",
                "violent_crime_score": "Crime",
                "energy_exposure_score": "Energy",
                "recent_risk_momentum_score": "Momentum",
            },
        )
    )

    add_chart(story, CHARTS_DIR / "top_ep_risk_countries.png", width=500, height=340)
    add_chart(story, CHARTS_DIR / "ep_risk_component_scores.png", width=500, height=330)


def add_severity_calibration_section(story, styles, rankings):
    """
    Add a transparent severity calibration section.
    """

    required_columns = {
        "country",
        "executive_protection_risk_score",
        "weighted_ep_risk_score",
        "severity_uplift_total",
    }

    if not required_columns.issubset(rankings.columns):
        return

    calibration_df = rankings.copy()
    calibration_df = calibration_df[
        pd.to_numeric(
            calibration_df["severity_uplift_total"],
            errors="coerce",
        ).fillna(0)
        > 0
    ].copy()

    if calibration_df.empty:
        return

    story.append(Paragraph("Severity Calibration Layer", styles["heading"]))

    story.append(
        Paragraph(
            "The severity calibration layer separates the initial weighted model score "
            "from the final calibrated Executive Protection Risk Score. This helps the "
            "model recognize countries where extreme conflict intensity, fatality "
            "concentration, geographic spread, compound governance weakness, or strategic "
            "energy exposure creates an operationally more severe environment than the "
            "weighted component score alone would suggest.",
            styles["body"],
        )
    )

    add_chart(
        story,
        CHARTS_DIR / "weighted_vs_final_ep_risk_score.png",
        width=500,
        height=330,
    )

    add_chart(
        story,
        CHARTS_DIR / "severity_calibration_uplifts.png",
        width=500,
        height=330,
    )

    story.append(
        build_table(
            calibration_df,
            [
                "country",
                "weighted_ep_risk_score",
                "severity_uplift_total",
                "executive_protection_risk_score",
                "risk_bucket",
                "extreme_conflict_uplift",
                "fatality_severity_uplift",
                "geographic_spread_uplift",
                "compound_governance_violence_uplift",
                "strategic_energy_instability_uplift",
                "momentum_uplift",
            ],
            max_rows=10,
            font_size=5,
            header_labels={
                "country": "Country",
                "weighted_ep_risk_score": "Weighted",
                "severity_uplift_total": "Uplift",
                "executive_protection_risk_score": "Final",
                "risk_bucket": "Bucket",
                "extreme_conflict_uplift": "Conflict",
                "fatality_severity_uplift": "Fatality",
                "geographic_spread_uplift": "Spread",
                "compound_governance_violence_uplift": "Gov/Viol.",
                "strategic_energy_instability_uplift": "Energy",
                "momentum_uplift": "Momentum",
            },
        )
    )

    story.append(
        Paragraph(
            "The uplift is bounded and additive. It should be interpreted as a "
            "calibration adjustment for strategic screening, not as a standalone "
            "threat assessment.",
            styles["small"],
        )
    )


def add_regional_spillover_section(
    story,
    styles,
    spillover_scores,
    spillover_top,
):
    """
    Add regional spillover risk section.
    """

    if spillover_scores.empty and spillover_top.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("Regional Spillover Risk", styles["heading"]))

    story.append(
        Paragraph(
            "Regional spillover analysis evaluates whether a country's executive "
            "protection risk is amplified by elevated risk in nearby or analytically "
            "connected regional environments. This is useful for energy operations "
            "because executive travel, site visits, logistics, security posture, and "
            "regional operating assumptions are often influenced by instability beyond "
            "a single country border.",
            styles["body"],
        )
    )

    add_chart(
        story,
        REGIONAL_SPILLOVER_CHART,
        width=500,
        height=330,
    )

    table_df = spillover_top if not spillover_top.empty else spillover_scores

    story.append(Paragraph("Top Regional Spillover Countries", styles["subheading"]))
    story.append(
        build_table(
            table_df,
            [
                "country",
                "analytical_region",
                "executive_protection_risk_score",
                "risk_bucket",
                "regional_spillover_score",
                "regional_spillover_flag",
                "regional_average_ep_risk_score",
                "elevated_or_higher_countries",
                "high_or_severe_countries",
            ],
            max_rows=12,
            font_size=5,
            header_labels={
                "country": "Country",
                "analytical_region": "Region",
                "executive_protection_risk_score": "EP",
                "risk_bucket": "Bucket",
                "regional_spillover_score": "Spillover",
                "regional_spillover_flag": "Flag",
                "regional_average_ep_risk_score": "Reg Avg",
                "elevated_or_higher_countries": "Elev+",
                "high_or_severe_countries": "High/Sev",
            },
        )
    )

    if not table_df.empty and "regional_context_note" in table_df.columns:
        story.append(Paragraph("Regional Context Notes", styles["subheading"]))
        notes = table_df[["country", "regional_context_note"]].head(6).copy()

        story.append(
            build_table(
                notes,
                ["country", "regional_context_note"],
                max_rows=6,
                font_size=6,
                header_labels={
                    "country": "Country",
                    "regional_context_note": "Regional Context",
                },
            )
        )

    story.append(
        Paragraph(
            "Regional spillover scores should be interpreted as a strategic screening "
            "overlay. They do not imply direct contagion or causal transmission of risk "
            "from one country to another.",
            styles["small"],
        )
    )


def add_intelligence_signal_section(
    story,
    styles,
    intelligence_signals,
    intelligence_signal_top,
):
    """
    Add executive protection intelligence signal section.
    """

    if intelligence_signals.empty and intelligence_signal_top.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("Executive Protection Intelligence Signal", styles["heading"]))

    story.append(
        Paragraph(
            "The Executive Protection Intelligence Signal combines the baseline EP "
            "risk score, scenario pressure, Monte Carlo top-20 stability, regional "
            "spillover exposure, and forward-risk pressure into a single executive-facing "
            "monitoring signal. The goal is to translate model outputs into a concise "
            "analyst interpretation suitable for strategic screening and portfolio "
            "presentation.",
            styles["body"],
        )
    )

    add_chart(
        story,
        INTELLIGENCE_SIGNAL_CHART,
        width=500,
        height=330,
    )

    table_df = (
        intelligence_signal_top
        if not intelligence_signal_top.empty
        else intelligence_signals
    )

    story.append(Paragraph("Top Executive Protection Intelligence Signals", styles["subheading"]))
    story.append(
        build_table(
            table_df,
            [
                "country",
                "analytical_region",
                "executive_protection_risk_score",
                "risk_bucket",
                "ep_intelligence_signal_score",
                "ep_intelligence_signal",
                "scenario_pressure_score",
                "monte_carlo_top20_stability_score",
                "regional_spillover_score",
            ],
            max_rows=12,
            font_size=5,
            header_labels={
                "country": "Country",
                "analytical_region": "Region",
                "executive_protection_risk_score": "EP",
                "risk_bucket": "Bucket",
                "ep_intelligence_signal_score": "Signal Score",
                "ep_intelligence_signal": "Signal",
                "scenario_pressure_score": "Scenario",
                "monte_carlo_top20_stability_score": "MC Stable",
                "regional_spillover_score": "Spillover",
            },
        )
    )

    if not table_df.empty and "analyst_priority_note" in table_df.columns:
        story.append(Paragraph("Analyst Priority Notes", styles["subheading"]))
        notes = table_df[["country", "analyst_priority_note"]].head(6).copy()

        story.append(
            build_table(
                notes,
                ["country", "analyst_priority_note"],
                max_rows=6,
                font_size=6,
                header_labels={
                    "country": "Country",
                    "analyst_priority_note": "Priority Note",
                },
            )
        )

    story.append(
        Paragraph(
            "The intelligence signal is a composite screening indicator. It should be "
            "interpreted as an analyst prioritization layer, not as a tactical travel "
            "approval decision or real-world event probability forecast.",
            styles["small"],
        )
    )


def add_forward_2026_section(story, styles, forward_scores, forward_changes):
    """
    Add the 2026 Forward Risk Update section.
    """

    if forward_scores.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("2026 Forward Risk Update", styles["heading"]))

    update_window = ""
    comparison_window = ""

    if "forward_update_window" in forward_scores.columns:
        update_window = str(forward_scores.iloc[0]["forward_update_window"])

    if "comparison_window" in forward_scores.columns:
        comparison_window = str(forward_scores.iloc[0]["comparison_window"])

    window_text = ""
    if update_window and comparison_window:
        window_text = (
            f" The forward layer is configured to compare {update_window} against "
            f"the same-period comparison window of {comparison_window}."
        )

    forward_unavailable = is_forward_data_unavailable(forward_scores)
    forward_has_changes = has_nonzero_forward_changes(forward_scores)

    if forward_unavailable:
        story.append(
            Paragraph(
                "The 2026 Forward Risk Update is designed as a nowcast-style layer "
                "built on top of the calibrated 2024 baseline model. In the current "
                "run, 2026 ACLED YTD data was unavailable for the forward-country "
                "set. As a result, the model retained the calibrated 2024 baseline "
                "rather than interpreting missing event data as risk easing."
                + window_text,
                styles["body"],
            )
        )

        story.append(
            Paragraph(
                "The forward scores below should therefore be read as baseline-retained "
                "screening scores, not as a true 2026 risk forecast.",
                styles["body"],
            )
        )
    else:
        story.append(
            Paragraph(
                "The 2026 Forward Risk Update is a nowcast-style layer built on top "
                "of the calibrated 2024 baseline model. It uses recent ACLED activity "
                "for the current top-risk countries to estimate whether risk appears "
                "to be rising, easing, or stable heading into the 2026 operating "
                "environment."
                + window_text,
                styles["body"],
            )
        )

    add_chart(
        story,
        CHARTS_DIR / "forward_2026_top_risk_countries.png",
        width=500,
        height=330,
    )

    story.append(Paragraph("Top 2026 Forward EP Risk Scores", styles["subheading"]))
    story.append(
        build_table(
            forward_scores,
            [
                "country",
                "baseline_ep_risk_score_2024",
                "baseline_risk_bucket_2024",
                "forward_2026_ep_risk_score",
                "forward_risk_bucket_2026",
                "forward_score_change",
                "forward_risk_change_flag",
                "target_year_data_status",
            ],
            max_rows=10,
            font_size=5,
            header_labels={
                "country": "Country",
                "baseline_ep_risk_score_2024": "2024 Base",
                "baseline_risk_bucket_2024": "Base",
                "forward_2026_ep_risk_score": "2026",
                "forward_risk_bucket_2026": "Forward",
                "forward_score_change": "Change",
                "forward_risk_change_flag": "Flag",
                "target_year_data_status": "Target Data",
            },
        )
    )

    if forward_has_changes:
        add_chart(
            story,
            CHARTS_DIR / "forward_2026_score_changes.png",
            width=500,
            height=330,
        )

    add_chart(
        story,
        CHARTS_DIR / "forward_2026_bucket_distribution.png",
        width=500,
        height=290,
    )

    if not forward_changes.empty:
        story.append(Paragraph("Forward Data Availability Notes", styles["subheading"]))
        story.append(
            build_table(
                forward_changes,
                [
                    "country",
                    "forward_2026_ep_risk_score",
                    "forward_score_change",
                    "forward_risk_change_flag",
                    "forward_adjustment_note",
                    "forward_fetch_status",
                ],
                max_rows=8,
                font_size=5,
                header_labels={
                    "country": "Country",
                    "forward_2026_ep_risk_score": "Forward",
                    "forward_score_change": "Change",
                    "forward_risk_change_flag": "Flag",
                    "forward_adjustment_note": "Note",
                    "forward_fetch_status": "Fetch Status",
                },
            )
        )


def add_change_detection_section(
    story,
    styles,
    score_changes,
    bucket_changes,
    top_rank_movers,
):
    """
    Add run-to-run change detection section.
    """

    if score_changes.empty and bucket_changes.empty and top_rank_movers.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("Run-to-Run Change Detection", styles["heading"]))

    story.append(
        Paragraph(
            "Run-to-run change detection compares the current Executive Protection "
            "Risk rankings against the previous saved model snapshot. This helps "
            "identify countries where modeled risk increased, decreased, changed "
            "risk bucket, or moved materially in the country rankings.",
            styles["body"],
        )
    )

    has_material_changes = has_material_change_detection(
        score_changes,
        bucket_changes,
        top_rank_movers,
    )

    if not has_material_changes:
        story.append(
            Paragraph(
                "No material run-to-run changes were detected in this model run. "
                "Current rankings, scores, and risk buckets matched the previous "
                "saved snapshot within the model's change-detection thresholds.",
                styles["body"],
            )
        )
        story.append(
            Paragraph(
                "The snapshot was still refreshed, so future runs can identify "
                "new movement when input data, model parameters, or forward-risk "
                "signals change.",
                styles["small"],
            )
        )
        return

    if not top_rank_movers.empty:
        movers = top_rank_movers.copy()

        if "rank_change" in movers.columns:
            movers["rank_change_abs"] = pd.to_numeric(
                movers["rank_change"],
                errors="coerce",
            ).fillna(0).abs()
            movers = movers[movers["rank_change_abs"] > 0].copy()

        if not movers.empty:
            story.append(Paragraph("Top Rank Movers", styles["subheading"]))
            story.append(
                build_table(
                    movers,
                    [
                        "country",
                        "rank_previous",
                        "rank_current",
                        "rank_change",
                        "rank_change_flag",
                        "score_change",
                        "score_change_flag",
                    ],
                    max_rows=10,
                    font_size=6,
                    header_labels={
                        "country": "Country",
                        "rank_previous": "Prev",
                        "rank_current": "Curr",
                        "rank_change": "Rank Chg.",
                        "rank_change_flag": "Rank Flag",
                        "score_change": "Score Chg.",
                        "score_change_flag": "Score Flag",
                    },
                )
            )

    if not bucket_changes.empty:
        story.append(Paragraph("Risk Bucket Changes", styles["subheading"]))
        story.append(
            build_table(
                bucket_changes,
                [
                    "country",
                    "risk_bucket_previous",
                    "risk_bucket_current",
                    "bucket_change",
                    "score_change",
                ],
                max_rows=10,
                font_size=6,
                header_labels={
                    "country": "Country",
                    "risk_bucket_previous": "Previous",
                    "risk_bucket_current": "Current",
                    "bucket_change": "Bucket Change",
                    "score_change": "Score Chg.",
                },
            )
        )

    if not score_changes.empty and "score_change" in score_changes.columns:
        material_changes = score_changes.copy()
        material_changes["score_change_abs"] = pd.to_numeric(
            material_changes["score_change"],
            errors="coerce",
        ).fillna(0).abs()

        material_changes = material_changes[
            material_changes["score_change_abs"] > 0.01
        ].copy()

        if not material_changes.empty:
            story.append(Paragraph("Material Score Changes", styles["subheading"]))
            story.append(
                build_table(
                    material_changes,
                    [
                        "country",
                        "executive_protection_risk_score_previous",
                        "executive_protection_risk_score_current",
                        "score_change",
                        "score_change_flag",
                        "risk_bucket_previous",
                        "risk_bucket_current",
                    ],
                    max_rows=10,
                    font_size=6,
                    header_labels={
                        "country": "Country",
                        "executive_protection_risk_score_previous": "Prev",
                        "executive_protection_risk_score_current": "Curr",
                        "score_change": "Score Chg.",
                        "score_change_flag": "Flag",
                        "risk_bucket_previous": "Prev Bucket",
                        "risk_bucket_current": "Curr Bucket",
                    },
                )
            )


def add_acled_section(story, styles, rankings):
    story.append(Paragraph("Civil Unrest and Political Violence", styles["heading"]))
    story.append(
        Paragraph(
            "ACLED event data is used to estimate the security environment relevant "
            "to executive movement, site visits, public events, and route planning. "
            "The model uses protests, riots, battles, remote violence, violence "
            "against civilians, fatalities, high-fatality events, geographic spread, "
            "and coordinate-pair spread to separate isolated event activity from broader "
            "operating risk.",
            styles["body"],
        )
    )

    story.append(
        build_table(
            rankings,
            [
                "country",
                "total_acled_events",
                "civil_unrest_events",
                "violent_political_events",
                "total_fatalities",
                "fatal_events",
                "high_fatality_events",
            ],
            max_rows=10,
            font_size=6,
            header_labels={
                "country": "Country",
                "total_acled_events": "Events",
                "civil_unrest_events": "Unrest",
                "violent_political_events": "Violent",
                "total_fatalities": "Fatalities",
                "fatal_events": "Fatal Events",
                "high_fatality_events": "High-Fatality",
            },
        )
    )

    add_chart(story, CHARTS_DIR / "civil_unrest_vs_ep_risk.png", width=500, height=320)
    add_chart(story, CHARTS_DIR / "top_acled_event_volume_countries.png", width=500, height=330)
    add_chart(story, CHARTS_DIR / "top_acled_fatality_countries.png", width=500, height=330)



def add_city_level_protective_intelligence_section(
    story,
    styles,
    city_features,
    top_city_rankings,
):
    """
    Add city/location-level ACLED protective intelligence section.
    """

    if city_features.empty and top_city_rankings.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("City-Level Protective Intelligence Layer", styles["heading"]))

    story.append(
        Paragraph(
            "The city-level protective intelligence layer extends the baseline "
            "country model by ranking ACLED city/location records according to recent "
            "civil unrest, political violence, severity, event momentum, and "
            "EP-relevant exposure. This layer is designed for strategic screening "
            "and travel-intelligence prioritization, not tactical route planning.",
            styles["body"],
        )
    )

    if not city_features.empty and "city_ep_risk_score" in city_features.columns:
        top_city = city_features.sort_values(
            "city_ep_risk_score",
            ascending=False,
        ).iloc[0]

        story.append(
            Paragraph(
                f"The highest-ranked city/location in the current ACLED city layer is "
                f"{top_city.get('city', 'N/A')}, {top_city.get('country', 'N/A')}, "
                f"with a City EP Risk Score of "
                f"{round(float(top_city.get('city_ep_risk_score', 0)), 2)} and a "
                f"signal of {top_city.get('signal', 'N/A')}.",
                styles["body"],
            )
        )

    table_df = top_city_rankings if not top_city_rankings.empty else city_features

    story.append(Paragraph("Top City/Location EP Risk Rankings", styles["subheading"]))
    story.append(
        build_table(
            table_df,
            [
                "rank",
                "city",
                "country",
                "admin1",
                "events_90d",
                "fatalities_90d",
                "civil_unrest_score",
                "political_violence_score",
                "severity_score",
                "momentum_score",
                "ep_relevance_score",
                "city_ep_risk_score",
                "signal",
                "primary_driver",
            ],
            max_rows=12,
            font_size=5,
            header_labels={
                "rank": "Rank",
                "city": "City/Location",
                "country": "Country",
                "admin1": "Admin1",
                "events_90d": "90d Events",
                "fatalities_90d": "90d Fatal.",
                "civil_unrest_score": "Unrest",
                "political_violence_score": "Violence",
                "severity_score": "Severity",
                "momentum_score": "Momentum",
                "ep_relevance_score": "EP Rel.",
                "city_ep_risk_score": "City EP",
                "signal": "Signal",
                "primary_driver": "Driver",
            },
        )
    )

    add_chart(
        story,
        CITY_TOP_20_CHART,
        width=500,
        height=330,
    )

    add_chart(
        story,
        CITY_COMPONENT_BREAKDOWN_CHART,
        width=500,
        height=330,
    )

    if CITY_RISK_MAP_FILE.exists():
        story.append(
            Paragraph(
                "An interactive geospatial city-risk map is generated separately as "
                f"an HTML dashboard artifact: {CITY_RISK_MAP_FILE.name}. The PDF "
                "summarizes the ranked output and chart views, while the Streamlit "
                "dashboard provides the interactive map experience.",
                styles["small"],
            )
        )

    story.append(
        Paragraph(
            "Methodology note: ACLED location names are treated as city/location-level "
            "records. Some entries may represent neighborhoods, towns, villages, "
            "districts, or event locations rather than formal city boundaries.",
            styles["small"],
        )
    )


def add_access_support_proxy_section(
    story,
    styles,
    city_access,
    top_operational_city_rankings,
):
    """
    Add airport and medical access proxy section.
    """

    if city_access.empty and top_operational_city_rankings.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("Airport and Medical Access Proxy Layer", styles["heading"]))

    story.append(
        Paragraph(
            "The access-support proxy layer adds a planning-support view to the "
            "city-level model. It combines airport access, country-level medical "
            "capacity proxies, support access scoring, and support gap scoring to "
            "estimate where protective planning may face greater operating constraints. "
            "This layer is not a medical assessment, evacuation plan, or tactical "
            "protective operations product.",
            styles["body"],
        )
    )

    table_df = (
        top_operational_city_rankings
        if not top_operational_city_rankings.empty
        else city_access
    )

    if not table_df.empty and "city_operational_ep_risk_score" in table_df.columns:
        top_operational = table_df.sort_values(
            "city_operational_ep_risk_score",
            ascending=False,
        ).iloc[0]

        story.append(
            Paragraph(
                f"The highest access-adjusted operational EP risk location is "
                f"{top_operational.get('city', 'N/A')}, "
                f"{top_operational.get('country', 'N/A')}, with an operational EP "
                f"risk score of "
                f"{round(float(top_operational.get('city_operational_ep_risk_score', 0)), 2)}. "
                f"The support gap score is "
                f"{round(float(top_operational.get('support_gap_score', 0)), 2)}.",
                styles["body"],
            )
        )

    story.append(Paragraph("Top Access-Adjusted Operational City Rankings", styles["subheading"]))

    table_display = table_df.copy()
    if "operational_ep_signal" in table_display.columns:
        table_display["operational_signal_short"] = table_display[
            "operational_ep_signal"
        ].apply(shorten_operational_signal)

    story.append(
        build_table(
            table_display,
            [
                "operational_rank",
                "city",
                "country",
                "admin1",
                "city_ep_risk_score",
                "nearest_airport_iata",
                "nearest_airport_km",
                "airport_access_score",
                "medical_capacity_score",
                "support_gap_score",
                "city_operational_ep_risk_score",
                "operational_signal_short",
            ],
            max_rows=12,
            font_size=5,
            header_labels={
                "operational_rank": "Rank",
                "city": "City",
                "country": "Country",
                "admin1": "Admin1",
                "city_ep_risk_score": "City EP",
                "nearest_airport_iata": "IATA",
                "nearest_airport_km": "Airport km",
                "airport_access_score": "Airport",
                "medical_capacity_score": "Medical",
                "support_gap_score": "Gap",
                "city_operational_ep_risk_score": "Operational",
                "operational_signal_short": "Signal",
            },
        )
    )

    story.append(
        Paragraph(
            "Note: the summary table uses IATA code and shortened operational signal "
            "labels to preserve PDF readability. Full airport names and status labels "
            "are provided in the access proxy detail table below.",
            styles["small"],
        )
    )

    if not city_access.empty and "city_operational_ep_risk_score" in city_access.columns:
        story.append(Paragraph("Access Proxy Detail", styles["subheading"]))

        detail_df = city_access.sort_values(
            "city_operational_ep_risk_score",
            ascending=False,
        ).head(10)

        if "operational_ep_signal" in detail_df.columns:
            detail_df["operational_signal_short"] = detail_df[
                "operational_ep_signal"
            ].apply(shorten_operational_signal)

        story.append(
            build_table(
                detail_df,
                [
                    "city",
                    "country",
                    "nearest_airport_iata",
                    "airport_access_status",
                    "hospital_beds_per_1000",
                    "physicians_per_1000",
                    "medical_capacity_status",
                    "operational_signal_short",
                ],
                max_rows=10,
                font_size=5,
                header_labels={
                    "city": "City",
                    "country": "Country",
                    "nearest_airport_iata": "IATA",
                    "airport_access_status": "Airport Status",
                    "hospital_beds_per_1000": "Beds/1k",
                    "physicians_per_1000": "Phys./1k",
                    "medical_capacity_status": "Medical Status",
                    "operational_signal_short": "Operational Signal",
                },
            )
        )

    story.append(
        Paragraph(
            "Interpretation note: the access-adjusted operational EP score increases "
            "when city-level risk is high and support access is constrained. Airport "
            "access is based on distance to large and medium airports where reference "
            "data is available. Medical capacity uses country-level World Bank proxy "
            "indicators and should not be interpreted as local hospital capability.",
            styles["small"],
        )
    )


def add_protective_intelligence_posture_section(
    story,
    styles,
    pi_trip_scores,
    top_pi_priorities,
):
    """
    Add the Protective Intelligence Exposure and Decision-Support Layer.
    """

    if pi_trip_scores.empty and top_pi_priorities.empty:
        return

    story.append(PageBreak())
    story.append(
        Paragraph(
            "Protective Intelligence Exposure and Decision-Support Layer",
            styles["heading"],
        )
    )

    story.append(
        Paragraph(
            "The Protective Intelligence layer translates the project's country, city, "
            "access, and exposure indicators into a movement-level decision-support "
            "score. This layer is designed to reflect an intelligence-led executive "
            "protection approach: identify exposure before movement, evaluate local "
            "threat context, assess predictability and venue risk, and convert those "
            "inputs into a protective posture recommendation.",
            styles["body"],
        )
    )

    table_df = top_pi_priorities if not top_pi_priorities.empty else pi_trip_scores

    if not table_df.empty and "protective_intelligence_risk_score" in table_df.columns:
        top_pi = table_df.sort_values(
            "protective_intelligence_risk_score",
            ascending=False,
        ).iloc[0]

        story.append(
            Paragraph(
                f"The highest Protective Intelligence priority in the current trip "
                f"input set is {top_pi.get('trip_id', 'N/A')} for "
                f"{top_pi.get('principal', 'N/A')} in "
                f"{top_pi.get('city', 'N/A')}, {top_pi.get('country', 'N/A')}. "
                f"The PI Risk Score is "
                f"{round(float(top_pi.get('protective_intelligence_risk_score', 0)), 2)}, "
                f"with a signal of {top_pi.get('protective_intelligence_signal', 'N/A')} "
                f"and posture recommendation: "
                f"{top_pi.get('protective_posture_recommendation', 'N/A')}.",
                styles["body"],
            )
        )

    story.append(Paragraph("Top Protective Intelligence Priorities", styles["subheading"]))
    story.append(
        build_table(
            table_df,
            [
                "pi_priority_rank",
                "trip_id",
                "principal",
                "city",
                "country",
                "scenario",
                "protective_intelligence_risk_score",
                "protective_intelligence_signal",
                "protective_posture_recommendation",
                "city_context_match_flag",
            ],
            max_rows=12,
            font_size=5,
            header_labels={
                "pi_priority_rank": "Rank",
                "trip_id": "Trip",
                "principal": "Principal",
                "city": "City",
                "country": "Country",
                "scenario": "Scenario",
                "protective_intelligence_risk_score": "PI Score",
                "protective_intelligence_signal": "PI Signal",
                "protective_posture_recommendation": "Posture",
                "city_context_match_flag": "Context",
            },
        )
    )

    if not table_df.empty:
        story.append(Paragraph("Protective Intelligence Component Scores", styles["subheading"]))
        story.append(
            build_table(
                table_df,
                [
                    "trip_id",
                    "local_threat_environment_score",
                    "principal_exposure_score",
                    "movement_predictability_score",
                    "venue_airport_hotel_exposure_score",
                    "online_information_leakage_score",
                    "support_gap_score",
                    "reputational_business_sensitivity_score",
                    "protective_intelligence_base_score",
                    "scenario_multiplier",
                    "protective_intelligence_risk_score",
                ],
                max_rows=10,
                font_size=5,
                header_labels={
                    "trip_id": "Trip",
                    "local_threat_environment_score": "Local Threat",
                    "principal_exposure_score": "Principal",
                    "movement_predictability_score": "Predictability",
                    "venue_airport_hotel_exposure_score": "Venue/Airport",
                    "online_information_leakage_score": "Online Leak",
                    "support_gap_score": "Support Gap",
                    "reputational_business_sensitivity_score": "Rep./Sector",
                    "protective_intelligence_base_score": "Base",
                    "scenario_multiplier": "Multiplier",
                    "protective_intelligence_risk_score": "PI Score",
                },
            )
        )

    if not table_df.empty and "analyst_priority_note" in table_df.columns:
        story.append(Paragraph("Analyst Priority Notes", styles["subheading"]))
        note_df = table_df[
            [
                column
                for column in [
                    "trip_id",
                    "principal",
                    "city",
                    "country",
                    "analyst_priority_note",
                ]
                if column in table_df.columns
            ]
        ].head(8)

        story.append(
            build_table(
                note_df,
                [
                    "trip_id",
                    "principal",
                    "city",
                    "country",
                    "analyst_priority_note",
                ],
                max_rows=8,
                font_size=5,
                header_labels={
                    "trip_id": "Trip",
                    "principal": "Principal",
                    "city": "City",
                    "country": "Country",
                    "analyst_priority_note": "Priority Note",
                },
            )
        )

    story.append(
        Paragraph(
            "Interpretation note: the Protective Intelligence score is a planning "
            "and triage indicator. It combines local threat environment, principal "
            "visibility, movement predictability, venue/airport/hotel exposure, online "
            "or itinerary exposure, support-access constraints, and reputational or "
            "business sensitivity. It does not replace protective advances, itinerary-"
            "specific threat assessment, law-enforcement liaison, venue security review, "
            "or real-time protective intelligence.",
            styles["small"],
        )
    )



def add_protective_intelligence_decision_support_section(
    story,
    styles,
    decision_support,
    top_decision_escalations,
    decision_rule_audit,
):
    """
    Add the Protective Intelligence COA Decision-Support Layer.
    """

    if decision_support.empty and top_decision_escalations.empty:
        return

    story.append(PageBreak())
    story.append(
        Paragraph(
            "Protective Intelligence COA Decision-Support Layer",
            styles["heading"],
        )
    )

    story.append(
        Paragraph(
            "The Protective Intelligence COA decision-support layer converts trip-level "
            "risk scores and trigger flags into explainable courses of action for "
            "analyst review. The goal is to move beyond identifying elevated risk and "
            "toward documenting the type of review, validation, monitoring, or escalation "
            "that may be appropriate in a protective intelligence workflow.",
            styles["body"],
        )
    )

    table_df = (
        top_decision_escalations
        if not top_decision_escalations.empty
        else decision_support
    ).copy()

    if "decision_priority_rank" in table_df.columns:
        table_df = table_df.sort_values(
            "decision_priority_rank",
            ascending=False,
        )

    if not table_df.empty and "protective_intelligence_risk_score" in table_df.columns:
        top_decision = table_df.sort_values(
            "protective_intelligence_risk_score",
            ascending=False,
        ).iloc[0]

        story.append(
            Paragraph(
                f"The highest COA decision-support priority is "
                f"{top_decision.get('trip_id', 'N/A')} for "
                f"{top_decision.get('principal', 'N/A')} in "
                f"{top_decision.get('city', 'N/A')}, "
                f"{top_decision.get('country', 'N/A')}. The PI Risk Score is "
                f"{round(float(top_decision.get('protective_intelligence_risk_score', 0)), 2)}, "
                f"with COA level: {top_decision.get('coa_level', 'N/A')} and "
                f"recommendation: "
                f"{top_decision.get('protective_intelligence_recommendation', 'N/A')}.",
                styles["body"],
            )
        )

    story.append(Paragraph("Top COA Decision-Support Priorities", styles["subheading"]))
    story.append(
        build_table(
            table_df,
            [
                "trip_id",
                "principal",
                "city",
                "country",
                "scenario",
                "protective_intelligence_risk_score",
                "risk_band",
                "coa_level",
                "protective_intelligence_recommendation",
                "primary_decision_driver",
                "data_confidence",
            ],
            max_rows=12,
            font_size=5,
            header_labels={
                "trip_id": "Trip",
                "principal": "Principal",
                "city": "City",
                "country": "Country",
                "scenario": "Scenario",
                "protective_intelligence_risk_score": "PI Score",
                "risk_band": "Band",
                "coa_level": "COA",
                "protective_intelligence_recommendation": "Recommendation",
                "primary_decision_driver": "Primary Driver",
                "data_confidence": "Confidence",
            },
        )
    )

    if not table_df.empty:
        story.append(Paragraph("Decision Drivers and Analyst Notes", styles["subheading"]))

        note_columns = [
            column
            for column in [
                "trip_id",
                "coa_level",
                "primary_decision_driver",
                "secondary_decision_driver",
                "supporting_indicators",
                "analyst_note",
            ]
            if column in table_df.columns
        ]

        if note_columns:
            story.append(
                build_table(
                    table_df[note_columns],
                    note_columns,
                    max_rows=8,
                    font_size=5,
                    header_labels={
                        "trip_id": "Trip",
                        "coa_level": "COA",
                        "primary_decision_driver": "Primary Driver",
                        "secondary_decision_driver": "Secondary Driver",
                        "supporting_indicators": "Supporting Indicators",
                        "analyst_note": "Analyst Note",
                    },
                )
            )

    trigger_columns = [
        "trip_id",
        "trigger_count",
        "trigger_support_gap",
        "trigger_predictable_movement",
        "trigger_online_visibility",
        "trigger_city_risk_momentum",
        "trigger_high_city_risk",
        "trigger_high_score_plus_support_gap",
        "trigger_multiple_high_triggers",
    ]

    available_trigger_columns = [
        column for column in trigger_columns if column in table_df.columns
    ]

    if available_trigger_columns:
        story.append(Paragraph("Decision Trigger Flags", styles["subheading"]))
        story.append(
            build_table(
                table_df[available_trigger_columns],
                available_trigger_columns,
                max_rows=8,
                font_size=5,
                header_labels={
                    "trip_id": "Trip",
                    "trigger_count": "Triggers",
                    "trigger_support_gap": "Support Gap",
                    "trigger_predictable_movement": "Predictable",
                    "trigger_online_visibility": "Online",
                    "trigger_city_risk_momentum": "Momentum",
                    "trigger_high_city_risk": "City Risk",
                    "trigger_high_score_plus_support_gap": "High+Gap",
                    "trigger_multiple_high_triggers": "Multi",
                },
            )
        )

    if not decision_rule_audit.empty:
        story.append(Paragraph("Decision Rule Audit", styles["subheading"]))

        audit_columns = [
            column
            for column in [
                "rule_id",
                "min_score",
                "max_score",
                "required_condition",
                "coa_level",
                "recommendation",
                "rules_file_loaded",
                "total_decision_records",
                "record_count",
            ]
            if column in decision_rule_audit.columns
        ]

        if audit_columns:
            story.append(
                build_table(
                    decision_rule_audit[audit_columns],
                    audit_columns,
                    max_rows=12,
                    font_size=5,
                    header_labels={
                        "rule_id": "Rule",
                        "min_score": "Min",
                        "max_score": "Max",
                        "required_condition": "Condition",
                        "coa_level": "COA",
                        "recommendation": "Recommendation",
                        "rules_file_loaded": "Rules Loaded",
                        "total_decision_records": "Records",
                        "record_count": "Rule Count",
                    },
                )
            )

    story.append(
        Paragraph(
            "Interpretation note: the COA decision-support layer is an analyst-facing "
            "triage tool. It recommends review posture categories such as monitoring, "
            "validation, enhanced advance work, security lead review, senior review, "
            "or posture reassessment. It does not provide tactical instructions, route "
            "approval, venue approval, or a real-world incident probability forecast.",
            styles["small"],
        )
    )

def add_energy_governance_crime_section(story, styles, rankings):
    story.append(Paragraph("Energy Exposure, Governance, and Crime Risk", styles["heading"]))
    story.append(
        Paragraph(
            "Energy exposure is included because executive protection risk for major "
            "energy firms is shaped not only by general country risk, but also by the "
            "strategic visibility of energy assets, infrastructure, exports, and market "
            "dependence. Governance risk captures institutional weakness, rule-of-law "
            "risk, corruption-control weakness, and political stability. The violent-crime "
            "proxy uses homicide rate per 100,000 people where available, including "
            "latest-available carry-forward logic when current-year homicide values lag.",
            styles["body"],
        )
    )

    story.append(
        build_table(
            rankings,
            [
                "country",
                "homicide_rate_per_100k",
                "homicide_rate_per_100k_year",
                "crime_data_quality_flag",
                "energy_exposure_raw",
                "energy_data_quality_flag",
                "data_coverage_flag",
            ],
            max_rows=10,
            font_size=5,
            header_labels={
                "country": "Country",
                "homicide_rate_per_100k": "Homicide",
                "homicide_rate_per_100k_year": "Crime Yr",
                "crime_data_quality_flag": "Crime Quality",
                "energy_exposure_raw": "Energy Raw",
                "energy_data_quality_flag": "Energy Quality",
                "data_coverage_flag": "Coverage",
            },
        )
    )

    add_chart(story, CHARTS_DIR / "energy_exposure_vs_ep_risk.png", width=500, height=315)
    add_chart(story, CHARTS_DIR / "governance_risk_vs_ep_risk.png", width=500, height=315)
    add_chart(story, CHARTS_DIR / "violent_crime_vs_ep_risk.png", width=500, height=315)
    add_chart(story, CHARTS_DIR / "recent_momentum_vs_ep_risk.png", width=500, height=315)


def add_scenario_section(story, styles, scenarios, scenario_top, scenario_summary):
    story.append(PageBreak())
    story.append(Paragraph("Scenario Analysis", styles["heading"]))
    story.append(
        Paragraph(
            "Scenario multipliers estimate how baseline country risk may change under "
            "specific executive protection contexts, such as public energy events, "
            "site visits to energy assets, travel during civil unrest, major project "
            "announcements, or high-visibility executive visits.",
            styles["body"],
        )
    )

    if not scenario_summary.empty:
        story.append(Paragraph("Scenario Summary", styles["subheading"]))
        story.append(
            build_table(
                scenario_summary,
                [
                    "scenario",
                    "average_scenario_ep_risk_score",
                    "max_scenario_ep_risk_score",
                    "elevated_or_higher_country_count",
                    "high_risk_country_count",
                    "severe_risk_country_count",
                ],
                max_rows=10,
                font_size=6,
                header_labels={
                    "scenario": "Scenario",
                    "average_scenario_ep_risk_score": "Avg.",
                    "max_scenario_ep_risk_score": "Max",
                    "elevated_or_higher_country_count": "Elev+",
                    "high_risk_country_count": "High",
                    "severe_risk_country_count": "Severe",
                },
            )
        )

    if not scenario_top.empty:
        story.append(
            Paragraph(
                "High-Visibility Executive Visit: Top Countries",
                styles["subheading"],
            )
        )

        high_visibility = scenario_top[
            scenario_top["scenario"] == "high_visibility_executive_visit"
        ].copy()

        if high_visibility.empty and not scenarios.empty:
            high_visibility = scenarios[
                scenarios["scenario"] == "high_visibility_executive_visit"
            ].sort_values("scenario_ep_risk_score", ascending=False)

        story.append(
            build_table(
                high_visibility,
                [
                    "scenario_rank",
                    "country",
                    "baseline_ep_risk_score",
                    "scenario_ep_risk_score",
                    "scenario_score_lift",
                    "scenario_risk_bucket",
                ],
                max_rows=10,
                font_size=7,
                header_labels={
                    "scenario_rank": "Rank",
                    "country": "Country",
                    "baseline_ep_risk_score": "Base",
                    "scenario_ep_risk_score": "Scenario",
                    "scenario_score_lift": "Lift",
                    "scenario_risk_bucket": "Bucket",
                },
            )
        )


def add_sensitivity_section(story, styles, sensitivity_summary, sensitivity_overlap):
    story.append(Paragraph("Sensitivity Analysis", styles["heading"]))
    story.append(
        Paragraph(
            "Sensitivity analysis recalculates country rankings under alternative "
            "weighting assumptions. This helps assess whether the top-risk countries "
            "remain elevated because of broad-based risk exposure or because of one "
            "dominant model component.",
            styles["body"],
        )
    )

    if not sensitivity_summary.empty:
        story.append(
            build_table(
                sensitivity_summary,
                [
                    "scenario_count",
                    "unique_countries_appearing_in_any_top20",
                    "countries_top20_in_all_scenarios",
                    "countries_top20_in_majority_of_scenarios",
                    "highly_stable_top20_countries",
                    "stable_or_highly_stable_top20_countries",
                    "most_sensitive_weighting_scenario",
                    "highest_average_absolute_rank_change",
                ],
                max_rows=1,
                font_size=5,
                header_labels={
                    "scenario_count": "Scenarios",
                    "unique_countries_appearing_in_any_top20": "Any Top 20",
                    "countries_top20_in_all_scenarios": "All Scenarios",
                    "countries_top20_in_majority_of_scenarios": "Majority",
                    "highly_stable_top20_countries": "Highly Stable",
                    "stable_or_highly_stable_top20_countries": "Stable+",
                    "most_sensitive_weighting_scenario": "Most Sensitive",
                    "highest_average_absolute_rank_change": "Avg Rank Chg.",
                },
            )
        )

        if "stability_interpretation" in sensitivity_summary.columns:
            story.append(
                Paragraph(
                    str(sensitivity_summary.iloc[0]["stability_interpretation"]),
                    styles["body"],
                )
            )

    if not sensitivity_overlap.empty:
        story.append(Paragraph("Most Stable Top-20 Countries", styles["subheading"]))
        story.append(
            build_table(
                sensitivity_overlap,
                [
                    "country",
                    "top20_scenario_count",
                    "top20_scenario_share",
                    "best_sensitivity_rank",
                    "worst_sensitivity_rank",
                    "average_sensitivity_rank",
                    "ranking_stability_flag",
                ],
                max_rows=12,
                font_size=6,
                header_labels={
                    "country": "Country",
                    "top20_scenario_count": "Top20 Count",
                    "top20_scenario_share": "Share",
                    "best_sensitivity_rank": "Best",
                    "worst_sensitivity_rank": "Worst",
                    "average_sensitivity_rank": "Avg Rank",
                    "ranking_stability_flag": "Stability",
                },
            )
        )

    add_chart(story, CHARTS_DIR / "sensitivity_top20_overlap.png", width=500, height=330)


def add_monte_carlo_section(
    story,
    styles,
    monte_carlo_summary,
    monte_carlo_top20,
):
    """
    Add Monte Carlo robustness analysis section.
    """

    if monte_carlo_summary.empty and monte_carlo_top20.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("Monte Carlo Risk Simulation", styles["heading"]))

    story.append(
        Paragraph(
            "Monte Carlo simulation tests how stable country risk rankings remain "
            "when model component weights are randomly perturbed around the baseline "
            "weighting structure. This helps identify countries that remain high-risk "
            "across many plausible weighting assumptions rather than only under one "
            "deterministic model setup.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "The simulation preserves the model's core components and bounded severity "
            "calibration concept, while allowing civil unrest, governance, violent crime, "
            "energy exposure, and recent momentum weights to vary. Countries with high "
            "top-20 probability are more robustly classified as priority-risk countries.",
            styles["body"],
        )
    )

    add_chart(
        story,
        MONTE_CARLO_SCORE_DISTRIBUTION_CHART,
        width=500,
        height=330,
    )

    add_chart(
        story,
        MONTE_CARLO_TOP20_PROBABILITY_CHART,
        width=500,
        height=330,
    )

    if not monte_carlo_top20.empty:
        story.append(
            Paragraph(
                "Most Monte Carlo-Stable Top-Risk Countries",
                styles["subheading"],
            )
        )
        story.append(
            build_table(
                monte_carlo_top20,
                [
                    "country",
                    "baseline_rank",
                    "baseline_score",
                    "baseline_bucket",
                    "mean_simulated_score",
                    "score_volatility",
                    "mean_simulated_rank",
                    "top20_probability",
                    "monte_carlo_stability_flag",
                ],
                max_rows=12,
                font_size=5,
                header_labels={
                    "country": "Country",
                    "baseline_rank": "Base Rank",
                    "baseline_score": "Base",
                    "baseline_bucket": "Bucket",
                    "mean_simulated_score": "Mean Sim.",
                    "score_volatility": "Vol.",
                    "mean_simulated_rank": "Mean Rank",
                    "top20_probability": "Top20 Prob.",
                    "monte_carlo_stability_flag": "Stability",
                },
            )
        )

    if not monte_carlo_summary.empty and "score_volatility" in monte_carlo_summary.columns:
        volatile = monte_carlo_summary.sort_values(
            "score_volatility",
            ascending=False,
        ).copy()

        story.append(
            Paragraph(
                "Countries Most Sensitive to Weight Uncertainty",
                styles["subheading"],
            )
        )
        story.append(
            build_table(
                volatile,
                [
                    "country",
                    "baseline_rank",
                    "baseline_score",
                    "mean_simulated_score",
                    "score_volatility",
                    "score_range",
                    "rank_range",
                    "top20_probability",
                ],
                max_rows=8,
                font_size=5,
                header_labels={
                    "country": "Country",
                    "baseline_rank": "Base Rank",
                    "baseline_score": "Base",
                    "mean_simulated_score": "Mean Sim.",
                    "score_volatility": "Vol.",
                    "score_range": "Score Range",
                    "rank_range": "Rank Range",
                    "top20_probability": "Top20 Prob.",
                },
            )
        )

    story.append(
        Paragraph(
            "Monte Carlo results should be interpreted as a robustness test of model "
            "assumptions, not as a probability forecast of real-world security events.",
            styles["small"],
        )
    )


def add_model_governance_section(
    story,
    styles,
    governance_summary,
    assumptions_summary,
):
    """
    Add model governance and methodology controls section.
    """

    if governance_summary.empty and assumptions_summary.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("Model Governance and Methodology Controls", styles["heading"]))

    story.append(
        Paragraph(
            "This section documents the model's intended use, data-source dependencies, "
            "scoring assumptions, scenario overlays, sensitivity design, forward-risk "
            "guardrails, and limitations. It is intended to make the framework more "
            "transparent, auditable, and suitable for portfolio presentation.",
            styles["body"],
        )
    )

    if not governance_summary.empty:
        story.append(Paragraph("Governance Summary", styles["subheading"]))
        story.append(
            build_table(
                governance_summary,
                [
                    "governance_area",
                    "description",
                    "model_implication",
                ],
                max_rows=10,
                font_size=5,
                header_labels={
                    "governance_area": "Area",
                    "description": "Description",
                    "model_implication": "Model Implication",
                },
            )
        )

    if not assumptions_summary.empty:
        story.append(Paragraph("Key Model Assumptions", styles["subheading"]))

        priority_assumptions = assumptions_summary[
            assumptions_summary["assumption_type"].isin(
                [
                    "Baseline risk weight",
                    "Risk bucket",
                    "Scenario multiplier",
                    "Forward-risk assumption",
                ]
            )
        ].copy()

        if priority_assumptions.empty:
            priority_assumptions = assumptions_summary.copy()

        story.append(
            build_table(
                priority_assumptions,
                [
                    "assumption_type",
                    "assumption_name",
                    "assumption_value",
                    "notes",
                ],
                max_rows=14,
                font_size=5,
                header_labels={
                    "assumption_type": "Type",
                    "assumption_name": "Assumption",
                    "assumption_value": "Value",
                    "notes": "Notes",
                },
            )
        )

    story.append(
        Paragraph(
            "Governance note: the model is designed as an open-source strategic "
            "screening framework. It does not replace local protective intelligence, "
            "itinerary-specific threat assessment, route analysis, venue security "
            "review, or real-time monitoring.",
            styles["small"],
        )
    )


def add_diagnostics_section(
    story,
    styles,
    maturity_summary,
    component_maturity,
    coverage_summary,
    missing_values,
):
    story.append(PageBreak())
    story.append(Paragraph("Model Diagnostics and Data Coverage", styles["heading"]))
    story.append(
        Paragraph(
            "Diagnostics summarize file availability, component maturity, missing-value "
            "coverage, baseline model maturity, and forward-layer availability.",
            styles["body"],
        )
    )

    if not maturity_summary.empty:
        story.append(Paragraph("Model Maturity", styles["subheading"]))
        story.append(
            build_table(
                maturity_summary,
                [
                    "model_maturity",
                    "live_components",
                    "total_components",
                    "placeholder_components",
                    "placeholder_share",
                    "forward_layer_status",
                ],
                max_rows=1,
                font_size=5,
                header_labels={
                    "model_maturity": "Maturity",
                    "live_components": "Live",
                    "total_components": "Total",
                    "placeholder_components": "Placeholder",
                    "placeholder_share": "Placeholder Share",
                    "forward_layer_status": "Forward Layer",
                },
            )
        )

    if not component_maturity.empty:
        story.append(Paragraph("Component Maturity", styles["subheading"]))
        story.append(
            build_table(
                component_maturity,
                [
                    "model_component",
                    "component_group",
                    "status",
                    "rows_available",
                    "placeholder_used",
                    "data_quality_flag",
                ],
                max_rows=10,
                font_size=5,
                header_labels={
                    "model_component": "Component",
                    "component_group": "Group",
                    "status": "Status",
                    "rows_available": "Rows",
                    "placeholder_used": "Placeholder",
                    "data_quality_flag": "Flag",
                },
            )
        )

    if not coverage_summary.empty:
        story.append(Paragraph("Component Coverage Summary", styles["subheading"]))
        story.append(
            build_table(
                coverage_summary,
                [
                    "coverage_area",
                    "countries",
                    "coverage_metric",
                    "coverage_value",
                    "quality_flag",
                ],
                max_rows=12,
                font_size=5,
                header_labels={
                    "coverage_area": "Area",
                    "countries": "Countries",
                    "coverage_metric": "Metric",
                    "coverage_value": "Value",
                    "quality_flag": "Flag",
                },
            )
        )

    add_chart(story, CHARTS_DIR / "ep_risk_bucket_distribution.png", width=500, height=290)
    add_chart(story, CHARTS_DIR / "model_data_coverage_distribution.png", width=500, height=290)

    if not missing_values.empty:
        missing_top = missing_values[missing_values["missing_count"] > 0].copy()

        if not missing_top.empty:
            story.append(Paragraph("Highest Missing-Value Columns", styles["subheading"]))
            story.append(
                build_table(
                    missing_top,
                    [
                        "column",
                        "missing_count",
                        "missing_share",
                        "non_missing_count",
                    ],
                    max_rows=10,
                    font_size=6,
                )
            )


def add_limitations(story, styles):
    story.append(Paragraph("Limitations", styles["heading"]))

    story.append(
        Paragraph(
            "This project is an independent research and portfolio project. It is "
            "not affiliated with, endorsed by, or representative of any company, "
            "government agency, security organization, ACLED, the World Bank, or "
            "any other organization referenced through public data sources.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "This model uses public country-level and event-level data. It does not "
            "include confidential travel itineraries, executive profiles, company "
            "asset-level security data, local protective intelligence, law-enforcement "
            "liaison information, proprietary threat reporting, or route-specific "
            "protective advances. Therefore, it should be viewed as a strategic "
            "screening model rather than a tactical protection plan.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "Country-level scores can obscure local variation. A low-risk national "
            "score does not mean that every city, venue, route, event, or asset is low "
            "risk. Conversely, a high-risk national score does not mean that all travel "
            "is infeasible. The model is best used as a prioritization and analytical "
            "triage tool.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "The 2026 Forward Risk Update is a nowcast-style analytical layer designed "
            "to use recent ACLED activity for the current top-risk countries. In runs "
            "where 2026 ACLED data is unavailable, the model retains the calibrated "
            "baseline rather than treating missing data as risk improvement. It should "
            "not be interpreted as a tactical forecast or as a replacement for local "
            "protective intelligence, itinerary-specific threat assessment, or real-time "
            "security monitoring.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "The airport and medical access layer uses public proxy data. Airport "
            "distance is based on reference airport locations, and medical capacity is "
            "based on country-level World Bank indicators. These features should be "
            "interpreted as planning-support context, not as a medical, evacuation, "
            "logistics, or tactical security assessment.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "The Protective Intelligence posture layer uses user-supplied trip and "
            "exposure assumptions. Its recommendations should be interpreted as a "
            "decision-support prioritization aid, not as a final travel approval, "
            "route plan, venue advance, family exposure review, or no-go determination.",
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "The COA decision-support layer translates scores and trigger flags into "
            "review recommendations for analyst triage. These outputs should not be "
            "treated as binding operational decisions, tactical instructions, route "
            "approval, venue approval, protective detail staffing guidance, or final "
            "go/no-go determinations.",
            styles["body"],
        )
    )


def generate_report():
    print("Generating PDF report...")

    rankings = read_csv_if_exists(RISK_RANKINGS_FILE)
    scenarios = read_csv_if_exists(SCENARIO_FILE)
    scenario_top = read_csv_if_exists(SCENARIO_TOP_COUNTRIES_FILE)
    scenario_summary = read_csv_if_exists(SCENARIO_SUMMARY_FILE)

    forward_scores = read_csv_if_exists(FORWARD_2026_RISK_FILE)
    forward_changes = read_csv_if_exists(FORWARD_2026_TOP_CHANGES_FILE)

    score_changes = read_csv_if_exists(RISK_SCORE_CHANGES_FILE)
    bucket_changes = read_csv_if_exists(RISK_BUCKET_CHANGES_FILE)
    top_rank_movers = read_csv_if_exists(TOP_RANK_MOVERS_FILE)

    governance_summary = read_csv_if_exists(MODEL_GOVERNANCE_FILE)
    assumptions_summary = read_csv_if_exists(MODEL_ASSUMPTIONS_FILE)

    monte_carlo_summary = read_csv_if_exists(MONTE_CARLO_COUNTRY_SUMMARY_FILE)
    monte_carlo_top20 = read_csv_if_exists(MONTE_CARLO_TOP20_PROBABILITY_FILE)

    spillover_scores = read_csv_if_exists(REGIONAL_SPILLOVER_FILE)
    spillover_top = read_csv_if_exists(REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE)

    intelligence_signals = read_csv_if_exists(INTELLIGENCE_SIGNAL_FILE)
    intelligence_signal_top = read_csv_if_exists(INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE)

    maturity_summary = read_csv_if_exists(MODEL_MATURITY_FILE)
    component_maturity = read_csv_if_exists(MODEL_COMPONENT_MATURITY_FILE)
    missing_values = read_csv_if_exists(MISSING_VALUES_FILE)
    coverage_summary = read_csv_if_exists(MODEL_COMPONENT_COVERAGE_FILE)

    sensitivity_summary = read_csv_if_exists(SENSITIVITY_SUMMARY_FILE)
    sensitivity_overlap = read_csv_if_exists(SENSITIVITY_OVERLAP_FILE)
    _ = read_csv_if_exists(SENSITIVITY_TOP20_FILE)

    city_features = read_csv_if_exists(CITY_EP_RISK_FEATURES_FILE)
    top_city_rankings = read_csv_if_exists(TOP_CITY_EP_RISK_RANKINGS_FILE)

    city_access = read_csv_if_exists(CITY_ACCESS_PROXY_FILE)
    top_operational_city_rankings = read_csv_if_exists(TOP_OPERATIONAL_RISK_FILE)

    pi_trip_scores = read_csv_if_exists(PROTECTIVE_INTELLIGENCE_TRIP_SCORES_FILE)
    top_pi_priorities = read_csv_if_exists(TOP_PROTECTIVE_INTELLIGENCE_PRIORITIES_FILE)

    decision_support = read_csv_if_exists(PROTECTIVE_INTELLIGENCE_DECISION_SUPPORT_FILE)
    top_decision_escalations = read_csv_if_exists(TOP_DECISION_ESCALATIONS_FILE)
    decision_rule_audit = read_csv_if_exists(DECISION_RULE_AUDIT_FILE)

    if rankings.empty:
        raise FileNotFoundError(
            f"Risk rankings not available at {RISK_RANKINGS_FILE}. "
            "Run python -m src.risk_scoring first."
        )

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(REPORT_FILE),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = make_styles()
    story = []

    add_title_section(story, styles)
    add_executive_summary(
        story,
        styles,
        rankings,
        maturity_summary,
        sensitivity_summary,
        forward_scores,
        intelligence_signals,
    )
    add_key_findings_section(
        story,
        styles,
        rankings,
        intelligence_signals,
        forward_scores,
        sensitivity_summary,
        monte_carlo_top20,
        spillover_top,
        top_pi_priorities,
        top_decision_escalations,
    )
    add_model_framework(story, styles)
    add_top_risk_section(story, styles, rankings)
    add_severity_calibration_section(story, styles, rankings)
    add_regional_spillover_section(
        story,
        styles,
        spillover_scores,
        spillover_top,
    )
    add_intelligence_signal_section(
        story,
        styles,
        intelligence_signals,
        intelligence_signal_top,
    )
    add_forward_2026_section(story, styles, forward_scores, forward_changes)
    add_change_detection_section(
        story,
        styles,
        score_changes,
        bucket_changes,
        top_rank_movers,
    )
    add_acled_section(story, styles, rankings)
    add_city_level_protective_intelligence_section(
        story,
        styles,
        city_features,
        top_city_rankings,
    )
    add_access_support_proxy_section(
        story,
        styles,
        city_access,
        top_operational_city_rankings,
    )
    add_protective_intelligence_posture_section(
        story,
        styles,
        pi_trip_scores,
        top_pi_priorities,
    )
    add_protective_intelligence_decision_support_section(
        story,
        styles,
        decision_support,
        top_decision_escalations,
        decision_rule_audit,
    )
    add_energy_governance_crime_section(story, styles, rankings)
    add_scenario_section(story, styles, scenarios, scenario_top, scenario_summary)
    add_sensitivity_section(story, styles, sensitivity_summary, sensitivity_overlap)
    add_monte_carlo_section(
        story,
        styles,
        monte_carlo_summary,
        monte_carlo_top20,
    )
    add_model_governance_section(
        story,
        styles,
        governance_summary,
        assumptions_summary,
    )
    add_diagnostics_section(
        story,
        styles,
        maturity_summary,
        component_maturity,
        coverage_summary,
        missing_values,
    )
    add_limitations(story, styles)

    doc.build(story)

    print(f"PDF report created: {REPORT_FILE}")

    return REPORT_FILE


if __name__ == "__main__":
    generate_report()