"""
HTML description editor - CodeMirror 5, two-panel layout.

The editor is rendered as a local Streamlit custom component so the iframe can
return its current value through Streamlit's component protocol. Pages read and
write the plain sync_key session value; the component uses a separate widget key.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from sku_manager.services.rules_store import load_rules
_COMPONENT_DIR = Path(__file__).with_name("html_editor_component")
_html_editor_component = components.declare_component(
    "html_editor_component",
    path=str(_COMPONENT_DIR),
)
_WORKSPACE_TABS = {"Content", "Specs", "Review"}


def html_editor(value: str, sync_key: str, height: int = 320) -> str:
    """
    Render the CodeMirror HTML editor + live preview.
    Returns the latest description text stored in session state.
    """
    component_key = f"{sync_key}_component"
    force_key = f"{sync_key}_force"
    event_key = f"{sync_key}_last_event"

    if sync_key not in st.session_state:
        st.session_state[sync_key] = "" if value is None else str(value)

    forced = st.session_state.pop(force_key, None)
    forced_this_render = forced is not None
    if forced_this_render:
        st.session_state[sync_key] = "" if forced is None else str(forced)

    prior_result = st.session_state.get(component_key)
    if not forced_this_render and isinstance(prior_result, dict):
        prior_value = prior_result.get("value")
        if prior_value is not None:
            st.session_state[sync_key] = str(prior_value)

    current = st.session_state[sync_key]
    rules = load_rules()

    result = _html_editor_component(
        value=current,
        rules=rules,
        css=_CSS.replace("{{HEIGHT}}", str(height)),
        toolbar=_toolbar_html(),
        find_bar=_find_bar_html(),
        paste_menu=_paste_menu_html(),
        height=height,
        active_tab=st.session_state.get("workspace_tab", ""),
        storage_key=sync_key,
        forced=forced_this_render,
        key=component_key,
        default={"value": current},
    )

    if forced_this_render:
        return current

    if isinstance(result, dict):
        next_value = result.get("value", current)
        next_value = "" if next_value is None else str(next_value)
        st.session_state[sync_key] = next_value
        current = next_value

        event_id = result.get("eventId")
        is_new_event = event_id and st.session_state.get(event_key) != event_id
        if is_new_event:
            st.session_state[event_key] = event_id
            navigate_to = result.get("navigateTo")
            if navigate_to in _WORKSPACE_TABS and navigate_to != st.session_state.get("workspace_tab"):
                st.session_state["workspace_tab"] = navigate_to
                st.rerun()

    return current

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _toolbar_html() -> str:
    return """
<div id="toolbar">
  <div class="tb-group">
    <button id="fullscreen-btn" class="btn accent" onclick="toggleFullscreen()" title="Open editor full screen">Full screen</button>
  </div>
  <div class="sep"></div>
  <div class="tb-group">
    <button class="btn bld" onclick="wrap('<b>','</b>')" title="Bold (Ctrl+B)">B</button>
    <button class="btn" onclick="ins('&lt;br&gt;')" title="Insert &lt;br&gt;">BR</button>
  </div>
  <div class="sep"></div>
  <div class="tb-group">
    <button class="btn" onclick="doSingleLine()" title="Single line (Ctrl+L)">&#8645;1L</button>
    <button class="btn" onclick="doCase('upper')" title="UPPERCASE">AA</button>
    <button class="btn" onclick="doCase('lower')" title="lowercase">aa</button>
    <button class="btn" onclick="doCase('sentence')" title="Sentence case">Aa</button>
  </div>
  <div class="sep"></div>
  <div class="tb-group">
    <button class="btn accent" onclick="toggleFind()" title="Find and replace (Ctrl+F)">Find/Replace</button>
  </div>
</div>"""

def _find_bar_html() -> str:
    return """
<div id="find-bar" class="bar hidden">
  <input id="find-input" placeholder="Find..."    />
  <input id="repl-input" placeholder="Replace..." />
  <label><input type="checkbox" id="find-case" /> Case</label>
  <button class="btn" onclick="findNext()">Next</button>
  <button class="btn" onclick="findPrev()">Prev</button>
  <button class="btn" onclick="doReplace()">Replace</button>
  <button class="btn" onclick="doReplaceAll()">All</button>
  <button class="btn" onclick="toggleFind()">&#x2715;</button>
  <span id="find-status"></span>
