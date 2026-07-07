from __future__ import annotations

import pandas as pd
import streamlit as st

from sku_manager.services.text_rules import format_text, parse_lines
from sku_manager.services.validation import LIMITS, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import character_counter, drag_reorder, links_panel, page_header, right_feedback_panel


def render(show_header: bool = True, embedded: bool = False, show_links: bool = True, show_feedback: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return
    details = item["details"]
    if show_header:
        page_header("Item Details Extraction", "Features", status=details.get("item_no"))
    if embedded:
        main = st.container()
        pane = None
    else:
        main, pane = st.columns([3.5, 1])

    with main:
        st.markdown("### Current Features")
        st.caption("Edit feature text directly in the table below. Rows export with Value1 = 10, 20, 30… and Value2 = feature text.")

        features_list = item.setdefault("features", [])
        if features_list:
            with st.expander(f"Reorder ({len(features_list)} rows)", expanded=False):
                perm = drag_reorder([str(f) for f in features_list])
                if perm is not None:
                    item["features"] = [features_list[i] for i in perm]
                    st.rerun()

        feature_df = pd.DataFrame({"Feature": features_list})
        edited = st.data_editor(feature_df, num_rows="dynamic", width="stretch", key=f"features_editor_{details['item_no']}")
        item["features"] = [format_text(str(value), st.session_state["special_rules_df"]) for value in edited["Feature"].tolist() if str(value).strip()]
        st.markdown("### Add Feature")
        new_feature = st.text_input("Type a single feature and click Add Feature", key=f"new_feature_{details['item_no']}")
        character_counter(new_feature, LIMITS["feature"])
        st.markdown('<div class="vo-field-row-gap">&#8203;</div>', unsafe_allow_html=True)
        a, b, c = st.columns(3)
        if a.button("Add Feature", width="stretch"):
            if new_feature.strip():
                item["features"].append(format_text(new_feature, st.session_state["special_rules_df"]))
                st.rerun()
        if b.button("Copy Features to Highlights", width="stretch"):
            item["highlights"] = [feature for feature in item["features"] if len(feature) <= LIMITS["highlight"]][:8]
            st.rerun()
        if c.button("Clear Features", width="stretch"):
            item["features"] = []
            st.rerun()
        bulk = st.text_area("Paste multiple features here (one per line)", height=150, placeholder="One feature per line")
        if st.button("Add Multiple Features", width="stretch"):
            item["features"].extend(
                [format_text(line, st.session_state["special_rules_df"]) for line in parse_lines(bulk) if len(line) <= LIMITS["feature_bulk"]]
            )
            st.rerun()
    if show_links:
        links_panel(item, key_suffix="features")

    if show_feedback and pane is not None:
        with pane:
            right_feedback_panel(item, item_warnings(details, item["features"], item["specs"], item["highlights"]), key_prefix="features_feedback")
