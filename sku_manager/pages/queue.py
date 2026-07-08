from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from sku_manager.config import STATUS_OPTIONS
from sku_manager.services.export import (
    build_input_sheet_df,
    build_output_df,
    build_video_links_df,
    excel_bytes,
    render_html,
    text_bytes,
)
from sku_manager.state import mark_status, set_current_item, sync_description_state
from sku_manager.ui.components import page_header


_SORT_OPTIONS = {
    "None (manual order)": None,
    "Item No":             "Item No",
    "Mfg Item":            "Mfg Item",
    "Title":               "Title",
    "Status":              "Status",
}


def render() -> None:
    sync_description_state()
    queue_df = st.session_state["queue_df"].copy()
    page_header("SKU Batch", "Work Queue")

    total = len(queue_df)
    completed = int((queue_df["Status"] == "Completed").sum())
    in_progress = int((queue_df["Status"] == "In Progress").sum())
    pending = total - completed - in_progress
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total SKUs", total)
    m2.metric("Completed", completed)
    m3.metric("In Progress", in_progress)
    m4.metric("Pending", max(pending, 0))

    _render_downloads()

    st.subheader("Item Processing List")

    ctrl1, ctrl2, ctrl3 = st.columns([3, 2, 1.6])
    with ctrl1:
        search = st.text_input("Search SKU or title", placeholder="Search SKUs, titles, mfg items...", label_visibility="collapsed")
    with ctrl2:
        sort_label = st.selectbox(
            "Sort by",
            list(_SORT_OPTIONS.keys()),
            index=0,
            label_visibility="collapsed",
        )
    with ctrl3:
        reorder_mode = st.toggle("Reorder mode", value=st.session_state.get("_queue_reorder_mode", False), key="_queue_reorder_mode")

    sort_col = _SORT_OPTIONS[sort_label]

    filtered = queue_df
    if search:
        mask = queue_df.apply(lambda row: search.lower() in " ".join(row.astype(str)).lower(), axis=1)
        filtered = queue_df[mask]
    if sort_col:
        filtered = filtered.sort_values(by=sort_col, kind="stable", na_position="last").reset_index()
        filtered = filtered.rename(columns={"index": "orig_index"})
    else:
        filtered = filtered.reset_index().rename(columns={"index": "orig_index"})

    if reorder_mode:
        _render_reorder_hint()

    header_cols = st.columns([0.45, 1.05, 1.55, 3.0, 1.5, 1.25, 1.15, 0.95, 0.95])
    header_style = "font-size:11px;font-weight:800;text-transform:uppercase;color:#6f8090;padding-bottom:2px;border-bottom:1px solid #e2e8f0;"
    for col, label in zip(
        header_cols,
        ["#", "ATR", "Item No", "Title", "Mfg Item", "Status", "Done By", "Preview", ""],
    ):
        col.markdown(f"<div style='{header_style}'>{label}</div>", unsafe_allow_html=True)

    changed = False
    picked_orig = st.session_state.get("_queue_swap_pick")

    for pos, (_, row) in enumerate(filtered.iterrows(), start=1):
        orig_idx = int(row["orig_index"])
        atr_type = _queue_atr_label(row.get("ATR Type", ""))
        item_no = str(row["Item No"])
        title = str(row["Title"])
        mfg = str(row["Mfg Item"])
        status = str(row["Status"])
        done_by = str(row["Done By"])

        row_cols = st.columns([0.45, 1.05, 1.55, 3.0, 1.5, 1.25, 1.15, 0.95, 0.95])
        pos_style = "padding-top:0.55rem;color:#6f8090;font-weight:700;"
        if picked_orig == orig_idx:
            pos_style = "padding-top:0.55rem;color:#ef8e0d;font-weight:800;background:#fff7ed;border-radius:6px;padding-left:6px;"
        row_cols[0].markdown(f"<div style='{pos_style}'>{pos}</div>", unsafe_allow_html=True)
        row_cols[1].markdown(
            f"<div style='padding-top:0.55rem;color:#405166;'>{html.escape(atr_type)}</div>",
            unsafe_allow_html=True,
        )
        row_cols[2].markdown(
            f"<div style='padding-top:0.55rem;font-weight:700;color:#1a2330;'>{html.escape(item_no)}</div>",
            unsafe_allow_html=True,
        )
        row_cols[3].markdown(
            f"<div style='padding-top:0.55rem;'>{html.escape(title[:90])}</div>",
            unsafe_allow_html=True,
        )
        row_cols[4].markdown(
            f"<div style='padding-top:0.55rem;color:#6f8090;'>{html.escape(mfg)}</div>",
            unsafe_allow_html=True,
        )
        current_status = status if status in STATUS_OPTIONS else STATUS_OPTIONS[0]
        new_status = row_cols[5].selectbox(
            "status",
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(current_status),
            key=f"queue_status_{item_no}",
            label_visibility="collapsed",
        )
        new_done_by = row_cols[6].text_input(
            "done_by",
            value=done_by,
            key=f"queue_done_{item_no}",
            label_visibility="collapsed",
            placeholder="Done By",
        )
        if status != new_status:
            queue_df.at[orig_idx, "Status"] = new_status
            changed = True
        if done_by != new_done_by:
            queue_df.at[orig_idx, "Done By"] = new_done_by
            changed = True

        if row_cols[7].button("Preview", key=f"queue_preview_{item_no}", use_container_width=True):
            _preview_dialog(item_no)

        if reorder_mode:
            btn_label = "Pick" if picked_orig is None else ("Swap" if picked_orig != orig_idx else "Cancel")
            btn_type = "primary" if picked_orig == orig_idx else "secondary"
            if row_cols[8].button(btn_label, key=f"queue_reorder_{item_no}", type=btn_type, use_container_width=True):
                _handle_reorder_click(queue_df, orig_idx)
                st.rerun()
        else:
            if row_cols[8].button("Open", key=f"queue_open_{item_no}", type="primary", use_container_width=True):
                set_current_item(item_no)
                mark_status(item_no, "In Progress", new_done_by)
                st.session_state["active_page"] = "SKU Workspace"
                st.session_state["workspace_tab"] = "Content"
                st.rerun()

    if changed:
        st.session_state["queue_df"] = queue_df


