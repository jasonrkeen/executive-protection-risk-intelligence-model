"""Streamlit and PDF presentation for the IV-2.1-RPR1 evidence audit.

Presentation only. The source output remains the IV validation CSVs.
"""


def show_intelligence_validation_tab(confidence, gaps, requirements, plan):
    import pandas as pd
    import streamlit as st

    st.subheader("Intelligence Evidence Coverage & Validation")
    st.caption(
        "Evidence-coverage index, not a statistical confidence level or incident probability. "
        "All movement inputs, source currency, and protective capacity require analyst verification."
    )
    if confidence.empty:
        st.warning("Validation output not found. Run python -m src.main.")
        return
    display = confidence.copy()
    if "intelligence_confidence_score" in display:
        display = display.sort_values("intelligence_confidence_score", ascending=True)
    cols = st.columns(4)
    cols[0].metric("Movements reviewed", str(len(display)))
    cols[1].metric("Priority validation", str(
        (display["validation_priority"] == "Priority validation").sum()
        if "validation_priority" in display else 0
    ))
    cols[2].metric("Listed evidence gaps", str(len(gaps)))
    cols[3].metric("Collection questions", str(len(plan)))
    st.markdown("### Movement-level evidence coverage")
    fields = [
        "trip_id", "city", "country", "protective_intelligence_risk_score",
        "residual_risk_score", "coa_level", "intelligence_confidence_score",
        "intelligence_confidence_label", "validation_priority", "validation_summary",
        "acled_latest_event_date", "acled_age_days", "wgi_coverage_status",
        "forward_target_data_status",
    ]
    fields = [key for key in fields if key in display]
    st.dataframe(display[fields], use_container_width=True, hide_index=True)
    st.download_button(
        "Download evidence-coverage table",
        data=display.to_csv(index=False).encode("utf-8"),
        file_name="intelligence_confidence_scores.csv",
        mime="text/csv",
    )
    if "intelligence_confidence_score" in display:
        st.bar_chart(display.set_index("trip_id")["intelligence_confidence_score"])
    options = display["trip_id"].astype(str).tolist()
    selected = st.selectbox("Inspect movement", options, key="iv_trip_select")
    row = display.loc[display["trip_id"].astype(str) == selected].iloc[0]
    st.info(str(row.get("validation_summary", "No validation notes available.")))
    st.caption(
        "ACLED 30/90-day windows are relative to the latest event in the input extract, "
        "not automatically to the current date. World Bank WGI availability is global, "
        "not verified separately for this country. Forward target-year status is informational."
    )
    for heading, frame, cols_to_show, fname in (
        (
            "Source coverage gaps", gaps,
            ["trip_id", "city", "country", "gap_area", "validation_requirement", "validation_priority"],
            "source_coverage_gaps.csv",
        ),
        (
            "Validation requirements", requirements,
            ["trip_id", "gap_area", "validation_requirement", "validation_priority"],
            "validation_requirements.csv",
        ),
        (
            "Analyst collection plan", plan,
            ["trip_id", "collection_question", "collection_purpose", "validation_priority"],
            "analyst_collection_plan.csv",
        ),
    ):
        st.markdown(f"### {heading}")
        selected_frame = frame
        if not frame.empty and "trip_id" in frame:
            selected_frame = frame[frame["trip_id"].astype(str) == selected]
        if selected_frame.empty:
            st.info("No outstanding entries for the selected movement.")
        else:
            selected_cols = [c for c in cols_to_show if c in selected_frame]
            st.dataframe(selected_frame[selected_cols], use_container_width=True, hide_index=True)
        st.download_button(
            f"Download {heading.lower()}",
            data=frame.to_csv(index=False).encode("utf-8"),
            file_name=fname,
            mime="text/csv",
            key=f"iv_download_{fname}",
        )
    st.warning(
        "Source existence, completeness, and analytical stability are not proof of source "
        "accuracy. The model is for strategic screening only, not operational travel approval."
    )


def add_intelligence_validation_section(story, styles, confidence, gaps, plan):
    from reportlab.platypus import Paragraph, PageBreak, Spacer
    from xml.sax.saxutils import escape

    if confidence.empty:
        return
    story.append(PageBreak())
    story.append(Paragraph(
        "Intelligence Evidence Coverage and Collection Requirements",
        styles["heading"],
    ))
    story.append(Paragraph(
        "IV-2.1-RPR1 measures coverage of seven explicitly checked evidence categories "
        "for each movement: source recency, city match, support proxies, trip inputs, "
        "protective capacity, global WGI availability, and COA coverage. Its numerical "
        "index is an uncalibrated evidence-coverage measure, not the probability that "
        "the model's risk conclusions are correct. Unknown or stale evidence is flagged.",
        styles["body"],
    ))
    for _, row in confidence.iterrows():
        ident = escape(str(row.get("trip_id", "Unknown movement")))
        city = escape(str(row.get("city", "")))
        country = escape(str(row.get("country", "")))
        label = escape(str(row.get("intelligence_confidence_label", "")))
        priority = escape(str(row.get("validation_priority", "")))
        details = escape(str(row.get("validation_summary", "")))
        value = row.get("intelligence_confidence_score")
        try:
            score = f"{float(value):.2f}"
        except (TypeError, ValueError):
            score = "unknown"
        story.append(Spacer(1, 5))
        story.append(Paragraph(
            f"<b>{ident} - {city}, {country}</b>: coverage index {score}/100; "
            f"{label}; {priority}. {details}",
            styles["body"],
        ))
    if not gaps.empty:
        story.append(Paragraph("Source and Evidence Gaps", styles["subheading"]))
        for _, gap in gaps.head(18).iterrows():
            note = escape(str(gap.get("validation_requirement", "")))
            story.append(Paragraph(
                f"<b>{escape(str(gap.get('trip_id', '')))}</b> / "
                f"{escape(str(gap.get('gap_area', '')))}: {note}",
                styles["small"],
            ))
    if not plan.empty:
        story.append(Paragraph("Analyst Collection Questions", styles["subheading"]))
        for _, item in plan.head(18).iterrows():
            question = escape(str(item.get("collection_question", "")))
            story.append(Paragraph(
                f"<b>{escape(str(item.get('trip_id', '')))}</b>: {question}",
                styles["small"],
            ))
    story.append(Paragraph(
        "The input ACLED window may terminate well before the report date, World Bank "
        "governance availability is assessed globally rather than per country, and "
        "protective-capacity ratings are provisional analyst assessments. These outputs "
        "must not be treated as travel approvals, tactical guidance, or validated "
        "likelihood estimates.",
        styles["small"],
    ))
