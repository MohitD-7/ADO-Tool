from __future__ import annotations

import html

import streamlit as st

from sku_manager.config import BATTERY_INFO_OPTIONS
from sku_manager.services.category_mapping import (
    category_labels,
    category_paths,
    display_path,
    leaf_name,
    merge_template_into_specs,
)
from sku_manager.pages.specs import bump_specs_editor
from sku_manager.services.text_rules import format_text
from sku_manager.services.validation import LIMITS, char_count_status, item_warnings
from sku_manager.state import clone_item_from_similar, current_item, set_description_state
from sku_manager.ui.components import (
    brand_autocomplete,
    field_notes_editor,
    hidden_notes,
    page_header,
    right_feedback_panel,
    source_video_panel,
)


def _select_options(df, column: str) -> list[str]:
    if df.empty or column not in df.columns:
        return [""]
    values = [str(value).strip() for value in df[column].tolist() if str(value).strip()]
    return values or [""]


def _warranty_brand_options() -> list[str]:
    df = st.session_state.get("warranty_df")
    if df is None or df.empty or "Brand Name" not in df.columns:
        return []
    return sorted({str(value).strip() for value in df["Brand Name"].tolist() if str(value).strip()})


def _similar_to_source_options(current_item_no: str) -> list[str]:
    items = st.session_state.get("items", {})
    queue_df = st.session_state.get("queue_df")
    options: list[str] = []
    seen: set[str] = set()

    def row_is_available(row) -> bool:
        atr_type = str(row.get("ATR Type", "") or "").strip().lower()
        status = str(row.get("Status", "") or "").strip().lower()
        is_parent_or_standalone = atr_type == "standalone" or atr_type.startswith("parent")
        return is_parent_or_standalone and status == "completed"

    def add(item_no: str) -> None:
        item_no = str(item_no or "").strip()
        if not item_no or item_no == current_item_no or item_no in seen or item_no not in items:
            return
        options.append(item_no)
        seen.add(item_no)

    if queue_df is not None and not queue_df.empty and "Item No" in queue_df.columns:
        for _, row in queue_df.iterrows():
            if row_is_available(row):
                add(row.get("Item No", ""))
    return options


def _similar_to_labels(options: list[str]) -> dict[str, str]:
    labels: dict[str, str] = {}
    items = st.session_state.get("items", {})
    queue_df = st.session_state.get("queue_df")
    queue_titles: dict[str, str] = {}
    if queue_df is not None and not queue_df.empty and {"Item No", "Title"}.issubset(queue_df.columns):
        for _, row in queue_df.iterrows():
            item_no = str(row.get("Item No", "")).strip()
            if item_no and item_no not in queue_titles:
                queue_titles[item_no] = str(row.get("Title", "")).strip()

    for item_no in options:
        details = items.get(item_no, {}).get("details", {})
        title = str(details.get("title", "") or queue_titles.get(item_no, "")).strip()
        if len(title) > 90:
            title = f"{title[:87]}..."
        labels[item_no] = f"{item_no} - {title}" if title else item_no
    return labels


def _apply_similar_to(current_item_no: str, select_key: str) -> None:
    source_item_no = str(st.session_state.get(select_key, "") or "").strip()
    if not source_item_no:
        return
    if clone_item_from_similar(current_item_no, source_item_no):
        st.session_state[f"similar_to_message_{current_item_no}"] = f"Copied details from {source_item_no}."
    else:
        st.session_state[f"similar_to_error_{current_item_no}"] = "Could not copy details from the selected SKU."


def _render_similar_to_control(item: dict) -> None:
    details = item["details"]
    item_no = str(details.get("item_no", "")).strip()
    options = _similar_to_source_options(item_no)
    if not options:
        return

    message = st.session_state.pop(f"similar_to_message_{item_no}", "")
    if message:
        st.success(message)
    error = st.session_state.pop(f"similar_to_error_{item_no}", "")
    if error:
        st.error(error)

    labels = _similar_to_labels(options)
    select_key = f"similar_to_select_{item_no}"
    sku_col, action_col = st.columns([4, 1], vertical_alignment="bottom")
    with sku_col:
        _dv2_label("Source SKU")
        selected = st.selectbox(
            "Source SKU",
            ["", *options],
            key=select_key,
            format_func=lambda value: "Select SKU" if not value else labels.get(str(value), str(value)),
            label_visibility="collapsed",
        )
    with action_col:
        st.button(
            "Similar To",
            key=f"similar_to_button_{item_no}",
            disabled=not selected,
            on_click=_apply_similar_to,
            args=(item_no, select_key),
            use_container_width=True,
        )
    st.markdown('<div class="vo-field-row-gap">&#8203;</div>', unsafe_allow_html=True)


