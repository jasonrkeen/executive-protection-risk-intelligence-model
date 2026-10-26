"""Human-readable candidate integrity views; separate from the production dashboard.

All candidate results are research-only. Withheld means no model assessment was
made; missing/invalid inputs are never silently displayed as score 50.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd


def format_candidate_for_display(shadow: pd.DataFrame) -> pd.DataFrame:
    needed = {
        "country", "candidate_component_score", "candidate_score_status",
        "candidate_shadow_composite", "candidate_disposition",
        "candidate_risk_bucket", "candidate_score_reason",
    }
    if not needed.issubset(shadow):
        raise ValueError("Missing candidate output fields")
    out = shadow[[
        "country", "candidate_score_status", "candidate_score_reason",
        "candidate_component_score", "candidate_shadow_composite",
        "candidate_disposition", "candidate_risk_bucket",
    ]].copy()
    for value in ("candidate_component_score", "candidate_shadow_composite"):
        out[value] = out[value].apply(
            lambda x: f"{float(x):.2f}" if pd.notna(x) else "WITHHELD"
        )
    out["candidate_risk_bucket"] = "NOT ISSUED"
    return out.rename(columns={
        "country": "Fictional country",
        "candidate_score_status": "Evidence status",
        "candidate_score_reason": "Why review is required",
        "candidate_component_score": "Research-only homicide index",
        "candidate_shadow_composite": "Research-only shadow composite",
        "candidate_disposition": "Scoring disposition",
        "candidate_risk_bucket": "Risk band",
    })


def show_candidate_integrity_tab(shadow: pd.DataFrame) -> None:
    """Research-only Streamlit presentation, not wired into the live dashboard."""
    import streamlit as st

    st.subheader("Experimental Source Integrity Review - Fictional Example")
    st.warning(
        "This research experiment does not issue security risk bands, travel "
        "clearance, or predictive probabilities. WITHHELD means evidence is "
        "unavailable, stale, conflicting, imputed or outside the toy reference."
    )
    if shadow.empty:
        st.info("No candidate evidence assessed.")
        return
    display = format_candidate_for_display(shadow)
    st.metric(
        "Candidate values WITHHELD",
        str((display["Research-only shadow composite"] == "WITHHELD").sum()),
    )
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption(
        "Other baseline components and the severity uplift were not independently "
        "validated or re-estimated. Scores shown are synthetic research indices only."
    )


def build_candidate_pdf(
    output: Path, observed: pd.DataFrame, absent: pd.DataFrame,
) -> Path:
    """Use ReportLab to display explicit WITHHELD states; output deterministic PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    output = Path(output)
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "research-body", parent=styles["BodyText"], fontSize=9,
        leading=12, spaceAfter=9,
    )
    small = ParagraphStyle(
        "research-cell", parent=styles["BodyText"], fontSize=7,
        leading=9, spaceAfter=0,
    )
    story = [
        Paragraph("SYNTHETIC RESEARCH - SCORING EVIDENCE INTEGRITY", styles["Title"]),
        Paragraph(
            "EXPERIMENTAL SHADOW ONLY. Two fictional countries; no operational "
            "approval, individual threat assessment, verified incidents or "
            "predictive probabilities are provided.", body,
        ),
        Paragraph(
            "Reference: a frozen, two-country toy homicide-rate range from "
            "3 to 12 per 100,000. Not applicable to real countries. All other "
            "risk components and severity adjustments remain historical and "
            "unverified in this experiment.", body,
        ),
    ]
    for title, scored in (
        ("Declared synthetic observations", observed),
        ("Unavailable source evidence - scores must be withheld", absent),
    ):
        story.append(Paragraph(escape(title), styles["Heading2"]))
        display = format_candidate_for_display(scored)
        data = [[Paragraph("Fictional country", small),
                 Paragraph("Evidence status", small),
                 Paragraph("Homicide index", small),
                 Paragraph("Shadow score", small),
                 Paragraph("Risk band", small)]]
        for _, row in display.iterrows():
            data.append([
                Paragraph(escape(str(row["Fictional country"])), small),
                Paragraph(escape(str(row["Evidence status"])), small),
                Paragraph(escape(str(row["Research-only homicide index"])), small),
                Paragraph(escape(str(row["Research-only shadow composite"])), small),
                Paragraph("NOT ISSUED", small),
            ])
        tbl = Table(data, repeatRows=1, colWidths=[90, 140, 85, 85, 78], hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9edf2")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#64748b")),
        ]))
        story.extend([Spacer(1, 8), tbl, Spacer(1, 16)])
    story.append(Paragraph(
        "A missing homicide measurement is NOT a measured zero and must not "
        "be transformed into an apparently reassuring midpoint. A score "
        "WITHHELD here remains unavailable for all protective decisions. "
        "A normal-looking research index is not source verification.",
        body,
    ))
    doc = SimpleDocTemplate(
        str(output), pagesize=letter,
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
        invariant=1,
    )
    doc.build(story)
    return output
