"""
Editor Rules manager page.
Lets users create, edit, and delete custom rules for the HTML description editor.
Each rule can wrap text in HTML tags, prepend/append text, apply per-line,
apply automatically on paste, and be triggered by a keyboard shortcut.
"""
from __future__ import annotations

import streamlit as st

from sku_manager.services import html_rules as logic
from sku_manager.services import rules_store
from sku_manager.ui.components import is_reserved_chord, page_header, shortcut_capture, suggested_chords


def render() -> None:
    page_header("Description Editor", "Custom Rules")

    rules = rules_store.load_rules()

    left, right = st.columns([1.1, 1.9])

    # ── Left: rule list ───────────────────────────────────────────────
    with left:
        st.markdown("### Rules")
        if not rules:
            st.caption("No rules yet. Create one on the right.")
        else:
            for rule in rules:
                sc = rule.get("shortcut", "") or "no shortcut"
                paste_tag = " | on-paste" if rule.get("apply_on_paste") else ""
                col_name, col_edit, col_del = st.columns([3, 1, 1])
                col_name.markdown(
                    f"**{rule['name']}**  \n"
                    f"<span style='font-size:.8rem;color:#6f8090'>{sc}{paste_tag}</span>",
                    unsafe_allow_html=True,
                )
                if col_edit.button("Edit", key=f"edit_{rule['name']}"):
                    st.session_state["_editing_rule"] = rule["name"]
                    st.session_state["_rule_form"] = dict(rule)
                    st.rerun()
                if col_del.button("Del", key=f"del_{rule['name']}"):
                    rules_store.delete_rule(rule["name"])
                    st.success(f"Deleted '{rule['name']}'.")
                    st.rerun()
        if st.button("+ New Rule", type="primary", use_container_width=True):
            st.session_state["_editing_rule"] = None
            st.session_state["_rule_form"] = _blank_rule()
            st.rerun()

    # ── Right: create / edit form ─────────────────────────────────────
    with right:
        if "_rule_form" not in st.session_state:
            st.info("Select a rule to edit, or click + New Rule.")
            return

        form = st.session_state["_rule_form"]
        editing_name = st.session_state.get("_editing_rule")
        heading = f"Edit: {editing_name}" if editing_name else "New Rule"
        st.markdown(f"### {heading}")

        form["name"] = st.text_input(
            "Rule name", value=form.get("name", ""),
            placeholder="e.g. Wrap in paragraph tag",
        )
        sc_label, sc_help = st.columns([9, 1])
        with sc_label:
            st.markdown(
                "<div style='font-weight:700;font-size:.8rem;color:#1a2330;margin-bottom:2px;'>"
                "Keyboard shortcut (optional)</div>",
                unsafe_allow_html=True,
            )
        with sc_help:
            with st.popover("?", use_container_width=True):
                st.markdown("**Safe shortcut suggestions**")
                st.caption(
                    "These combos are not intercepted by Chrome or the OS. "
                    "Any Ctrl-only or Ctrl+Shift-only combo with a plain letter/digit "
                    "usually clashes with a browser shortcut — the widget will warn you."
                )
                for chord in suggested_chords():
                    st.markdown(f"- `{chord}`")

        capture_key = f"shortcut_capture_{editing_name or 'new'}"
        form["shortcut"] = shortcut_capture(form.get("shortcut", ""), key=capture_key)
        if form.get("shortcut"):
            if is_reserved_chord(form["shortcut"]):
                st.warning(
                    f"**{form['shortcut']}** is reserved by the browser or OS and may be "
                    "intercepted before the editor sees it. Pick a different combo — "
                    "try adding Alt (e.g. `Ctrl+Alt+…`)."
                )
            else:
                st.caption(f"Current shortcut: **{form['shortcut']}**")
        else:
            st.caption("Click the box, press the combo you want, then Save.")
        form["apply_on_paste"] = st.checkbox(
            "Apply this rule automatically on paste",
            value=form.get("apply_on_paste", False),
        )
        form["apply_per_line"] = st.checkbox(
            "Apply to each line separately",
            value=form.get("apply_per_line", False),
        )

        st.markdown('<div style="border-top:1px solid #e2e8f0;margin:10px 0"></div>', unsafe_allow_html=True)
        st.markdown("**Modifications**")

        c1, c2 = st.columns(2)
        form["add_start"] = c1.checkbox("Add text at start", value=form.get("add_start", False))
        form["start_text"] = c1.text_input(
            "Start text", value=form.get("start_text", ""),
            disabled=not form["add_start"], placeholder="Text prepended",
        )
        form["add_end"] = c2.checkbox("Add text at end", value=form.get("add_end", False))
        form["end_text"] = c2.text_input(
            "End text", value=form.get("end_text", ""),
            disabled=not form["add_end"], placeholder="Text appended",
        )

        form["add_tags"] = st.checkbox("Wrap with HTML tag", value=form.get("add_tags", False))
        if form["add_tags"]:
            form["tag"] = st.text_input(
                "Tag name (without < >)", value=form.get("tag", ""),
                placeholder="e.g.  p   or   span",
            )
            tp1, tp2 = st.columns(2)
            form["start_after_tag"] = tp1.checkbox(
                "Place start text after opening tag",
                value=form.get("start_after_tag", False),
            )
            form["end_before_tag"] = tp2.checkbox(
                "Place end text before closing tag",
                value=form.get("end_before_tag", False),
            )
        else:
            form["tag"] = form.get("tag", "")

        # Preview
        st.markdown('<div style="border-top:1px solid #e2e8f0;margin:10px 0"></div>', unsafe_allow_html=True)
        preview_text = st.text_input("Preview input text", value="Sample text", key="_rule_preview_input")
        if preview_text:
            preview_out = logic.apply_rule(preview_text, form)
            st.markdown(
                f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;'
                f'padding:.6rem .9rem;font-family:monospace;font-size:.88rem;color:#1a2330;">'
                f'{preview_out}</div>',
                unsafe_allow_html=True,
            )
        sa, sb, sc_ = st.columns([2, 1, 1])
        if sa.button("Save Rule", type="primary", use_container_width=True):
            errors = logic.validate_rule(
                form,
                rules_store.load_rules(),
                editing_name=editing_name,
            )
            if errors:
                for e in errors:
                    st.error(e)
            else:
                if editing_name:
                    rules_store.update_rule(editing_name, form)
                    st.success(f"Updated '{form['name']}'.")
                else:
                    rules_store.add_rule(form)
                    st.success(f"Created '{form['name']}'.")
                del st.session_state["_rule_form"]
                st.session_state.pop("_editing_rule", None)
                st.rerun()

        if sb.button("Cancel", use_container_width=True):
            del st.session_state["_rule_form"]
            st.session_state.pop("_editing_rule", None)
            st.rerun()
def _blank_rule() -> dict:
    return {
        "name": "", "shortcut": "",
        "apply_on_paste": False, "apply_per_line": False,
        "add_start": False, "start_text": "",
        "add_end": False, "end_text": "",
        "add_tags": False, "tag": "",
        "start_after_tag": False, "end_before_tag": False,
    }
