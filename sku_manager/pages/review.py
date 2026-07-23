"""
Review page.

Reviewers upload an output Excel (produced by the creator's Download Excel),
which is parsed back into the full workspace. They can switch between all SKUs,
edit everything, and download a corrected Excel when done.
"""
from __future__ import annotations

import pandas as pd
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
        "Upload one or more Excel files exported from this app (Download Excel). "
        "Multiple files are appended into a single review batch, in upload order, "
        "and export as one Excel/Text file."
    )

    uploaded_files = st.file_uploader(
        "Output Excel file(s) (.xlsx)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="_review_upload",
    )
    if not uploaded_files:
        return

    queue_frames: list[pd.DataFrame] = []
    merged_items: dict = {}
    duplicates: list[str] = []
    for uploaded in uploaded_files:
        try:
            queue_df, items = parse_output_excel(uploaded)
        except ValueError as exc:
            st.error(f"{uploaded.name}: {exc}")
            return
        fresh_mask = ~queue_df["Item No"].astype(str).isin(merged_items.keys())
        queue_frames.append(queue_df[fresh_mask])
        for ino, item in items.items():
            if ino in merged_items:
                duplicates.append(ino)
                continue
            merged_items[ino] = item
        st.caption(f"{uploaded.name}: {len(items)} SKU(s)")

    combined_queue = pd.concat(queue_frames, ignore_index=True)

    if duplicates:
        st.warning(
            f"Skipped {len(duplicates)} duplicate SKU(s) found in more than one file "
            f"(kept the first occurrence): {', '.join(dict.fromkeys(duplicates))}"
        )
    names = [uploaded.name for uploaded in uploaded_files]
    source_label = names[0] if len(names) == 1 else f"{names[0]} (+{len(names) - 1} more)"
    st.success(f"Loaded {len(merged_items)} SKU(s) from {len(names)} file(s).")

    if st.button("Open for Review", type="primary"):
        set_batch(combined_queue)
        st.session_state["items"] = merged_items
        st.session_state["current_item_no"] = next(iter(merged_items), "")
        st.session_state["_review_loaded"] = True
        st.session_state["_review_source_name"] = source_label
        for ino, item in merged_items.items():
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
    workspace.render(restrict_to_review=True)


def _default_export_name(source: str) -> str:
    name = source.replace(".xlsx", "").replace(".xls", "").replace(".csv", "")
    return f"{name} - Reviewed"


def _clear_review_state() -> None:
    for key in ["_review_loaded", "_review_source_name", "_review_excel_name", "_review_text_name"]:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if key.startswith("_desc_"):
            del st.session_state[key]