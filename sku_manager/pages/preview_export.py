from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from sku_manager.services.export import build_output_df, excel_bytes, render_html
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
    blockers = submit_blockers(item)
    item_warning_list = item_warnings(details, item["features"], item["specs"], item["highlights"])

    if blockers:
        st.error("This SKU cannot be submitted yet. Complete the required fields:")
        for reason in blockers:
            st.markdown(f"- {reason}")
    elif item_warning_list:
        st.warning("Current item has non-blocking validation warnings.")
        for warning in item_warning_list:
            st.markdown(f"- {warning}", unsafe_allow_html=True)
    else:
        st.success("Current item is ready for submit/export.")
    fname_col, _ = st.columns([2, 1])
    export_filename = fname_col.text_input(
        "File name",
        value=st.session_state.get("_export_filename", "Items Processed"),
        placeholder="Enter file name (no extension needed)",
        key="_export_filename",
    ).strip() or "Items Processed"

    a, b, c = st.columns([1, 1, 1])
    submit_clicked = a.button(
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
    b.download_button(
        "Download Excel",
        data=excel_bytes(output_df),
        file_name=f"{export_filename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    c.download_button(
        "Download CSV",
        data=output_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{export_filename}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    tab_preview, tab_rows, tab_html = st.tabs(["Product Preview", "Output Rows", "HTML Template"])
    with tab_preview:
        html = render_html(item, st.session_state["html_template"])
        components.html(html, height=650, scrolling=True)
    with tab_rows:
        st.dataframe(output_df, width="stretch", hide_index=True)
    with tab_html:
        st.session_state["html_template"] = st.text_area(
            "HTML Template", value=st.session_state["html_template"], height=420
        )


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