def _render_category_control(item: dict) -> None:
    details = item["details"]
    details.setdefault("category", "")
    item_no = str(details.get("item_no", "")).strip()
    current = str(details.get("category", "") or "")
    paths = category_paths()
    if not paths and not current:
        return

    options = ["", *paths]
    if current and current not in options:
        # Keep a previously saved category selectable even if its mapping rows were removed.
        options.append(current)
    labels = category_labels(paths)

    _dv2_label("Product Category (optional)")
    selected = st.selectbox(
        "Product Category",
        options,
        index=options.index(current),
        key=f"category_select_{item_no}",
        format_func=lambda value: "No category selected" if not value else labels.get(value, leaf_name(value)),
        label_visibility="collapsed",
    )

    if selected != current:
        details["category"] = selected
        if selected:
            added = merge_template_into_specs(item.setdefault("specs", []), selected)
            bump_specs_editor(item_no)
            if added:
                st.success(
                    f"Added {added} predefined spec row(s) for {leaf_name(selected)}. "
                    "Fill in the values on the Specs tab."
                )

    if selected:
        st.markdown(
            f'<div style="font-size:12px;color:#666;margin-top:2px;">'
            f'Taxonomy: <strong>{html.escape(display_path(selected))}</strong></div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="vo-field-row-gap">&#8203;</div>', unsafe_allow_html=True)


def _dv2_label(text: str, value: str | None = None, limit: int | None = None) -> None:
    """Render the mockup's label row: LABEL on the left, `47/150` counter on the right."""
    if value is not None and limit is not None:
        count, ok = char_count_status(value, limit)
        cls = "dv2-count" if ok else "dv2-count bad"
        st.markdown(
            f'<div class="dv2-label-row"><span>{html.escape(text)}</span>'
            f'<span class="{cls}">{count}/{limit}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="dv2-label-row"><span>{html.escape(text)}</span></div>',
            unsafe_allow_html=True,
        )


