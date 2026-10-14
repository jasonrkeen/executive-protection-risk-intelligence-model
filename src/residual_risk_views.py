"""Shared review presentation for the RPR-1 replacement."""
NOTICE = ("RPR-1 replacement for the unavailable native integration package. "
          "Experimental analyst assumptions; not calibrated probabilities or travel clearance. "
          "Unknown capacity retains baseline PI numerically and requires assessment.")
COLS = ["trip_id", "protective_intelligence_risk_score", "protective_capacity_score",
        "task_saturation_score", "protective_coverage_gap", "residual_risk_score",
        "capacity_input_status", "residual_review_state"]


def show_residual_risk_tab(scores):
    import streamlit as st
    st.subheader("Residual Protective Risk")
    st.caption(NOTICE)
    if scores.empty:
        st.info("Residual risk has not been generated. Run the residual layer after PI scoring.")
        return
    st.dataframe(scores[COLS], hide_index=True)
    selected = st.selectbox("Movement", scores.trip_id.tolist(), key="residual_trip")
    row = scores.loc[scores.trip_id == selected].iloc[0]
    st.write(row.residual_review_state)
    st.bar_chart(row[["protective_intelligence_risk_score", "residual_risk_score"]])


def add_residual_risk_section(story, styles, scores):
    from reportlab.platypus import Paragraph, PageBreak, Spacer
    from xml.sax.saxutils import escape
    if story:
        story.append(PageBreak())
    story.extend([Paragraph("Residual Protective Risk - RPR-1 Replacement", styles["heading"]),
                  Paragraph(NOTICE, styles["body"])])
    if scores.empty:
        story.append(Paragraph("Residual layer not generated; no residual assessment available.", styles["body"]))
        return
    # Compact movement paragraphs avoid wide or clipped tables and retain unknowns.
    for _, row in scores.iterrows():
        def value(key):
            import pandas as pd
            return "Unknown" if pd.isna(row[key]) else f"{float(row[key]):.2f}"
        text = (f"Movement {escape(str(row.trip_id))}: PI {value('protective_intelligence_risk_score')}; "
                f"capacity {value('protective_capacity_score')}; saturation {value('task_saturation_score')}; "
                f"coverage gap {value('protective_coverage_gap')}; residual {value('residual_risk_score')}. "
                f"{escape(str(row.residual_review_state))}.")
        story.extend([Spacer(1, 6), Paragraph(text, styles["body"])])
