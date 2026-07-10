from __future__ import annotations

import pandas as pd
import streamlit as st

from sku_manager.services.text_rules import format_text, parse_lines
from sku_manager.services.validation import LIMITS, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import reorder_editor, field_notes_editor, page_header, right_feedback_panel, source_video_panel
from sku_manager.ui.grid import reset_stable_data_editor, stable_data_editor


def render(show_header: bool = True, embedded: bool = False, show_links: bool = True, show_feedback: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return
    details = item["details"]
    ino = details["item_no"]
    if show_header:
        page_header("Item Details Extraction", "Highlights", status=details.get("item_no"))
    if embedded:
        main = st.container()
        pane = None
    else:
        main, pane = st.columns([3.5, 1])

    with main:
        with st.expander("Highlights", expanded=False):
            if st.button("Copy Features", width="stretch", key=f"copy_features_to_highlights_{ino}"):
                item["highlights"] = [str(feature) for feature in item.get("features", []) if str(feature).strip()]
                st.rerun()

            st.markdown("### Current Highlights")
            st.caption("Max 8 highlights. Rows export with Value1 = 10, 20, 30..., Value2 = highlight text, Value3 = PDP.")

            highlights_list = item.setdefault("highlights", [])
            # Reserve the reorder control's spot above the grid, but fill it
            # after the editor writes the updated list (see features.py).
            reorder_slot = st.container()

            highlight_df = pd.DataFrame({"Highlight": highlights_list})
            editor_key = f"highlights_editor_{ino}"
            edited = stable_data_editor(
                highlight_df,
                num_rows="dynamic",
                width="stretch",
                key=editor_key,
            )
            item["highlights"] = [
                format_text(str(value), st.session_state["special_rules_df"])
                for value in edited["Highlight"].tolist()
                if str(value).strip()
            ]

            with reorder_slot:
                current = item["highlights"]
                if current:
                    perm = reorder_editor([str(h) for h in current], key=f"reorder_highlights_{ino}")
                    if perm is not None:
                        item["highlights"] = [current[i] for i in perm]
                        reset_stable_data_editor(editor_key)
                        st.rerun()

            st.markdown("### Add Highlights in Bulk")
            bulk = st.text_area(
                "Paste multiple highlights here (one per line)",
                height=150,
                placeholder="One highlight per line",
                key=f"highlights_bulk_{ino}",
            )
            if st.button("Add Multiple Highlights", width="stretch", key=f"add_bulk_highlights_{ino}"):
                item["highlights"].extend(
                    [
                        format_text(line, st.session_state["special_rules_df"])
                        for line in parse_lines(bulk)
                        if len(line) <= LIMITS["highlight_bulk"]
                    ]
                )
                item["highlights"] = item["highlights"][:8]
                st.rerun()

    if show_feedback and pane is not None:
        with pane:
            if show_links:
                source_video_panel(item, key_suffix="highlights_side", expanded=False)
                st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            field_notes_editor(item, "highlights", "PDP highlight notes")
            st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            right_feedback_panel(item, item_warnings(details, item["features"], item["specs"], item["highlights"]), key_prefix="highlights_feedback")