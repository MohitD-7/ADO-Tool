"""Patch Streamlit's compiled frontend so grid row checkboxes stay visible.

st.data_editor(num_rows="dynamic") hardcodes rowMarkers kind "checkbox",
which draws the row-select checkbox only while the pointer hovers that row.
The same bundle ships a "checkbox-visible" variant (used for dataframe row
selection) that draws every checkbox all the time, but there is no
Python-side switch between them, so rewrite the bundle string in place.

Runs once per process, is idempotent, and is best-effort: an already
patched bundle, a future Streamlit whose marker string changed, or a
read-only install all leave Streamlit untouched. Because it patches the
installed package at startup, it also survives redeploys that reinstall
Streamlit fresh. Browsers cache the bundle under its hashed name, so the
first load after patching may need a hard refresh (Ctrl+F5).
"""

from __future__ import annotations

from pathlib import Path

import streamlit

_HOVER_ONLY = 'rowMarkers:{kind:"checkbox",'
_ALWAYS_VISIBLE = 'rowMarkers:{kind:"checkbox-visible",'

_applied = False


def ensure_visible_row_checkboxes() -> None:
    global _applied
    if _applied:
        return
    _applied = True
    js_dir = Path(streamlit.__file__).resolve().parent / "static" / "static" / "js"
    for bundle in sorted(js_dir.glob("index.*.js")):
        try:
            text = bundle.read_text(encoding="utf-8")
            if _HOVER_ONLY in text:
                bundle.write_text(text.replace(_HOVER_ONLY, _ALWAYS_VISIBLE), encoding="utf-8")
        except (OSError, UnicodeError):
            continue
