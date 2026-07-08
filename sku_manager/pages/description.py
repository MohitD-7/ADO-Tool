from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from sku_manager.services.text_rules import format_text, parse_lines
from sku_manager.services.validation import item_warnings
from sku_manager.state import current_item, description_state_keys, sync_description_state
from sku_manager.ui.components import drag_reorder, field_notes_editor, page_header, source_video_panel
from sku_manager.ui.editor import html_editor


def render(
    show_header: bool = True,
    show_links: bool = True,
    show_validation: bool = True,
    show_item_notes: bool = True,
    show_notes: bool = True,
    show_description: bool = True,
    show_includes: bool = True,
) -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return

    sync_description_state(item)
    details = item["details"]
    ino = details["item_no"]
    sync_key, _, force_key = description_state_keys(ino)

    if show_header:
        page_header("Content Layer", "Description and Includes", status=ino)

    use_side_pane = show_notes or show_links or show_validation or show_item_notes
    if use_side_pane:
        main, pane = st.columns([3.5, 1])
    else:
        main = st.container()
        pane = None

    with main:
        if show_description:
            th1, th2 = st.columns([5, 1])
            with th1:
                st.markdown("### Product Description")
                st.caption("Use the toolbar to insert HTML tags. Type directly in HTML.")
            with th2:
                st.markdown('<div class="vo-spacer-btn">&#8203;</div>', unsafe_allow_html=True)
                fmt_click = st.button("Format Visible Text", use_container_width=True, key=f"fmt_all_{ino}")

            details["description"] = html_editor(
                value=details.get("description", ""),
                sync_key=sync_key,
                height=320,
            )

            if fmt_click:
                current = sync_description_state(item)
                rules_df = st.session_state["special_rules_df"]
                for key in ["title", "short_title", "mfg_model", "description"]:
                    details[key] = format_text(details.get(key, ""), rules_df)
                details["description"] = format_text(current, rules_df)
                st.session_state[force_key] = details["description"]
                for entry in item.setdefault("includes", []):
                    if entry.get("text"):
                        entry["text"] = format_text(entry["text"], rules_df)
                item["features"] = [format_text(str(f), rules_df) for f in item.get("features", [])]
                item["highlights"] = [format_text(str(h), rules_df) for h in item.get("highlights", [])]
                for spec in item.get("specs", []):
                    spec["Spec"] = format_text(str(spec.get("Spec", "") or ""), rules_df)
                    spec["Value"] = format_text(str(spec.get("Value", "") or ""), rules_df)
                st.rerun()

        if show_includes:
            st.markdown("### Includes / Box Contents")
            item.setdefault("includes", [])
            _render_includes_editor(item, ino, item["includes"])
            _render_includes_bulk(item, ino)

    warnings = item_warnings(
        details,
        item["features"],
        item["specs"],
        item["highlights"],
        st.session_state.get("special_rules_df"),
        includes=item.get("includes", []),
    )

    if pane is not None:
        with pane:
            if show_links:
                source_video_panel(item, key_suffix="description_side", expanded=False)
                st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            if show_notes and show_description:
                field_notes_editor(item, "description", "Product description notes")
                st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            if show_notes and show_includes:
                field_notes_editor(item, "includes", "Includes / box contents notes")
                st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
            if show_validation and warnings:
                with st.expander(
                    f"Validation ({len(warnings)} warning{'s' if len(warnings) != 1 else ''})",
                    expanded=True,
                ):
                    for warning in warnings:
                        st.markdown(f'<div class="vo-warning">{warning}</div>', unsafe_allow_html=True)
            if show_item_notes:
                with st.expander("Item notes", expanded=False):
                    item["details"]["comments"] = st.text_area(
                        "Item-level comment",
                        value=item["details"].get("comments", ""),
                        key=f"desc_item_comment_{ino}",
                        height=80,
                    )

