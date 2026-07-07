from __future__ import annotations

import streamlit as st

from sku_manager.config import STATUS_OPTIONS
from sku_manager.state import mark_status, set_current_item
from sku_manager.ui.components import page_header


_SORT_OPTIONS = {
    "None (manual order)": None,
    "Item No":             "Item No",
    "Mfg Item":            "Mfg Item",
    "Title":               "Title",
    "Status":              "Status",
}


def render() -> None:
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

    st.subheader("Item Processing List")

    # ── Controls row: search / sort / reorder toggle ──────────────────
    ctrl1, ctrl2, ctrl3 = st.columns([3, 2, 1.6])
    with ctrl1:
        search = st.text_input("Search SKU or title", placeholder="Search SKUs, titles, mfg items…", label_visibility="collapsed")
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

    # ── Header row ───────────────────────────────────────────────────
    header_cols = st.columns([0.6, 1.9, 3.4, 1.9, 1.5, 1.3, 1.2])
    header_style = "font-size:11px;font-weight:800;text-transform:uppercase;color:#6f8090;padding-bottom:2px;border-bottom:1px solid #e2e8f0;"
    for col, label in zip(
        header_cols,
        ["#", "Item No", "Title", "Mfg Item", "Status", "Done By", ""],
    ):
        col.markdown(f"<div style='{header_style}'>{label}</div>", unsafe_allow_html=True)

    changed = False
    picked_orig = st.session_state.get("_queue_swap_pick")

    for pos, (_, row) in enumerate(filtered.iterrows(), start=1):
        orig_idx = int(row["orig_index"])
        item_no  = str(row["Item No"])
        title    = str(row["Title"])
        mfg      = str(row["Mfg Item"])
        status   = str(row["Status"])
        done_by  = str(row["Done By"])

        row_cols = st.columns([0.6, 1.9, 3.4, 1.9, 1.5, 1.3, 1.2])
        pos_style = "padding-top:0.55rem;color:#6f8090;font-weight:700;"
        if picked_orig == orig_idx:
            pos_style = "padding-top:0.55rem;color:#ef8e0d;font-weight:800;background:#fff7ed;border-radius:6px;padding-left:6px;"
        row_cols[0].markdown(f"<div style='{pos_style}'>{pos}</div>", unsafe_allow_html=True)
        row_cols[1].markdown(
            f"<div style='padding-top:0.55rem;font-weight:700;color:#1a2330;'>{item_no}</div>",
            unsafe_allow_html=True,
        )
        row_cols[2].markdown(
            f"<div style='padding-top:0.55rem;'>{title[:90]}</div>",
            unsafe_allow_html=True,
        )
        row_cols[3].markdown(
            f"<div style='padding-top:0.55rem;color:#6f8090;'>{mfg}</div>",
            unsafe_allow_html=True,
        )
        current_status = status if status in STATUS_OPTIONS else STATUS_OPTIONS[0]
        new_status = row_cols[4].selectbox(
            "status",
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(current_status),
            key=f"queue_status_{item_no}",
            label_visibility="collapsed",
        )
        new_done_by = row_cols[5].text_input(
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

        if reorder_mode:
            btn_label = "✓ Pick" if picked_orig is None else ("Swap here" if picked_orig != orig_idx else "Cancel")
            btn_type = "primary" if picked_orig == orig_idx else "secondary"
            if row_cols[6].button(btn_label, key=f"queue_reorder_{item_no}", type=btn_type, use_container_width=True):
                _handle_reorder_click(queue_df, orig_idx)
                st.rerun()
        else:
            if row_cols[6].button("Open", key=f"queue_open_{item_no}", type="primary", use_container_width=True):
                set_current_item(item_no)
                mark_status(item_no, "In Progress", new_done_by)
                st.session_state["active_page"] = "SKU Workspace"
                st.session_state["workspace_tab"] = "Content"
                st.rerun()

    if changed:
        st.session_state["queue_df"] = queue_df


def _render_reorder_hint() -> None:
    picked = st.session_state.get("_queue_swap_pick")
    if picked is None:
        msg = "**Reorder mode:** click **Pick** on the row you want to move, then click **Swap here** on the target row."
    else:
        msg = "**Reorder mode:** click **Swap here** on the target row, or **Cancel** on the picked row to abort."
    st.info(msg, icon="↕")


def _handle_reorder_click(queue_df, clicked_orig_idx: int) -> None:
    picked = st.session_state.get("_queue_swap_pick")
    if picked is None:
        st.session_state["_queue_swap_pick"] = clicked_orig_idx
        return
    if picked == clicked_orig_idx:
        st.session_state.pop("_queue_swap_pick", None)
        return
    # Move `picked` row to sit immediately before `clicked` position in the underlying order
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