def _render_downloads() -> None:
    with st.expander("Download", expanded=False):
        queue_df = st.session_state["queue_df"]
        items = st.session_state["items"]
        output_df = build_output_df(queue_df, items)
        input_df = build_input_sheet_df(queue_df, items)
        video_links_df = build_video_links_df(queue_df, items)

        xlsx_col, text_col = st.columns(2)
        excel_name = xlsx_col.text_input(
            "Excel file name",
            value=st.session_state.get("_queue_excel_filename", "Items Processed"),
            placeholder="Enter Excel file name",
            key="_queue_excel_filename",
        ).strip() or "Items Processed"
        text_name = text_col.text_input(
            "Text file name",
            value=st.session_state.get("_queue_text_filename", "Items Processed"),
            placeholder="Enter text file name",
            key="_queue_text_filename",
        ).strip() or "Items Processed"

        dl_xlsx, dl_text = st.columns(2)
        dl_xlsx.download_button(
            "Download Excel",
            data=excel_bytes(output_df, input_df, video_links_df),
            file_name=f"{excel_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        dl_text.download_button(
            "Download Text",
            data=text_bytes(output_df),
            file_name=f"{text_name}.txt",
            mime="text/plain",
            use_container_width=True,
        )


def _queue_atr_label(value) -> str:
    text = str(value or "").strip()
    return "" if text.lower().startswith("child of ") else text


@st.dialog("Product Preview", width="large")
def _preview_dialog(item_no: str) -> None:
    item = st.session_state.get("items", {}).get(item_no)
    if not item:
        st.warning("This SKU is not available for preview.")
        return
    if st.session_state.get("current_item_no") == item_no:
        sync_description_state(item)
    details = item.get("details", {})
    st.caption(f"SKU: {details.get('item_no', item_no)}")
    components.html(render_html(item, st.session_state["html_template"]), height=760, scrolling=True)


def _render_reorder_hint() -> None:
    picked = st.session_state.get("_queue_swap_pick")
    if picked is None:
        msg = "**Reorder mode:** click **Pick** on the row you want to move, then click **Swap** on the target row."
    else:
        msg = "**Reorder mode:** click **Swap** on the target row, or **Cancel** on the picked row to abort."
    st.info(msg, icon="<->")


def _handle_reorder_click(queue_df, clicked_orig_idx: int) -> None:
    picked = st.session_state.get("_queue_swap_pick")
    if picked is None:
        st.session_state["_queue_swap_pick"] = clicked_orig_idx
        return
    if picked == clicked_orig_idx:
        st.session_state.pop("_queue_swap_pick", None)
        return
    order = list(queue_df.index)
    if picked not in order or clicked_orig_idx not in order:
        st.session_state.pop("_queue_swap_pick", None)
        return
    order.remove(picked)
    insert_at = order.index(clicked_orig_idx)
    order.insert(insert_at, picked)
    new_df = queue_df.loc[order].reset_index(drop=True)
    st.session_state["queue_df"] = new_df
    st.session_state.pop("_queue_swap_pick", None)