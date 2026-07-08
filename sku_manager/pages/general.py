from __future__ import annotations

import html

import streamlit as st

from sku_manager.config import BATTERY_INFO_OPTIONS
from sku_manager.services.text_rules import format_text
from sku_manager.services.validation import LIMITS, char_count_status, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import field_notes_editor, hidden_notes, page_header, right_feedback_panel, source_video_panel


def _select_options(df, column: str) -> list[str]:
    if df.empty or column not in df.columns:
        return [""]
    values = [str(value).strip() for value in df[column].tolist() if str(value).strip()]
    return values or [""]


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
        cs_in, cs_btn = st.columns([5, 1])
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

        with b2:
            _dv2_label("Battery Material")
            materials = _select_options(st.session_state["battery_materials_df"], "Battery Material")
            details["battery_material"] = st.selectbox(
                "Battery Material", materials,
                index=materials.index(details.get("battery_material", materials[0]))
                    if details.get("battery_material", materials[0]) in materials else 0,
                disabled=battery_disabled,
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
            details["battery_type"] = st.selectbox(
                "Battery Type", types,
                index=types.index(details.get("battery_type", types[0]))
                    if details.get("battery_type", types[0]) in types else 0,
                disabled=battery_disabled,
                label_visibility="collapsed",
            )
        if show_links:
            st.markdown('<h2 class="dv2-section-title">Media &amp; References</h2>', unsafe_allow_html=True)
            source_video_panel(item, key_suffix="general_main", expanded=False)
        if show_format and st.button("Format Visible Text", key=f"format_all_{details['item_no']}",
                                     type="primary", use_container_width=True):
            rules_df = st.session_state["special_rules_df"]
            for key in ["title", "short_title", "mfg_model", "description"]:
                details[key] = format_text(details.get(key, ""), rules_df)
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
