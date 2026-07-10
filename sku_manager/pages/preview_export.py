from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from sku_manager.services.export import (
    build_input_sheet_df,
    build_output_df,
    build_video_links_df,
    build_warranty_export_df,
    excel_bytes,
    render_html,
    text_bytes,
)
from sku_manager.services.validation import item_warnings, submit_blockers
from sku_manager.state import current_item, mark_status, sync_description_state
from sku_manager.ui.components import page_header


def render(show_header: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return

    sync_description_state(item)
    details = item["details"]
    ino = details.get("item_no", "")
    if show_header:
        page_header("Final Review", "Batch Summary & Export", status=ino)

    # Post-submit success screen
    if st.session_state.get("_submitted_ino") == ino:
        _render_submit_success(ino)
        return

    output_df = build_output_df(st.session_state["queue_df"], st.session_state["items"])
    input_df = build_input_sheet_df(st.session_state["queue_df"], st.session_state["items"])
    video_links_df = build_video_links_df(st.session_state["queue_df"], st.session_state["items"])
    blockers = submit_blockers(item)
    item_warning_list = item_warnings(details, item["features"], item["specs"], item["highlights"])

    if blockers:
        with st.expander(f"⚠ Not filled / required ({len(blockers)})", expanded=False):
            st.caption("This SKU cannot be submitted yet. Complete the required fields:")
            for reason in blockers:
                st.markdown(f"- {reason}")
    elif item_warning_list:
        with st.expander(f"⚠ Warnings — not filled ({len(item_warning_list)})", expanded=False):
            st.caption("Non-blocking validation warnings:")
            for warning in item_warning_list:
                st.markdown(f"- {warning}", unsafe_allow_html=True)
    else:
        st.success("Current item is ready for submit/export.")
    submit_col, _ = st.columns([1, 2])
    submit_clicked = submit_col.button(
        "Submit Current Item",
        type="primary",
        use_container_width=True,
    )
    if submit_clicked:
        if blockers:
            _confirm_submit_dialog(ino, blockers)
        else:
            mark_status(ino, "Completed")
            st.session_state["_submitted_ino"] = ino
            st.rerun()

    with st.expander("Download", expanded=False):
        xlsx_col, txt_col = st.columns(2)
        excel_filename = xlsx_col.text_input(
            "Excel file name",
            value=st.session_state.get("_export_excel_filename", "Items Processed"),
            placeholder="Enter Excel file name (no extension needed)",
            key="_export_excel_filename",
        ).strip() or "Items Processed"
        text_filename = txt_col.text_input(
            "Text file name",
            value=st.session_state.get("_export_text_filename", "Items Processed"),
            placeholder="Enter text file name (no extension needed)",
            key="_export_text_filename",
        ).strip() or "Items Processed"

        warranty_df = build_warranty_export_df(st.session_state["queue_df"], st.session_state["items"])
        dl_xlsx, dl_text = st.columns(2)
        dl_xlsx.download_button(
            "Download Excel",
            data=excel_bytes(output_df, input_df, video_links_df, warranty_df),
            file_name=f"{excel_filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        dl_text.download_button(
            "Download Text",
            data=text_bytes(output_df),
            file_name=f"{text_filename}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    tab_preview, tab_rows, tab_html = st.tabs(["Product Preview", "Output Rows", "HTML Template"])
    with tab_preview:
        html = render_html(item, st.session_state["html_template"])
        if st.button("⛶ Full screen", key="_preview_fullscreen_btn", use_container_width=False):
            _fullscreen_preview_dialog(html)
        components.html(html, height=650, scrolling=True)
    with tab_rows:
        st.dataframe(output_df, width="stretch", hide_index=True)
    with tab_html:
        st.session_state["html_template"] = st.text_area(
            "HTML Template", value=st.session_state["html_template"], height=420
        )


@st.dialog("Product Preview", width="large")
def _fullscreen_preview_dialog(html: str) -> None:
    components.html(html, height=760, scrolling=True)


@st.dialog("Cannot submit — required fields missing")
def _confirm_submit_dialog(ino: str, blockers: list[str]) -> None:
    st.markdown(
        f"**SKU {ino}** is missing the following required fields:"
    )
    for reason in blockers:
        st.markdown(f"- {reason}")
    st.markdown("---")
    st.caption(
        "You can go back and complete these fields, or submit anyway and leave them empty."
    )
    c1, c2 = st.columns(2)
    if c1.button("OK", use_container_width=True):
        st.rerun()
    if c2.button("Submit Anyway", type="primary", use_container_width=True):
        mark_status(ino, "Completed")
        st.session_state["_submitted_ino"] = ino
        st.rerun()


def _render_submit_success(ino: str) -> None:
    st.markdown(
        f"""
        <div style="background:#f0faf3;border:2px solid #7cba8c;border-left:6px solid #2e8b57;
             border-radius:10px;padding:1.4rem 1.6rem;margin:1rem 0;text-align:center;">
          <div style="font-size:2rem;">✓</div>
          <div style="font-weight:800;font-size:1.15rem;color:#1b5e30;margin-top:.3rem;">
            SKU {ino} submitted successfully
          </div>
          <div style="color:#396b48;font-size:.9rem;margin-top:.35rem;">
            Status set to <strong>Completed</strong>. Click Continue to pick the next SKU from the work queue.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("Continue to Work Queue", type="primary", use_container_width=True):
        st.session_state.pop("_submitted_ino", None)
        st.session_state["active_page"] = "SKU Batch"
        st.rerun()
    if c2.button("Stay on Review", use_container_width=True):
        st.session_state.pop("_submitted_ino", None)
        st.rerun()