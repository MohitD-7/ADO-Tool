from __future__ import annotations

import streamlit as st

from sku_manager.services.workbook_io import REQUIRED_COLUMNS, read_queue_workbook
from sku_manager.state import set_batch
from sku_manager.ui.components import page_header


def render() -> None:
    page_header("Step 1 of 3", "Upload SKU Batch")

    # ── How-to flow ───────────────────────────────────────────────────
    st.markdown(
        """
        <div style="display:flex;gap:1.5rem;margin-bottom:1.2rem;">
          <div style="flex:1;background:#fff;border:1px solid #e2e8f0;border-top:3px solid #ef8e0d;border-radius:8px;padding:.8rem 1rem;">
            <div style="font-weight:800;font-size:.9rem;color:#1a2330;margin-bottom:.2rem;">Step 1: Upload</div>
            <div style="font-size:.82rem;color:#555;">Drop your Excel file below and click <strong>Start Batch</strong>.</div>
          </div>
          <div style="flex:1;background:#fff;border:1px solid #e2e8f0;border-top:3px solid #cbd5e1;border-radius:8px;padding:.8rem 1rem;">
            <div style="font-weight:800;font-size:.9rem;color:#1a2330;margin-bottom:.2rem;">Step 2: Work Queue</div>
            <div style="font-size:.82rem;color:#555;">Pick a SKU and click <strong>Process Item</strong> to open its form.</div>
          </div>
          <div style="flex:1;background:#fff;border:1px solid #e2e8f0;border-top:3px solid #cbd5e1;border-radius:8px;padding:.8rem 1rem;">
            <div style="font-weight:800;font-size:.9rem;color:#1a2330;margin-bottom:.2rem;">Step 3: Edit and Export</div>
            <div style="font-size:.82rem;color:#555;">Fill in each section tab, then go to <strong>Review</strong> to export.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.4, 1])
    with left:
        uploaded = st.file_uploader(
            "Excel file (.xlsx / .xls / .xlsm)",
            type=["xlsx", "xls", "xlsm"],
            accept_multiple_files=False,
        )
        st.caption("Required columns: " + ", ".join(REQUIRED_COLUMNS) + ". Optional: ATR Type (Parent, parent SKU, or blank).")

    if uploaded is None:
        with right:
            st.markdown(
                '<div style="background:#f8fafc;border:1px solid #7cba8c;border-left:4px solid #ef8e0d;border-radius:6px;padding:.8rem 1rem;color:#1b5e30;font-size:.9rem;">'
                "<strong>No file uploaded yet.</strong><br>Drag and drop your Excel queue file into the box on the left, or click Browse Files."
                "</div>",
                unsafe_allow_html=True,
            )
        return

    result = read_queue_workbook(uploaded)
    if not result.ok:
        st.error("The uploaded file could not be used.")
        if result.missing_columns:
            st.write("Missing columns:", ", ".join(result.missing_columns))
        if result.original_columns:
            st.write("Columns found:", ", ".join(result.original_columns))
        if result.message:
            st.code(result.message)
        return

    st.success(f"Loaded {len(result.queue_df)} SKUs. Click Start Batch, or review the preview below first.")

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("Start Batch →", type="primary", width="stretch"):
            set_batch(result.queue_df)
            st.session_state["active_page"] = "SKU Batch"
            st.rerun()
    with col_b:
        st.caption("You can still edit reference data from the Reference Data page before or after starting.")

    st.dataframe(result.queue_df.head(25), width="stretch", hide_index=True)
