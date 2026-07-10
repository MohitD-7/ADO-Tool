from __future__ import annotations

import pandas as pd
import streamlit as st

from sku_manager.services.text_rules import format_text, parse_lines
from sku_manager.services.validation import LIMITS, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import character_counter, reorder_editor, field_notes_editor, page_header, right_feedback_panel, source_video_panel


def render(show_header: bool = True, embedded: bool = False, show_links: bool = True, show_feedback: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return
    details = item["details"]
    ino = details["item_no"]
    if show_header:
        page_header("Item Details Extraction", "Features", status=details.get("item_no"))
    if embedded:
        main = st.container()
        pane = None
    else:
        main, pane = st.columns([3.5, 1])

    with main:
        st.markdown("### Current Features")
        st.caption("Edit feature text directly in the table below. Rows export with Value1 = 10, 20, 30... and Value2 = feature text.")

        features_list = item.setdefault("features", [])
        # Reserve the reorder control's spot above the grid, but fill it *after*
        # the editor below has written the updated list — otherwise a row just
        # added in the grid wouldn't appear here until the next rerun.
        reorder_slot = st.container()

        feature_df = pd.DataFrame({"Feature": features_list})
        edited = st.data_editor(
            feature_df,
            num_rows="dynamic",
            width="stretch",
            key=f"features_editor_{ino}",
        )
        item["features"] = [
            format_text(str(value), st.session_state["special_rules_df"])
            for value in edited["Feature"].tolist()
            if str(value).strip()
        ]

        with reorder_slot:
            current = item["features"]
            if current:
                perm = reorder_editor([str(f) for f in current], key=f"reorder_features_{ino}")
                if perm is not None:
                    item["features"] = [current[i] for i in perm]
                    st.session_state.pop(f"features_editor_{ino}", None)
                    st.rerun()

        with st.expander("Add Feature", expanded=False):
            st.markdown("#### Single feature")
            new_feature = st.text_input(
                "Type a single feature and click Add Feature",
                key=f"new_feature_{ino}",
            )
            character_counter(new_feature, LIMITS["feature"])
            st.markdown('<div class="vo-field-row-gap">&#8203;</div>', unsafe_allow_html=True)
            single_a, single_b = st.columns(2)
            if single_a.button("Add Feature", width="stretch", key=f"add_feature_{ino}"):
                if new_feature.strip():
                    item["features"].append(format_text(new_feature, st.session_state["special_rules_df"]))
                    st.rerun()
            if single_b.button("Clear Features", width="stretch", key=f"clear_features_{ino}"):
                item["features"] = []
                st.rerun()

            st.markdown("#### Bulk features")
            bulk = st.text_area(
                "Paste multiple features here (one per line)",
                height=150,
                placeholder="One feature per line",
                key=f"features_bulk_{ino}",
            )
            if st.button("Add Multiple Features", width="stretch", key=f"add_bulk_features_{ino}"):
                item["features"].extend(
                    [
                        format_text(line, st.session_state["special_rules_df"])
                        for line in parse_lines(bulk)
                        if len(line) <= LIMITS["feature_bulk"]
                    ]
                )
                st.rerun()

    if show_feedback and pane is not None:
        with pane:
            if show_links:
                source_video_panel(item, key_suffix="features_side", expanded=False)
                st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            field_notes_editor(item, "features", "Feature bullet notes")
            st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            right_feedback_panel(item, item_warnings(details, item["features"], item["specs"], item["highlights"]), key_prefix="features_feedback")