def render(show_header: bool = True, embedded: bool = False, show_links: bool = True, show_feedback: bool = True, show_format: bool = True, show_notes: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return

    details = item["details"]

    # When general.render() is called from the Workspace, the workspace top-bar
    # already rendered the dv2 header + tabs and opened the `.dv2` wrapper.
    # If someone calls it standalone (show_header=True), fall back to the
    # legacy header so we don't leave the page unstyled.
    if show_header:
        page_header("Editing SKU", details.get("title") or details.get("item_no", ""), status="In Progress")

    if embedded:
        main = st.container()
        pane = None
    else:
        main, pane = st.columns([3.5, 1])

    with main:
        _render_similar_to_control(item)
        _render_category_control(item)
        st.markdown('<h2 class="dv2-section-title">Basic Information</h2>', unsafe_allow_html=True)

        c_title, c_mpn = st.columns([2, 1])
        with c_title:
            _dv2_label("Title *", details.get("title", ""), LIMITS["title"])
            details["title"] = st.text_input(
                "Title", value=details.get("title", ""),
                key=f"title_{details['item_no']}",
                label_visibility="collapsed",
            )
        with c_mpn:
            _dv2_label("MFG Model / MPN", details.get("mfg_model", ""), LIMITS["mfg_model"])
            details["mfg_model"] = st.text_input(
                "MFG Model", value=details.get("mfg_model", ""),
                key=f"mfg_model_{details['item_no']}",
                label_visibility="collapsed",
            )
        # Short Title (full width) + Copy Title button aligned right
        short_title_key = f"short_title_{details['item_no']}"
        if short_title_key not in st.session_state:
            st.session_state[short_title_key] = details.get("short_title", "")

        def _copy_title() -> None:
            st.session_state[short_title_key] = details.get("title", "")
        _dv2_label(
            "Short Title (for mobile / tight spaces)",
            st.session_state.get(short_title_key, ""),
            LIMITS["short_title"],
        )
        cs_in, cs_btn = st.columns([5, 1], vertical_alignment="bottom")
        with cs_in:
            details["short_title"] = st.text_input(
                "Short Title", key=short_title_key,
                label_visibility="collapsed",
            )
        with cs_btn:
            st.button("Copy Title", key=f"copy_title_{details['item_no']}",
                      on_click=_copy_title, use_container_width=True)
        if show_notes and pane is None:
            hidden_notes(item, "title")

        # Warranty fields
        details.setdefault("warranty_brand", "")
        details.setdefault("warranty_months", "")
        wb_col, wm_col = st.columns(2)
        with wb_col:
            _dv2_label("Warranty Brand (optional)")
            brand_options = _warranty_brand_options()
            details["warranty_brand"] = brand_autocomplete(
                details.get("warranty_brand", ""),
                brand_options,
                key=f"warranty_brand_{details['item_no']}",
            )
            typed_brand = details["warranty_brand"].strip()
            if typed_brand:
                matched = any(typed_brand.lower() == b.lower() for b in brand_options)
                if matched:
                    st.markdown(
                        '<div style="color:#2a7a3a;font-size:12px;font-weight:700;margin-top:2px;">'
                        '&#9989; Matched in warranty master list</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div style="color:#c62828;font-size:12px;font-weight:700;margin-top:2px;">'
                        '&#9888; Not found in warranty master list</div>',
                        unsafe_allow_html=True,
                    )
        with wm_col:
            _dv2_label("Warranty Months (optional)")
            details["warranty_months"] = st.text_input(
                "Warranty Months", value=details.get("warranty_months", ""),
                key=f"warranty_months_{details['item_no']}",
                label_visibility="collapsed",
                placeholder="e.g., 12",
            )

        st.markdown('<h2 class="dv2-section-title">Battery &amp; Compliance</h2>', unsafe_allow_html=True)

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            _dv2_label("Battery Info")
            details["battery_info"] = st.selectbox(
                "Battery Info", BATTERY_INFO_OPTIONS,
                index=BATTERY_INFO_OPTIONS.index(details.get("battery_info", "no battery used"))
                    if details.get("battery_info", "no battery used") in BATTERY_INFO_OPTIONS else 0,
                label_visibility="collapsed",
            )
        battery_disabled = details["battery_info"] == "no battery used"
        if battery_disabled:
            details["battery_material"] = ""
            details["battery_quantity"] = ""
            details["battery_type"] = ""

        with b2:
            _dv2_label("Battery Material")
            materials = _select_options(st.session_state["battery_materials_df"], "Battery Material")
            if battery_disabled:
                st.text_input("Battery Material", value="", disabled=True, label_visibility="collapsed")
            else:
                details["battery_material"] = st.selectbox(
                    "Battery Material", materials,
                    index=materials.index(details.get("battery_material", materials[0]))
                        if details.get("battery_material", materials[0]) in materials else 0,
                    label_visibility="collapsed",
                )
        with b3:
            _dv2_label("Battery Quantity")
            details["battery_quantity"] = st.text_input(
                "Battery Quantity", value=details.get("battery_quantity", ""),
                disabled=battery_disabled,
                label_visibility="collapsed",
            )
        with b4:
            _dv2_label("Battery Type / Form")
            types = _select_options(st.session_state["battery_types_df"], "Battery Type")
            if battery_disabled:
                st.text_input("Battery Type", value="", disabled=True, label_visibility="collapsed")
            else:
                details["battery_type"] = st.selectbox(
                    "Battery Type", types,
                    index=types.index(details.get("battery_type", types[0]))
                        if details.get("battery_type", types[0]) in types else 0,
                    label_visibility="collapsed",
                )
        if show_format and st.button("Format Visible Text", key=f"format_all_{details['item_no']}",
                                     type="primary", use_container_width=True):
            rules_df = st.session_state["special_rules_df"]
            for key in ["title", "short_title", "mfg_model", "description"]:
                details[key] = format_text(details.get(key, ""), rules_df)
            set_description_state(details["item_no"], details.get("description", ""))
            for entry in item.setdefault("includes", []):
                if entry.get("text"):
                    entry["text"] = format_text(entry["text"], rules_df)
            item["features"]   = [format_text(str(f), rules_df) for f in item.get("features", [])]
            item["highlights"] = [format_text(str(h), rules_df) for h in item.get("highlights", [])]
            for spec in item.get("specs", []):
                spec["Spec"]  = format_text(str(spec.get("Spec",  "") or ""), rules_df)
                spec["Value"] = format_text(str(spec.get("Value", "") or ""), rules_df)
            st.rerun()


    if show_feedback and pane is not None:
        with pane:
            if show_notes:
                field_notes_editor(item, "title", "Basic information notes")
                st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            right_feedback_panel(
                item,
                item_warnings(details, item["features"], item["specs"], item["highlights"]),
                key_prefix="general_feedback",
            )
            if show_links:
                st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
                st.markdown('<h2 class="dv2-section-title">Media &amp; References</h2>', unsafe_allow_html=True)
                source_video_panel(item, key_suffix="general_main", expanded=False)
