from __future__ import annotations

import pandas as pd
import streamlit as st

from sku_manager.services.text_rules import format_text
from sku_manager.services.validation import LIMITS, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import character_counter, reorder_editor, field_notes_editor, page_header, right_feedback_panel, source_video_panel
from sku_manager.ui.grid import reset_stable_data_editor, stable_data_editor


def render(show_header: bool = True, show_links: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return
    details = item["details"]
    if show_header:
        page_header("Item Details Extraction", "Specifications", status=details.get("item_no"))
    main, pane = st.columns([3.5, 1])

    with main:
        st.markdown("### Current Specifications")
        st.caption(
            "Edit specs directly in the table. Rows export with "
            "Value1 = category, Value2 = order (10/20/30…, auto), "
            "Value3 = group, Value4 = spec name, Value5 = spec value."
        )

        specs_list = item.setdefault("specs", [])
        _normalize_specs(specs_list)

        # Reserve the reorder control's spot above the grid, but fill it after
        # the editor writes the updated list (see features.py).
        reorder_slot = st.container()
        editor_key = f"specs_editor_{details['item_no']}"

        specs_df = pd.DataFrame(
            [
                {
                    "Value1 (Category)": s.get("category", ""),
                    "Value2 (Order)":    (idx + 1) * 10,
                    "Value3 (Group)":    s.get("group", ""),
                    "Value4 (Spec)":     s.get("Spec", ""),
                    "Value5 (Value)":    s.get("Value", ""),
                }
                for idx, s in enumerate(specs_list)
            ],
            columns=["Value1 (Category)", "Value2 (Order)", "Value3 (Group)", "Value4 (Spec)", "Value5 (Value)"],
        )
        edited = stable_data_editor(
            specs_df,
            num_rows="dynamic",
            width="stretch",
            key=editor_key,
            column_config={
                "Value1 (Category)": st.column_config.TextColumn("Value1 (Category)", width="medium"),
                "Value2 (Order)":    st.column_config.NumberColumn("Value2 (Order)", disabled=True, width="small"),
                "Value3 (Group)":    st.column_config.TextColumn("Value3 (Group)",    width="medium"),
                "Value4 (Spec)":     st.column_config.TextColumn("Value4 (Spec)",     width="medium"),
                "Value5 (Value)":    st.column_config.TextColumn("Value5 (Value)",    width="large"),
            },
        )
        rules_df = st.session_state["special_rules_df"]
        cleaned = []
        for _, row in edited.fillna("").iterrows():
            category = format_text(str(row.get("Value1 (Category)", "")), rules_df)
            group    = format_text(str(row.get("Value3 (Group)",    "")), rules_df)
            key      = format_text(str(row.get("Value4 (Spec)",     "")), rules_df)
            value    = format_text(str(row.get("Value5 (Value)",    "")), rules_df)
            if key or value or category or group:
                cleaned.append({"category": category, "group": group, "Spec": key, "Value": value})
        item["specs"] = cleaned

        with reorder_slot:
            current = item["specs"]
            if current:
                labels = [
                    f"{s.get('Spec', '') or '—'}: {s.get('Value', '') or ''}".strip(": ").strip()
                    or "(empty)"
                    for s in current
                ]
                perm = reorder_editor(labels, key=f"reorder_specs_{details['item_no']}")
                if perm is not None:
                    item["specs"] = [current[i] for i in perm]
                    reset_stable_data_editor(editor_key)
                    st.rerun()

        st.markdown("### Add Specification")
        c1, c2, c3, c4 = st.columns(4)
        new_category = c1.text_input("V1 Category", key=f"new_spec_cat_{details['item_no']}", placeholder="optional")
        new_group    = c2.text_input("V3 Group",    key=f"new_spec_grp_{details['item_no']}", placeholder="optional")
        with c3:
            new_key = st.text_input("V4 Spec", key=f"new_spec_key_{details['item_no']}", placeholder="e.g. Color")
            character_counter(new_key, LIMITS["spec_key"])
        with c4:
            new_value = st.text_input("V5 Value", key=f"new_spec_value_{details['item_no']}", placeholder="e.g. Matte Black")
            character_counter(new_value, LIMITS["spec_value"])
        st.markdown('<div class="vo-field-row-gap">&#8203;</div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        if a.button("Add Specification", width="stretch"):
            if new_key.strip() or new_value.strip() or new_category.strip() or new_group.strip():
                rules_df = st.session_state["special_rules_df"]
                item["specs"].append(
                    {
                        "category": format_text(new_category, rules_df),
                        "group":    format_text(new_group,    rules_df),
                        "Spec":     format_text(new_key,      rules_df),
                        "Value":    format_text(new_value,    rules_df),
                    }
                )
                st.rerun()
        if b.button("Clear Specifications", width="stretch"):
            item["specs"] = []
            st.rerun()
        bulk = st.text_area(
            "Paste multiple specs here (tab-separated per line: spec name → tab → value). "
            "Leave either side blank to add a value-only or label-only row.",
            height=160,
            placeholder="Color\tMatte Black\nWeight\t2.5 lbs\n\tValue with no label\nLabel with no value\t",
        )
        if st.button("Add Multiple Specifications", width="stretch"):
            item["specs"].extend(_parse_bulk_specs(bulk))
            st.rerun()
    with pane:
        if show_links:
            source_video_panel(item, key_suffix="specs_side", expanded=False)
            st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
        field_notes_editor(item, "specs", "Specification notes")
        st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
        right_feedback_panel(item, item_warnings(details, item["features"], item["specs"], item["highlights"]), key_prefix="specs_feedback")


def _normalize_specs(specs: list) -> None:
    for entry in specs:
        entry.setdefault("category", "")
        entry.setdefault("group", "")
        entry.setdefault("Spec", "")
        entry.setdefault("Value", "")


def _parse_bulk_specs(text: str) -> list[dict]:
    entries: list[dict] = []
    for raw in str(text).replace("\r", "\n").split("\n"):
        if not raw.strip() and "\t" not in raw:
            continue
        if "\t" in raw:
            key, value = raw.split("\t", 1)
        elif ":" in raw:
            key, value = raw.split(":", 1)
        else:
            key, value = raw, ""
        key = key.strip()
        value = value.strip()
        if not key and not value:
            continue
        entries.append({"category": "", "group": "", "Spec": key, "Value": value})
    return entries
