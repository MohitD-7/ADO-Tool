from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from sku_manager.services.category_mapping import display_path
from sku_manager.services.text_rules import flatten_cell_text, format_text
from sku_manager.services.validation import LIMITS, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import character_counter, field_notes_editor, page_header, right_feedback_panel, source_video_panel
from sku_manager.ui.grid import select_first_data_editor_cell


_SPEC_COLUMNS = ["Value1 (Category)", "Value2 (Order)", "Value3 (Group)", "Value4 (Spec)", "Value5 (Value)"]


def render(show_header: bool = True, show_links: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return
    details = item["details"]
    ino = details["item_no"]
    if show_header:
        page_header("Item Details Extraction", "Specifications", status=details.get("item_no"))
    main, pane = st.columns([3.5, 1])

    with main:
        st.markdown("### Current Specifications")
        category_path = str(details.get("category", "") or "")
        if category_path:
            st.caption(f"Category: {display_path(category_path)}")
        st.caption(
            "Edit specs in the table, use Value2 (Order) to reorder rows, then click Save Specs. "
            "Rows export with Value1 = category, Value2 = order (10/20/30..., auto), "
            "Value3 = group, Value4 = spec name, Value5 = spec value."
        )

        specs_list = item.setdefault("specs", [])
        _normalize_specs(specs_list)

        message_key = f"specs_save_message_{ino}"
        message = st.session_state.pop(message_key, "")
        if message:
            st.success(message)

        editor_key = _specs_editor_key(ino)
        specs_df = _specs_dataframe(specs_list)
        with st.form(f"specs_form_{ino}", clear_on_submit=False):
            edited = st.data_editor(
                specs_df,
                num_rows="dynamic",
                width="stretch",
                key=editor_key,
                hide_index=True,
                column_config={
                    "Value1 (Category)": st.column_config.TextColumn("Value1 (Category)", width="medium"),
                    "Value2 (Order)": st.column_config.NumberColumn(
                        "Value2 (Order)",
                        width="small",
                        step=10,
                        min_value=0,
                    ),
                    "Value3 (Group)": st.column_config.TextColumn("Value3 (Group)", width="medium"),
                    "Value4 (Spec)": st.column_config.TextColumn("Value4 (Spec)", width="medium"),
                    "Value5 (Value)": st.column_config.TextColumn("Value5 (Value)", width="large"),
                },
            )
            save_specs = st.form_submit_button("Save Specs", type="primary", use_container_width=True)
        select_first_data_editor_cell(editor_key)

        if save_specs:
            item["specs"] = _clean_specs_from_editor(edited, st.session_state["special_rules_df"])
            st.session_state[message_key] = f"Saved {len(item['specs'])} specification row(s)."
            bump_specs_editor(ino)
            st.rerun()

        st.markdown("### Add Specification")
        c1, c2, c3, c4 = st.columns(4)
        new_category = c1.text_input("V1 Category", key=f"new_spec_cat_{ino}", placeholder="optional")
        new_group = c2.text_input("V3 Group", key=f"new_spec_grp_{ino}", placeholder="optional")
        with c3:
            new_key = st.text_input("V4 Spec", key=f"new_spec_key_{ino}", placeholder="e.g. Color")
            character_counter(new_key, LIMITS["spec_key"])
        with c4:
            new_value = st.text_input("V5 Value", key=f"new_spec_value_{ino}", placeholder="e.g. Matte Black")
            character_counter(new_value, LIMITS["spec_value"])
        st.markdown('<div class="vo-field-row-gap">&#8203;</div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        if a.button("Add Specification", width="stretch"):
            if new_key.strip() or new_value.strip() or new_category.strip() or new_group.strip():
                rules_df = st.session_state["special_rules_df"]
                item["specs"].append(
                    {
                        "category": format_text(new_category, rules_df),
                        "group": format_text(new_group, rules_df),
                        "Spec": format_text(new_key, rules_df),
                        "Value": format_text(new_value, rules_df),
                    }
                )
                bump_specs_editor(ino)
                st.rerun()
        if b.button("Clear Specifications", width="stretch"):
            item["specs"] = []
            bump_specs_editor(ino)
            st.rerun()
        bulk = st.text_area(
            "Paste multiple specs here (tab-separated per line: spec name -> tab -> value). "
            "Leave either side blank to add a value-only or label-only row.",
            height=160,
            placeholder="Color\tMatte Black\nWeight\t2.5 lbs\n\tValue with no label\nLabel with no value\t",
        )
        if st.button("Add Multiple Specifications", width="stretch"):
            rules_df = st.session_state["special_rules_df"]
            item["specs"].extend(_format_specs(_parse_bulk_specs(bulk), rules_df))
            bump_specs_editor(ino)
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


def _specs_editor_key(item_no: str) -> str:
    rev_key = f"specs_editor_rev_{item_no}"
    revision = int(st.session_state.get(rev_key, 0))
    return f"specs_editor_{item_no}_{revision}"


def bump_specs_editor(item_no: str) -> None:
    rev_key = f"specs_editor_rev_{item_no}"
    st.session_state[rev_key] = int(st.session_state.get(rev_key, 0)) + 1


def _specs_dataframe(specs_list: list[dict]) -> pd.DataFrame:
    rows = [
        {
            "Value1 (Category)": s.get("category", ""),
            "Value2 (Order)": (idx + 1) * 10,
            "Value3 (Group)": s.get("group", ""),
            "Value4 (Spec)": s.get("Spec", ""),
            "Value5 (Value)": s.get("Value", ""),
        }
        for idx, s in enumerate(specs_list)
    ]
    # Always show one empty trailing row so the user can type directly without
    # having to click the '+' add-row button first.
    rows.append({
        "Value1 (Category)": "",
        "Value2 (Order)": None,
        "Value3 (Group)": "",
        "Value4 (Spec)": "",
        "Value5 (Value)": "",
    })
    return pd.DataFrame(rows, columns=_SPEC_COLUMNS)


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _order_value(value: Any, fallback_index: int) -> float:
    text = _clean_cell(value).strip()
    if not text:
        return float((fallback_index + 1) * 10)
    try:
        return float(text)
    except ValueError:
        return float((fallback_index + 1) * 10)


def _clean_specs_from_editor(edited: pd.DataFrame, rules_df) -> list[dict]:
    ordered: list[tuple[float, int, dict]] = []
    for position, (_, row) in enumerate(edited.iterrows()):
        raw_cells = {
            column: _clean_cell(row.get(column, ""))
            for column in ("Value1 (Category)", "Value3 (Group)", "Value4 (Spec)", "Value5 (Value)")
        }
        category = format_text(flatten_cell_text(raw_cells["Value1 (Category)"]), rules_df)
        group = format_text(flatten_cell_text(raw_cells["Value3 (Group)"]), rules_df)
        key = format_text(flatten_cell_text(raw_cells["Value4 (Spec)"]), rules_df)
        value = format_text(flatten_cell_text(raw_cells["Value5 (Value)"]), rules_df)
        if key or value or category or group:
            ordered.append((
                _order_value(row.get("Value2 (Order)", ""), position),
                position,
                {"category": category, "group": group, "Spec": key, "Value": value},
            ))
    return [record for _, _, record in sorted(ordered, key=lambda entry: (entry[0], entry[1]))]


def _format_specs(specs: list[dict], rules_df) -> list[dict]:
    return [
        {
            "category": format_text(spec.get("category", ""), rules_df),
            "group": format_text(spec.get("group", ""), rules_df),
            "Spec": format_text(spec.get("Spec", ""), rules_df),
            "Value": format_text(spec.get("Value", ""), rules_df),
        }
        for spec in specs
    ]


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
