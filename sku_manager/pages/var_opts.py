from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from sku_manager.services.variants import (
    parent_child_groups,
    variant_completeness,
)
from sku_manager.state import current_item
from sku_manager.ui.grid import stable_data_editor


def _variants_state() -> dict:
    return st.session_state.setdefault("variants", {})


def _group_for_current(groups: list[dict]) -> dict | None:
    """Return the parent group for the current SKU (matching the parent itself
    or one of its children)."""
    ino = str(st.session_state.get("current_item_no", ""))
    for group in groups:
        if group["parent_sku"] == ino:
            return group
    for group in groups:
        if any(child["sku"] == ino for child in group["children"]):
            return group
    return None


def render() -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return

    queue_df = st.session_state.get("queue_df")
    groups = parent_child_groups(queue_df)
    group = _group_for_current(groups)

    if group is None:
        st.info(
            "Variant Options apply to a parent SKU with child variants. "
            "This SKU has no children, so there is nothing to configure here."
        )
        return

    psku = group["parent_sku"]
    variants = _variants_state()
    entry = variants.setdefault(psku, {"attributes": [], "values": {}})
    attributes: list[str] = entry["attributes"]
    values: dict = entry["values"]

    # ── Parent header ────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:6px;">
          <span style="font-size:11px;font-weight:800;text-transform:uppercase;color:#6f8090;">Parent SKU</span>
          <span style="font-family:'JetBrains Mono',Consolas,monospace;font-weight:700;color:#1a2330;">{html.escape(psku)}</span>
          <span style="color:#405166;">{html.escape(group['parent_title'])}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{len(group['children'])} child SKU(s). Attributes below are shared by every child.")

    # ── Attribute manager ────────────────────────────────────────────────
    st.markdown('<h2 class="dv2-section-title">Attributes</h2>', unsafe_allow_html=True)
    if attributes:
        chip_cols = st.columns(min(len(attributes), 6))
        for i, attr in enumerate(list(attributes)):
            with chip_cols[i % len(chip_cols)]:
                if st.button(f"✕ {attr}", key=f"varopts_rmattr_{psku}_{attr}", use_container_width=True):
                    attributes.remove(attr)
                    for child_values in values.values():
                        child_values.pop(attr, None)
                    st.rerun()
    else:
        st.caption("No attributes yet — add one to start filling values.")

    add_col, btn_col = st.columns([3, 1])
    new_attr = add_col.text_input(
        "New attribute",
        key=f"varopts_newattr_{psku}",
        label_visibility="collapsed",
        placeholder="Add an attribute (e.g. Compatibility, Laptop Capacity)",
    )
    if btn_col.button("Add attribute", key=f"varopts_addattr_{psku}", use_container_width=True):
        name = new_attr.strip()
        if name and name not in attributes:
            attributes.append(name)
        st.session_state.pop(f"varopts_newattr_{psku}", None)
        st.rerun()

    # ── Children × attributes grid ───────────────────────────────────────
    st.markdown('<h2 class="dv2-section-title">Child Variants</h2>', unsafe_allow_html=True)
    if not attributes:
        st.info("Add at least one attribute above to enter values for the child SKUs.")
    else:
        child_names = {child["sku"]: child["title"] for child in group["children"]}
        data = []
        for child in group["children"]:
            csku = child["sku"]
            child_values = values.get(csku, {})
            row = {"Child SKU": csku, "Child Name": child_names[csku]}
            for attr in attributes:
                row[attr] = child_values.get(attr, "")
            data.append(row)
        df = pd.DataFrame(data, columns=["Child SKU", "Child Name", *attributes])

        col_config = {
            "Child SKU": st.column_config.TextColumn("Child SKU", disabled=True, width="medium"),
            "Child Name": st.column_config.TextColumn("Child Name", disabled=True, width="large"),
        }
        for attr in attributes:
            col_config[attr] = st.column_config.TextColumn(attr, width="medium")

        editor_key = f"varopts_editor_{psku}_{'|'.join(attributes)}"
        edited = stable_data_editor(
            df,
            key=editor_key,
            column_config=col_config,
            num_rows="fixed",
            width="stretch",
            hide_index=True,
        )

        for _, row in edited.iterrows():
            csku = str(row["Child SKU"])
            store = values.setdefault(csku, {})
            for attr in attributes:
                store[attr] = str(row.get(attr, "") or "").strip()

    # ── Completeness status (the download itself lives in the Work Queue) ─
    st.markdown('<h2 class="dv2-section-title">Status</h2>', unsafe_allow_html=True)
    complete, problems = variant_completeness(queue_df, variants)
    if complete:
        st.success(
            "All variant options are complete across the batch. "
            "Download the file from **Work Queue → Download**."
        )
    else:
        with st.expander(f"⚠ Incomplete ({len(problems)})", expanded=True):
            st.caption("Every child needs a non-empty value for each attribute before it can be exported:")
            for problem in problems:
                st.markdown(f"- {problem}")