def _render_includes_editor(item: dict, ino: str, includes_list: list[dict]) -> None:
    st.caption(
        "Edit include rows below. Rows export with Value1 = 10, 20, 30… "
        "Fill **Value2 (Text)** OR **Value3 (SKU)** per row, not both."
    )
    if includes_list:
        with st.expander(f"Reorder ({len(includes_list)} rows)", expanded=False):
            labels = [
                (str(e.get("text", "") or "").strip() or f"SKU {str(e.get('sku', '') or '').strip()}")
                for e in includes_list
            ]
            perm = drag_reorder(labels)
            if perm is not None:
                item["includes"] = [includes_list[i] for i in perm]
                st.rerun()
    df = pd.DataFrame(
        [
            {
                "Value2 (Text)": str(entry.get("text", "") or ""),
                "Value3 (SKU)":  str(entry.get("sku", "") or ""),
            }
            for entry in includes_list
        ],
        columns=["Value2 (Text)", "Value3 (SKU)"],
    )
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        width="stretch",
        key=f"includes_editor_{ino}",
        column_config={
            "Value2 (Text)": st.column_config.TextColumn("Value2 (Text)", width="large"),
            "Value3 (SKU)":  st.column_config.TextColumn("Value3 (SKU)",  width="medium"),
        },
    )

    new_list: list[dict] = []
    for _, row in edited.iterrows():
        text = str(row.get("Value2 (Text)", "") or "").strip()
        sku = str(row.get("Value3 (SKU)", "") or "").strip()
        if not text and not sku:
            continue
        if text and sku:
            sku = ""
        new_list.append({"text": text, "sku": sku})
    item["includes"] = new_list


def _render_includes_bulk(item: dict, ino: str) -> None:
    with st.expander("Add includes in bulk", expanded=False):
        st.caption(
            "One include per line. Use **Tab** to separate text from SKU — "
            "leave one side blank. Copy two columns from Excel and paste here to fill both."
        )
        bulk_label = "Paste includes"
        bulk = st.text_area(
            bulk_label,
            height=140,
            placeholder="Text include line\n<Tab>SKU-only line\nText\tignored-if-both",
            key=f"inc_bulk_{ino}",
            label_visibility="collapsed",
        )
        _inject_tab_capture(bulk_label)
        cols = st.columns(2)
        if cols[0].button("Append", key=f"inc_bulk_append_{ino}", use_container_width=True):
            item["includes"].extend(_parse_bulk_includes(bulk))
            st.rerun()
        if cols[1].button("Replace all", key=f"inc_bulk_replace_{ino}", use_container_width=True):
            item["includes"] = _parse_bulk_includes(bulk)
            st.rerun()


def _inject_tab_capture(aria_label: str) -> None:
    components.html(
        f"""
<script>
(function() {{
  var LABEL = {aria_label!r};
  function bind() {{
    var doc = window.parent.document;
    var areas = doc.querySelectorAll('textarea[aria-label=\"' + LABEL + '\"]');
    areas.forEach(function(ta) {{
      if (ta.dataset.tabCaptureBound === '1') return;
      ta.dataset.tabCaptureBound = '1';
      ta.addEventListener('keydown', function(e) {{
        if (e.key !== 'Tab' || e.ctrlKey || e.altKey || e.metaKey) return;
        e.preventDefault();
        var start = ta.selectionStart;
        var end = ta.selectionEnd;
        var val = ta.value;
        ta.value = val.slice(0, start) + '\\t' + val.slice(end);
        ta.selectionStart = ta.selectionEnd = start + 1;
        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
      }});
    }});
  }}
  bind();
  var mo = new MutationObserver(bind);
  mo.observe(window.parent.document.body, {{ childList: true, subtree: true }});
}})();
</script>
""",
        height=0,
    )


def _parse_bulk_includes(text: str) -> list[dict]:
    entries: list[dict] = []
    for line in parse_lines(text):
        if "\t" in line:
            left, right = line.split("\t", 1)
            left = left.strip()
            right = right.strip()
            if left and not right:
                entries.append({"text": left, "sku": ""})
            elif right and not left:
                entries.append({"text": "", "sku": right})
            elif left and right:
                entries.append({"text": left, "sku": ""})
        else:
            entries.append({"text": line, "sku": ""})
    return entries