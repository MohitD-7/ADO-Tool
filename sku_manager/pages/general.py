from __future__ import annotations

import streamlit as st

from sku_manager.config import BATTERY_INFO_OPTIONS
from sku_manager.services.text_rules import format_text
from sku_manager.services.validation import LIMITS, item_warnings
from sku_manager.state import current_item
from sku_manager.ui.components import character_counter, hidden_notes, links_panel, page_header, right_feedback_panel


def _select_options(df, column: str) -> list[str]:
    if df.empty or column not in df.columns:
        return [""]
    values = [str(value).strip() for value in df[column].tolist() if str(value).strip()]
    return values or [""]


def render(show_header: bool = True) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return

    details = item["details"]
    if show_header:
        page_header("Editing SKU", details.get("title") or details.get("item_no", ""), status="In Progress")
    main, pane = st.columns([3.5, 1])

    with main:
        # ── Identity section ──────────────────────────────────────────
        st.markdown(
            '<div style="background:#fff;border:1px solid #dde3ea;border-left:4px solid #2f6f73;border-radius:8px;padding:0.5rem 0.8rem 0.4rem 0.8rem;margin-bottom:0.4rem;">',
            unsafe_allow_html=True,
        )
        st.markdown("### Identity")

        title = st.text_input("Product Title", value=details.get("title", ""), key=f"title_{details['item_no']}")
        details["title"] = title
        character_counter(title, LIMITS["title"])
        hidden_notes(item, "title")

        c1, c2 = st.columns([3, 1])
        with c1:
            details["short_title"] = st.text_input("Short Title", value=details.get("short_title", ""), key=f"short_title_{details['item_no']}")
            character_counter(details["short_title"], LIMITS["short_title"])
        with c2:
            if st.button("Copy Title", width="stretch"):
                details["short_title"] = details["title"]
                st.rerun()

        c3, c4 = st.columns(2)
        with c3:
            st.text_input("Item No (read-only)", value=details.get("item_no", ""), disabled=True)
            details["mfg_model"] = st.text_input("Mfg Model", value=details.get("mfg_model", ""), key=f"mfg_model_{details['item_no']}")
            character_counter(details["mfg_model"], LIMITS["mfg_model"])
        with c4:
            st.text_input("Mfg Item (read-only)", value=details.get("mfg_item", ""), disabled=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Battery section ───────────────────────────────────────────
        st.markdown(
            '<div style="background:#fff;border:1px solid #dde3ea;border-left:4px solid #f28c00;border-radius:8px;padding:0.5rem 0.8rem 0.4rem 0.8rem;margin-bottom:0.4rem;">',
            unsafe_allow_html=True,
        )
        st.markdown("### Battery Information")
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            details["battery_info"] = st.selectbox(
                "Battery Info",
                BATTERY_INFO_OPTIONS,
                index=BATTERY_INFO_OPTIONS.index(details.get("battery_info", "no battery used")) if details.get("battery_info", "no battery used") in BATTERY_INFO_OPTIONS else 0,
            )
        with b2:
            materials = _select_options(st.session_state["battery_materials_df"], "Battery Material")
            details["battery_material"] = st.selectbox("Battery Material", materials, index=materials.index(details.get("battery_material", materials[0])) if details.get("battery_material", materials[0]) in materials else 0)
        with b3:
            details["battery_quantity"] = st.text_input("Battery Quantity", value=details.get("battery_quantity", ""), disabled=details["battery_info"] == "no battery used")
        with b4:
            types = _select_options(st.session_state["battery_types_df"], "Battery Type")
            details["battery_type"] = st.selectbox("Battery Type", types, index=types.index(details.get("battery_type", types[0])) if details.get("battery_type", types[0]) in types else 0)
        st.markdown("</div>", unsafe_allow_html=True)

        if st.button("Format Visible Text", width="stretch"):
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

        links_panel(item)

    with pane:
        right_feedback_panel(item, item_warnings(details, item["features"], item["specs"], item["highlights"]), key_prefix="general_feedback")
