from __future__ import annotations

import html

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from sku_manager.config import STATUS_OPTIONS
from sku_manager.services.export import (
    battery_excel_bytes,
    build_battery_df,
    build_input_sheet_df,
    build_output_df,
    build_video_links_df,
    build_warranty_export_df,
    excel_bytes,
    render_html,
    text_bytes,
    warranty_excel_bytes,
)
from sku_manager.services.relationships import (
    ROLE_CHILD,
    ROLE_OPTIONS,
    apply_relationships,
    current_relationships,
)
from sku_manager.services.variants import (
    build_variant_df,
    variant_completeness,
    variant_excel_bytes,
)
from sku_manager.state import mark_status, set_current_item, sync_description_state
from sku_manager.ui.components import page_header


_SORT_OPTIONS = {
    "None (manual order)": None,
    "Item No":             "Item No",
    "Mfg Item":            "Mfg Item",
    "Title":               "Title",
    "JIRA":                "JIRA",
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
    _render_relationship_editor()
    queue_df = st.session_state["queue_df"].copy()

    st.subheader("Item Processing List")

    ctrl1, ctrl2 = st.columns([3, 2])
    with ctrl1:
        search = st.text_input("Search SKU or title", placeholder="Search SKUs, titles, mfg items, JIRA...", label_visibility="collapsed")
    with ctrl2:
        sort_label = st.selectbox(
            "Sort by",
            list(_SORT_OPTIONS.keys()),
            index=0,
            label_visibility="collapsed",
        )

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

    header_cols = st.columns([0.45, 1.05, 1.55, 3.0, 1.2, 1.0, 0.8, 0.6])
    header_style = "font-size:11px;font-weight:800;text-transform:uppercase;color:#6f8090;padding-bottom:2px;border-bottom:1px solid #e2e8f0;"
    for col, label in zip(
        header_cols,
        ["#", "ATR", "Item No", "Title", "Status", "JIRA", "Preview", "Open"],
    ):
        col.markdown(f"<div style='{header_style}'>{label}</div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='height:10px;line-height:10px;font-size:0;'>&#8203;</div>",
        unsafe_allow_html=True,
    )

    changed = False

    for pos, (_, row) in enumerate(filtered.iterrows(), start=1):
        orig_idx = int(row["orig_index"])
        atr_type = _queue_atr_label(row.get("ATR Type", ""))
        is_child = str(row.get("ATR Type", "")).strip() == ""
        item_no = str(row["Item No"])
        title = str(row["Title"])
        status = str(row["Status"])
        jira = str(row.get("JIRA", ""))

        row_cols = st.columns(
            [0.45, 1.05, 1.55, 3.0, 1.2, 1.0, 0.8, 0.6],
            vertical_alignment="center",
        )
        pos_style = "color:#6f8090;font-weight:700;"
        row_cols[0].markdown(f"<div style='{pos_style}'>{pos}</div>", unsafe_allow_html=True)
        row_cols[1].markdown(
            f"<div style='color:#405166;'>{html.escape(atr_type)}</div>",
            unsafe_allow_html=True,
        )
        row_cols[2].markdown(
            f"<div style='font-weight:700;color:#1a2330;'>{html.escape(item_no)}</div>",
            unsafe_allow_html=True,
        )
        row_cols[3].markdown(
            f"<div style='color:#1a2330;'>{html.escape(title[:90])}</div>",
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
        row_cols[5].markdown(
            f"<div style='color:#405166;'>{html.escape(jira)}</div>",
            unsafe_allow_html=True,
        )
        if status != new_status:
            queue_df.at[orig_idx, "Status"] = new_status
            changed = True

        if row_cols[6].button(
            "Preview",
            key=f"queue_preview_{item_no}",
            use_container_width=True,
            disabled=is_child,
            help="Child variants are configured under Var Opts, not previewed individually." if is_child else None,
        ):
            _preview_dialog(item_no)

        if row_cols[7].button(
            "Open",
            key=f"queue_open_{item_no}",
            type="primary",
            use_container_width=True,
            disabled=is_child,
            help="Child variants are never worked on directly — use the parent's Var Opts tab." if is_child else None,
        ):
            set_current_item(item_no)
            mark_status(item_no, "In Progress")
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

        warranty_df = build_warranty_export_df(queue_df, items)
        dl_xlsx, dl_text = st.columns(2)
        dl_xlsx.download_button(
            "Download Excel",
            data=excel_bytes(output_df, input_df, video_links_df, warranty_df),
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

        st.markdown("---")
        st.markdown("### Warranty Export")
        warranty_rows = []
        for _, queue_row in queue_df.iterrows():
            item_no = str(queue_row["Item No"]).strip()
            if not item_no or item_no not in items:
                continue
            item = items[item_no]
            brand = item["details"].get("warranty_brand", "").strip()
            months = item["details"].get("warranty_months", "").strip()
            if brand:
                warranty_rows.append((item_no, brand, months))

        warranty_name = st.text_input(
            "Warranty file name",
            value=st.session_state.get("_queue_warranty_filename", "Warranty Data"),
            placeholder="Enter warranty file name",
            key="_queue_warranty_filename",
        ).strip() or "Warranty Data"

        if warranty_rows:
            import pandas as pd
            warranty_data = []
            warranty_master = st.session_state.get("warranty_df", pd.DataFrame())
            for item_no, brand, months in warranty_rows:
                if not warranty_master.empty:
                    brand_lower = brand.lower()
                    matched = warranty_master[warranty_master["Brand Name"].str.lower() == brand_lower]
                    if not matched.empty:
                        match = matched.iloc[0]
                        warranty_data.append({
                            "SKU": item_no,
                            "SKIP_Y_N": "N",
                            "MFG_CODE": match.get("Mfg Code", ""),
                            "DESCR": match.get("Warranty Description", ""),
                            "MO_PARTS": months,
                            "MO_LABOR": 0,
                            "URL": match.get("Warranty URL", ""),
                            "INT_PREFIX": "",
                            "PHONE#": match.get("Warranty Tel#", ""),
                            "EXTENSION": "",
                            "DISCONT": "",
                        })
            warranty_df = pd.DataFrame(warranty_data, columns=[
                "SKU", "SKIP_Y_N", "MFG_CODE", "DESCR", "MO_PARTS", "MO_LABOR",
                "URL", "INT_PREFIX", "PHONE#", "EXTENSION", "DISCONT"
            ]) if warranty_data else pd.DataFrame(columns=[
                "SKU", "SKIP_Y_N", "MFG_CODE", "DESCR", "MO_PARTS", "MO_LABOR",
                "URL", "INT_PREFIX", "PHONE#", "EXTENSION", "DISCONT"
            ])
            st.download_button(
                "Download Warranty Excel",
                data=warranty_excel_bytes(warranty_df) if not warranty_df.empty else b"",
                file_name=f"{warranty_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                disabled=warranty_df.empty,
            )
        else:
            st.caption("No SKUs with warranty information filled in yet.")

        st.markdown("---")
        st.markdown("### Variant Options Export")
        variants = st.session_state.get("variants", {})
        variant_df = build_variant_df(queue_df, variants)
        var_name = st.text_input(
            "Variant options file name",
            value=st.session_state.get("_queue_varopts_filename", "Variant Options"),
            placeholder="Enter variant options file name",
            key="_queue_varopts_filename",
        ).strip() or "Variant Options"
        if variant_df.empty:
            st.caption("No parent/child variant data in this batch.")
        else:
            complete, problems = variant_completeness(queue_df, variants)
            if not complete:
                st.caption(
                    f"{len(problems)} attribute value(s) still empty — complete them in the "
                    "Var Opts tab to enable this download."
                )
            st.download_button(
                "Download Variant Options",
                data=variant_excel_bytes(variant_df),
                file_name=f"{var_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                disabled=not complete,
            )

        st.markdown("---")
        st.markdown("### Battery Export")
        battery_df = build_battery_df(queue_df, items)
        battery_name = st.text_input(
            "Battery file name",
            value=st.session_state.get("_queue_battery_filename", "Battery Data"),
            placeholder="Enter battery file name",
            key="_queue_battery_filename",
        ).strip() or "Battery Data"
        if battery_df.empty:
            st.caption("No SKUs with battery information yet.")
        else:
            st.download_button(
                "Download Battery Excel",
                data=battery_excel_bytes(battery_df),
                file_name=f"{battery_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )


def _render_relationship_editor() -> None:
    queue_df = st.session_state["queue_df"]
    if queue_df.empty:
        return

    with st.expander("Edit Relationships (Parent / Child / Standalone)", expanded=False):
        message = st.session_state.pop("relationship_message", "")
        if message:
            st.success(message)
        for warning in st.session_state.pop("relationship_warnings", []):
            st.warning(warning)

        st.caption(
            "Change any SKU's role, pick the parent for each child, then click Apply. "
            "The queue reorders itself (children under their parent) and the Input sheet "
            "of the output Excel follows automatically."
        )

        records = current_relationships(queue_df)
        skus = [entry["item_no"] for entry in records]
        editor_df = pd.DataFrame(
            [
                {
                    "Item No": entry["item_no"],
                    "Title": entry["title"][:70],
                    "Role": entry["role"],
                    "Parent SKU": entry["parent_sku"],
                }
                for entry in records
            ]
        )

        rev = int(st.session_state.get("relationship_editor_rev", 0))
        with st.form(f"relationship_form_{rev}", clear_on_submit=False):
            edited = st.data_editor(
                editor_df,
                hide_index=True,
                width="stretch",
                key=f"relationship_editor_{rev}",
                disabled=["Item No", "Title"],
                column_config={
                    "Item No": st.column_config.TextColumn("Item No", width="small"),
                    "Title": st.column_config.TextColumn("Title", width="large"),
                    "Role": st.column_config.SelectboxColumn("Role", options=ROLE_OPTIONS, required=True, width="small"),
                    "Parent SKU": st.column_config.SelectboxColumn(
                        "Parent SKU (for Child rows)",
                        options=["", *skus],
                        width="medium",
                    ),
                },
            )
            applied = st.form_submit_button("Apply Relationship Changes", type="primary", use_container_width=True)

        if applied:
            assignments = {
                str(row["Item No"]): (
                    str(row.get("Role", "") or ""),
                    str(row.get("Parent SKU", "") or "") if str(row.get("Role", "")) == ROLE_CHILD else "",
                )
                for _, row in edited.iterrows()
            }
            new_queue, warnings = apply_relationships(queue_df, assignments)
            st.session_state["queue_df"] = new_queue
            items = st.session_state.get("items", {})
            for _, row in new_queue.iterrows():
                item = items.get(str(row["Item No"]).strip())
                if item:
                    item["details"]["atr_type"] = str(row["ATR Type"])
            st.session_state["relationship_message"] = "Relationships updated and queue reordered."
            st.session_state["relationship_warnings"] = warnings
            st.session_state["relationship_editor_rev"] = rev + 1
            st.rerun()


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