</div>"""


def _paste_menu_html() -> str:
    return """
<div id="paste-menu" class="hidden">
  <div class="pm-title">Paste as</div>
  <button onclick="doPaste('plain')">&#128196; Plain Text</button>
  <button onclick="doPaste('clean')">&#10024; Clean HTML</button>
  <button onclick="doPaste('raw')">&#128196; Raw HTML</button>
  <button class="pm-cancel" onclick="hidePasteMenu()">Cancel</button>
</div>"""


_CSS = """
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: transparent;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 13px; color: #1a2330; }
#toolbar {
  display: flex; align-items: center; gap: 3px; flex-wrap: wrap;
  background: #f8fafc;
  border: 2px solid #cbd5e1; border-bottom: 1px solid #e2e8f0;
  border-radius: 6px 6px 0 0; padding: 5px 8px;
}
.tb-group { display: flex; gap: 2px; }
.sep { width: 1px; height: 20px; background: #e2e8f0; margin: 0 3px; flex-shrink: 0; }
.btn {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 4px;
  padding: 3px 8px; font-size: 12px; cursor: pointer; color: #1a2330;
  font-family: inherit; line-height: 1.5; white-space: nowrap;
  transition: background .1s, border-color .1s;
}
.btn:hover   { background: #f8fafc; border-color: #ef8e0d; color: #ef8e0d; }
.btn.bld     { font-weight: 800; }
.btn.itl     { font-style: italic; }
.btn.uln     { text-decoration: underline; }
.btn.stk     { text-decoration: line-through; }
.btn.sym     { min-width: 26px; text-align: center; }
.btn.accent  { background: #fff7ed; border-color: #ef8e0d; color: #ef8e0d; font-weight: 700; }
.btn.primary { background: #ef8e0d; color: #fff; border-color: #ef8e0d; font-weight: 700; }
.btn.primary:hover { background: #d97f06; }
.bar {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  background: #f8fafc;
  border: 2px solid #cbd5e1; border-top: none; border-bottom: 1px solid #e2e8f0;
  padding: 5px 8px;
}
.bar input {
  flex: 1; min-width: 120px; max-width: 240px;
  padding: 3px 7px; border: 1.5px solid #cbd5e1; border-radius: 4px;
  font-size: 12px; font-family: inherit; outline: none;
}
.bar input:focus { border-color: #ef8e0d; }
.bar label { display: flex; align-items: center; gap: 3px; font-size: 11px; white-space: nowrap; }
.bar-lbl   { font-size: 11px; font-weight: 700; color: #555; white-space: nowrap; }
#find-status { font-size: 11px; color: #555; margin-left: 4px; }
#resize-handle {
  height: 10px; cursor: ns-resize; user-select: none;
  background: linear-gradient(#f8fafc, #e2e8f0);
  border: 1px solid #cbd5e1; border-top: none;
  border-radius: 0 0 6px 6px;
  position: relative;
}
#resize-handle::before {
  content: ""; position: absolute; left: 50%; top: 3px; transform: translateX(-50%);
  width: 42px; height: 3px; background: #cbd5e1; border-radius: 2px;
}
#resize-handle:hover { background: linear-gradient(#f8fafc, #e2e8f0); }
#resize-handle:hover::before { background: #ef8e0d; }
.rules-bar-flex { background: #fff7ed; border-color: #fed7aa; }
.rules-label { font-size: 11px; font-weight: 800; color: #8b5000; text-transform: uppercase; letter-spacing: .04em; margin-right: 4px; }
.rules-empty { font-size: 11px; color: #6f8090; font-style: italic; }
.btn.rule-btn { background: #fff; border-color: #fed7aa; color: #1a2330; font-weight: 600; }
.btn.rule-btn:hover { background: #ffedd5; border-color: #ef8e0d; color: #8b5000; }
.rule-kbd { display: inline-block; margin-left: 4px; padding: 1px 5px; background: #f6ebd3; border: 1px solid #fed7aa; border-radius: 3px; font-family: Consolas, monospace; font-size: 10px; color: #6b4400; }
.hidden { display: none !important; }
#main-panels { display: flex; width: 100%; }
#editor-panel { flex: 1 1 55%; min-width: 0; }
#preview-panel {
  flex: 1 1 45%; min-width: 0;
  border: 2px solid #cbd5e1; border-top: none; border-left: 1px solid #e2e8f0;
  border-radius: 0 0 6px 0;
  overflow-y: auto; height: {{HEIGHT}}px;
  background: #fff; padding: 10px 14px;
  font-size: 14px; line-height: 1.65; color: #1a2330;
}
#preview-label {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; color: #cbd5e1;
  border-bottom: 1px solid #e8edf2; padding-bottom: 5px; margin-bottom: 8px;
}
#preview-content a { color: #ef8e0d; }
#preview-placeholder { color: #bbb; font-style: italic; font-size: 13px; margin-top: 20px; }
#cm-wrap .CodeMirror {
  height: {{HEIGHT}}px;
  border: 2px solid #cbd5e1; border-top: none;
  border-radius: 0 0 0 6px; border-right: none;
  font-size: 14px; line-height: 1.65;
  font-family: "Consolas", "Menlo", "Monaco", monospace;
}
#cm-wrap .CodeMirror-gutters {
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
}
#cm-wrap .CodeMirror-linenumber {
  color: #cbd5e1;
  font-size: 11px;
  padding-right: 6px;
}
#cm-wrap .CodeMirror-focused {
  border-color: #ef8e0d; box-shadow: 0 0 0 3px rgba(239,142,13,.18);
}
.cm-s-default .cm-tag       { color: #0000cc; font-weight: 600; }
.cm-s-default .cm-attribute { color: #cc0000; }
.cm-s-default .cm-string    { color: #008800; }
.cm-s-default .cm-atom      { color: #7c4dff; font-weight: 600; }
.cm-s-default .cm-comment   { color: #888; font-style: italic; }
.cm-s-default .cm-bracket   { color: #444; }
#cm-wrap .cm-redline {
  text-decoration-line: underline;
  text-decoration-style: wavy;
  text-decoration-color: #d92d20;
  text-decoration-thickness: 1.5px;
  text-underline-offset: 2px;
}
#cm-wrap .cm-redline-special { background: rgba(217, 45, 32, .07); }
#cm-wrap .cm-redline-spelling { background: rgba(217, 45, 32, .03); }
#counter { text-align: right; font-size: 11px; font-weight: 700; padding: 3px 2px; }
.cnt-ok  { color: #2a7a3a; }
.cnt-bad { color: #c62828; }
#paste-menu {
  position: fixed; background: #fff;
  border: 1.5px solid #cbd5e1; border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,.18);
  padding: 8px 6px; min-width: 190px; max-width: calc(100vw - 16px); z-index: 99999;
  top: 80px; left: 30px;
}
.pm-title {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; color: #888;
  padding: 2px 8px 6px; border-bottom: 1px solid #e0e0e0; margin-bottom: 4px;
}
#paste-menu button {
  display: block; width: 100%; text-align: left;
  background: none; border: none; border-radius: 4px;
  padding: 7px 10px; font-size: 13px; cursor: pointer;
  color: #1a2330; font-family: inherit;
}
#paste-menu button:hover { background: #f8fafc; }
.pm-cancel { color: #888 !important; font-size: 12px !important; margin-top: 4px; }
#editor-shell { background: transparent; }
body.fullscreen-mode {
  background: #f7f9fb;
  padding: 12px;
  overflow: hidden;
}
body.fullscreen-mode #editor-shell {
  height: calc(100vh - 24px);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
body.fullscreen-mode #toolbar,
body.fullscreen-mode .bar {
  flex: 0 0 auto;
}
body.fullscreen-mode #main-panels {
  flex: 1 1 auto;
  min-height: 0;
}
body.fullscreen-mode #editor-panel,
body.fullscreen-mode #preview-panel {
  min-height: 0;
}
body.fullscreen-mode #resize-handle {
  display: none;
}
body.fullscreen-mode #counter {
  background: #fff;
  border-left: 2px solid #cbd5e1;
  border-right: 2px solid #cbd5e1;
  border-bottom: 2px solid #cbd5e1;
}
"""
