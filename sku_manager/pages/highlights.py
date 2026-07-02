from __future__ import annotations

import pandas as pd
import streamlit as st

from sku_manager.services.text_rules import format_text, parse_lines
from sku_manager.services.validation import LIMITS, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import drag_reorder, links_panel, page_header, right_feedback_panel


def render(show_header: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return
    details = item["details"]
    if show_header:
        page_header("Item Details Extraction", "Highlights", status=details.get("item_no"))
    main, pane = st.columns([3.5, 1])

    with main:
        st.markdown(
            '<div style="background:#fff;border:1px solid #dde3ea;border-left:4px solid #2f6f73;border-radius:8px;padding:0.5rem 0.8rem 0.4rem 0.8rem;margin-bottom:0.4rem;">',
            unsafe_allow_html=True,
        )
        st.markdown("### Current Highlights")
        st.caption("Max 8 highlights. Rows export with Value1 = 10, 20, 30…, Value2 = highlight text, Value3 = PDP.")

        highlights_list = item.setdefault("highlights", [])
        if highlights_list:
            with st.expander(f"Reorder ({len(highlights_list)} rows)", expanded=False):
                perm = drag_reorder([str(h) for h in highlights_list])
                if perm is not None:
                    item["highlights"] = [highlights_list[i] for i in perm]
                    st.rerun()

        highlight_df = pd.DataFrame({"Highlight": highlights_list})
        edited = st.data_editor(highlight_df, num_rows="dynamic", width="stretch", key=f"highlights_editor_{details['item_no']}")
        item["highlights"] = [format_text(str(value), st.session_state["special_rules_df"]) for value in edited["Highlight"].tolist() if str(value).strip()]
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            '<div style="background:#fff;border:1px solid #dde3ea;border-left:4px solid #f28c00;border-radius:8px;padding:0.5rem 0.8rem 0.4rem 0.8rem;margin-bottom:0.4rem;">',
            unsafe_allow_html=True,
        )
        st.markdown("### Add Highlights in Bulk")
        bulk = st.text_area("Paste multiple highlights here (one per line)", height=150, placeholder="One highlight per line")
        if st.button("Add Multiple Highlights", width="stretch"):
            item["highlights"].extend(
                [format_text(line, st.session_state["special_rules_df"]) for line in parse_lines(bulk) if len(line) <= LIMITS["highlight_bulk"]]
            )
            item["highlights"] = item["highlights"][:8]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    links_panel(item, key_suffix="highlights")

    with pane:
        right_feedback_panel(item, item_warnings(details, item["features"], item["specs"], item["highlights"]), key_prefix="highlights_feedback")
