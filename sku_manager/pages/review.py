"""
Review page.

Reviewers upload an output Excel (produced by the creator's Download Excel),
which is parsed back into the full workspace. They can switch between all SKUs,
edit everything, and download a corrected Excel when done.
"""
from __future__ import annotations

import streamlit as st

from sku_manager.pages import workspace
from sku_manager.services.export import (
    build_input_sheet_df,
    build_output_df,
    build_video_links_df,
    build_warranty_export_df,
    excel_bytes,
    parse_output_excel,
    text_bytes,
)
from sku_manager.state import set_batch, set_description_state, sync_description_state
from sku_manager.ui.components import page_header
from sku_manager.ui.layout import review_sku_bar


def render() -> None:
    page_header("Review Mode", "Upload and Review a Created Batch")

    if not st.session_state.get("_review_loaded"):
        _render_upload()
        return

    _render_review_workspace()


def _render_upload() -> None:
    st.markdown("### Upload a Batch for Review")
    st.caption(
        "Upload an Excel file exported from this app (Download Excel). "
        "All SKUs will load into the workspace exactly as the creator left them."
    )

    uploaded = st.file_uploader(
        "Output Excel file (.xlsx)",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        key="_review_upload",
    )
    if uploaded is None:
        return

    try:
        queue_df, items = parse_output_excel(uploaded)
    except ValueError as exc:
        st.error(str(exc))
        return

    st.success(f"Loaded {len(items)} SKU(s) from '{uploaded.name}'.")

    if st.button("Open for Review", type="primary"):
        set_batch(queue_df)
        st.session_state["items"] = items
        st.session_state["current_item_no"] = next(iter(items), "")
        st.session_state["_review_loaded"] = True
        st.session_state["_review_source_name"] = uploaded.name
        for ino, item in items.items():
            set_description_state(ino, item["details"].get("description", ""))
        st.rerun()


def _render_review_workspace() -> None:
    source = st.session_state.get("_review_source_name", "uploaded file")

    review_sku_bar()

    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.caption(f"Source: {source}")
    with top_r:
        if st.button("Exit Review", use_container_width=True):
            _clear_review_state()
            st.rerun()
    default_name = _default_export_name(source)
    xl_name_col, txt_name_col = st.columns(2)
    excel_name = xl_name_col.text_input(
        "Excel file name",
        value=st.session_state.get("_review_excel_name", default_name),
        placeholder="Enter Excel file name (no extension)",
        key="_review_excel_name",
    ).strip() or default_name
    text_name = txt_name_col.text_input(
        "Text file name",
        value=st.session_state.get("_review_text_name", default_name),
        placeholder="Enter text file name (no extension)",
        key="_review_text_name",
    ).strip() or default_name

    sync_description_state()
    output_df = build_output_df(st.session_state["queue_df"], st.session_state["items"])
    input_df = build_input_sheet_df(st.session_state["queue_df"], st.session_state["items"])
    video_links_df = build_video_links_df(st.session_state["queue_df"], st.session_state["items"])
    warranty_df = build_warranty_export_df(st.session_state["queue_df"], st.session_state["items"])

    xl_col, txt_col = st.columns(2)
    xl_col.download_button(
        "Download Excel",
        data=excel_bytes(output_df, input_df, video_links_df, warranty_df),
        file_name=f"{excel_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
    txt_col.download_button(
        "Download Text",
        data=text_bytes(output_df),
        file_name=f"{text_name}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    workspace.render()


def _default_export_name(source: str) -> str:
    name = source.replace(".xlsx", "").replace(".xls", "").replace(".csv", "")
    return f"{name} - Reviewed"


def _clear_review_state() -> None:
    for key in ["_review_loaded", "_review_source_name", "_review_excel_name", "_review_text_name"]:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if key.startswith("_desc_"):
            del st.session_state[key]