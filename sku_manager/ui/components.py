from __future__ import annotations

import hashlib
import html

import pandas as pd
import streamlit as st

try:
    from streamlit_sortables import sort_items
except ImportError:
    sort_items = None

from sku_manager.services.validation import char_count_status


def enable_global_spellcheck() -> None:
    """Force browser spellcheck (red squiggly underlines) on every native text input/textarea,
    including fields that aren't currently focused.

    Must be called on every render (not gated behind a "ran once" flag): the
    HTML below is identical across reruns, so Streamlit keeps the same iframe
    without reloading it, which is what lets the interval/observer persist. If
    this were only called once, Streamlit would unmount the iframe on the next
    rerun (since it would no longer appear in that run's output) and it
    would be destroyed.

    Browsers only actively spellcheck text entered via real keystrokes while a
    field has focus; when Streamlit re-renders and sets a field's value
    programmatically, the browser never re-scans it, so marks vanish the
    moment focus leaves. To work around this, unfocused fields get their
    `spellcheck` attribute toggled off/on periodically, which forces the
    browser to redo its check against whatever text is currently there.
    """
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        (function() {
          function recheck(el) {
            try {
              el.setAttribute('spellcheck', 'false');
              void el.offsetHeight;
              el.setAttribute('spellcheck', 'true');
            } catch (e) {}
          }

          function applySpellcheck(doc) {
            if (!doc) return;
            var els = doc.querySelectorAll('textarea, input[type="text"], input:not([type])');
            els.forEach(function(el) {
              if (!el.getAttribute('lang')) el.setAttribute('lang', 'en-US');
              if (el.getAttribute('spellcheck') !== 'true') {
                el.setAttribute('spellcheck', 'true');
              } else if (doc.activeElement !== el) {
                recheck(el);
              }
            });
          }

          try {
            var doc = window.parent.document;
            doc.documentElement.setAttribute('lang', 'en-US');
            applySpellcheck(doc);
            var observer = new MutationObserver(function() { applySpellcheck(doc); });
            observer.observe(doc.body, { childList: true, subtree: true });
            setInterval(function() { applySpellcheck(doc); }, 700);
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
    )


def page_header(kicker: str, title: str, status: str | None = None) -> None:
    safe_kicker = html.escape(str(kicker))
    safe_title = html.escape(str(title))
    badge = f'<span class="vo-badge">{html.escape(str(status))}</span>' if status else ""
    st.markdown(
        f"""
        <div class="vo-header">
          <div class="vo-kicker"><span>{safe_kicker}</span>{badge}</div>
          <div class="vo-title">{safe_title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def character_counter(value: str, limit: int) -> None:
    count, ok = char_count_status(value, limit)
    cls = "vo-count-ok" if ok else "vo-count-bad"
    st.markdown(f'<div class="{cls}">{count} / {limit} characters</div>', unsafe_allow_html=True)


def field_notes_editor(
    item: dict,
    field_key: str,
    title: str | None = None,
    *,
    expanded: bool = False,
) -> None:
    """Edit field-level comments only."""
    safe_title = html.escape(title or "Comments")
    st.markdown(f'<div class="vo-field-notes-label">{safe_title}</div>', unsafe_allow_html=True)
    with st.expander("Comments", expanded=expanded):
        comments = item.setdefault("comments", {})
        comments[field_key] = st.text_area(
            "Comment",
            value=comments.get(field_key, ""),
            key=f"comment_{item['details']['item_no']}_{field_key}",
            height=92,
        )
def hidden_notes(item: dict, field_key: str) -> None:
    field_notes_editor(item, field_key)


def _reorder_token(label: str, orig: int) -> str:
    """A stable, unique token string for a reorder row.

    The label stays visible; an index-derived marker of invisible characters is
    appended so two rows with identical text remain distinct and — crucially —
    the token never changes across reruns (position is shown via a CSS counter,
    not baked into this string). U+2063 is an invisible separator; the marker
    encodes ``orig`` in binary as zero-width space / zero-width non-joiner.
    """
    marker = "".join("‌" if bit == "1" else "​" for bit in format(orig, "b"))
    return f"{label}⁣{marker}"


# Inlined palette values (the drag list is an iframe and can't read our CSS vars).
_REORDER_STYLE = """
.sortable-component {
    background: transparent;
    padding: 0;
    margin: 0;
    box-shadow: none;
    border: none;
}
.sortable-container,
.sortable-container-body {
    background: transparent;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    counter-reset: reorder-weight 0;
}
.sortable-item {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    text-align: left;
    width: 100%;
    box-sizing: border-box;
    background-color: #ffffff;
    color: #191c1e;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 8px 12px;
    margin: 0;
    font-size: 0.88rem;
    font-weight: 400;
    line-height: 1.35;
    box-shadow: none;
    cursor: grab;
}
.sortable-item::before {
    counter-increment: reorder-weight 10;
    content: counter(reorder-weight);
    flex: 0 0 auto;
    min-width: 2.75em;
    margin-right: 12px;
    color: #64748b;
    font-weight: 600;
    text-align: right;
}
.sortable-item.dragging::before {
    counter-increment: none;
}
.sortable-item:hover {
    border-color: #ef8e0d;
    background-color: #fff7ed;
}
.sortable-item.dragging,
.sortable-item.sortable-chosen,
.sortable-item.sortable-ghost,
.sortable-item.sortable-drag {
    cursor: grabbing;
    opacity: 0.9;
    color: #191c1e !important;
    background-color: #ffffff !important;
    border-color: #ef8e0d;
    box-shadow: 0 2px 10px rgba(25, 28, 30, 0.14);
}
.sortable-item.dragging *,
.sortable-item.sortable-chosen *,
.sortable-item.sortable-ghost *,
.sortable-item.sortable-drag * {
    color: #191c1e !important;
}
"""


def reorder_editor(labels: list[str], key: str) -> list[int] | None:
    """Drag-and-drop reorder control with an explicit Save.

    Rows are dragged into a *pending* working order held in session state;
    nothing commits until the user clicks "Save order", at which point the
    permutation (original indices in their new order) is returned. Every other
    run returns None.

    The caller should apply the permutation to its list, reset any data editor
    that renders that list (pop the editor's widget-state key so it re-initialises
    from the new order), and st.rerun().

    The reorder UI is revealed by a toggle rather than an expander: the drag
    list is an iframe component, and iframe components render blank inside a
    collapsed expander (they measure their height while hidden and never
    re-measure when it opens).
    """
    n = len(labels)
    show_key = f"{key}__show"
    st.toggle(f"Reorder ({n} rows)", key=show_key)
    if not st.session_state.get(show_key):
        return None

    state_key = f"{key}__working"
    working = st.session_state.get(state_key)
    if not isinstance(working, list) or sorted(working) != list(range(n)):
        working = list(range(n))
        st.session_state[state_key] = working

    if sort_items is None:
        return _fallback_reorder_editor(labels, key, working, state_key)

    # Build one *stable* draggable token per original row. The token identity
    # must not change between reruns: the keyed component echoes back the token
    # strings from its own frontend state on a drop, so if we renumbered them we
    # would fail to map the result back (KeyError). Each token is therefore the
    # label plus an invisible, index-derived marker — that keeps tokens unique
    # even when two rows share the same label, without showing anything extra.
    # The visible weight (10, 20, 30…) is drawn by a CSS counter on the row's
    # position instead (see _REORDER_STYLE), so it always tracks the live order.
    tokens_by_orig = [_reorder_token(labels[i], i) for i in range(n)]
    token_to_orig = {token: i for i, token in enumerate(tokens_by_orig)}
    display_tokens = [tokens_by_orig[orig] for orig in working]

    # Remount the component whenever the underlying *text* changes. The caller's
    # data editor reformats and rewrites the list on every rerun, which would
    # otherwise leave the component echoing back tokens built from stale label
    # text (→ KeyError below). The signature is over the label multiset, so it
    # is unchanged by reordering — dragging still persists — and only flips when
    # a row's text is edited, added, or removed.
    sig = hashlib.md5("\x00".join(sorted(labels)).encode("utf-8")).hexdigest()[:8]
    ordered = sort_items(
        display_tokens, direction="vertical", custom_style=_REORDER_STYLE,
        key=f"{key}_sortable_{sig}",
    )
    # Guard: if the component is momentarily out of sync (its cached tokens
    # predate a text change), ignore its output this run rather than crashing.
    if set(ordered) == set(display_tokens):
        new_working = [token_to_orig[token] for token in ordered]
        if new_working != working:
            # Drop happened: persist the pending order. Still not committed.
            st.session_state[state_key] = new_working
            st.rerun()

    changed = working != list(range(n))
    save_col, reset_col = st.columns(2)
    if save_col.button(
        "Save order", key=f"{key}_save", type="primary",
        disabled=not changed, use_container_width=True,
    ):
        order = list(working)
        st.session_state.pop(state_key, None)
        return order
    if reset_col.button(
        "Reset", key=f"{key}_reset", disabled=not changed, use_container_width=True,
    ):
        st.session_state.pop(state_key, None)
        st.rerun()
    return None


def _fallback_reorder_editor(
    labels: list[str],
    key: str,
    working: list[int],
    state_key: str,
) -> list[int] | None:
    """Fallback reorder control used when streamlit-sortables is unavailable."""
    from sku_manager.ui.grid import reset_stable_data_editor, stable_data_editor

    rows = [
        {
            "Order": (position + 1) * 10,
            "Item": labels[orig],
        }
        for position, orig in enumerate(working)
    ]
    editor_key = f"{key}_fallback_order"
    edited = stable_data_editor(
        pd.DataFrame(rows, columns=["Order", "Item"]),
        key=editor_key,
        num_rows="fixed",
        width="stretch",
        hide_index=True,
        column_config={
            "Order": st.column_config.NumberColumn("Order", width="small", step=10),
            "Item": st.column_config.TextColumn("Item", disabled=True, width="large"),
        },
    )

    sortable_rows = []
    for position, row in edited.fillna("").iterrows():
        if position >= len(working):
            continue
        try:
            order_value = float(row.get("Order", (position + 1) * 10))
        except (TypeError, ValueError):
            order_value = float((position + 1) * 10)
        sortable_rows.append((order_value, int(position), working[int(position)]))

    proposed = [orig for _, _, orig in sorted(sortable_rows)]
    changed = proposed != list(range(len(labels)))
    save_col, reset_col = st.columns(2)
    if save_col.button(
        "Save order", key=f"{key}_save", type="primary",
        disabled=not changed, use_container_width=True,
    ):
        st.session_state.pop(state_key, None)
        reset_stable_data_editor(editor_key)
        return proposed
    if reset_col.button(
        "Reset", key=f"{key}_reset", disabled=not changed, use_container_width=True,
    ):
        st.session_state.pop(state_key, None)
        reset_stable_data_editor(editor_key)
        st.rerun()
    return None


def _line_list(value) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").splitlines()
    return [str(line).strip() for line in raw if str(line).strip()]


def links_panel(item: dict, key_suffix: str = "shared") -> None:
    """Common source-link box for the current SKU."""
    ino = item["details"]["item_no"]
    links = item.setdefault("links", {})
    existing = _line_list(links.get("general", []))
    updated = st.text_area(
        "Source links",
        value="\n".join(existing),
        key=f"source_links_{key_suffix}_{ino}",
        height=110,
        placeholder="https://example.com/source-1\nhttps://example.com/source-2",
    )
    links["general"] = _line_list(updated)


def source_video_panel(item: dict, key_suffix: str = "shared", *, expanded: bool = False) -> None:
    """One common place for all SKU source links and video links."""
    safe_title = html.escape("Common source / video links")
    st.markdown(f'<div class="vo-field-notes-label">{safe_title}</div>', unsafe_allow_html=True)
    with st.expander("Source and video links", expanded=expanded):
        st.caption("Put one link per line. These apply to the whole SKU.")
        links_panel(item, key_suffix=key_suffix)
        video_value = "\n".join(_line_list(item.setdefault("details", {}).get("video_link", "")))
        updated_video = st.text_area(
            "Video links",
            value=video_value,
            key=f"video_links_{key_suffix}_{item['details']['item_no']}",
            height=92,
            placeholder="https://example.com/video-1\nhttps://example.com/video-2",
        )
        item["details"]["video_link"] = "\n".join(_line_list(updated_video))
_RESERVED_CHORDS = {
    # Chrome / OS-level shortcuts that would either intercept our keydown or
    # steal focus even if we preventDefault them. Numeric digit chords with
    # Ctrl-only jump to tabs; Ctrl+T/N/W etc. are hard-reserved.
    "Ctrl+T", "Ctrl+N", "Ctrl+Shift+N", "Ctrl+W", "Ctrl+Shift+W",
    "Ctrl+Tab", "Ctrl+Shift+Tab",
    "Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4", "Ctrl+5",
    "Ctrl+6", "Ctrl+7", "Ctrl+8", "Ctrl+9", "Ctrl+0",
    "Ctrl+L", "Ctrl+D", "Ctrl+H", "Ctrl+J", "Ctrl+P", "Ctrl+F",
    "Ctrl+R", "Ctrl+Shift+R", "Ctrl+U", "Ctrl+O", "Ctrl+S",
    "F5", "F11", "F12",
    "Alt+F4", "Alt+Left", "Alt+Right", "Alt+Home",
}

_SUGGESTED_CHORDS = [
    "Ctrl+Alt+A", "Ctrl+Alt+B", "Ctrl+Alt+C", "Ctrl+Alt+D",
    "Ctrl+Alt+E", "Ctrl+Alt+F", "Ctrl+Alt+G", "Ctrl+Alt+H",
    "Ctrl+Alt+K", "Ctrl+Alt+L", "Ctrl+Alt+M", "Ctrl+Alt+N",
    "Ctrl+Alt+P", "Ctrl+Alt+Q", "Ctrl+Alt+R", "Ctrl+Alt+U",
    "Ctrl+Alt+V", "Ctrl+Alt+X", "Ctrl+Alt+Y", "Ctrl+Alt+Z",
    "Ctrl+Shift+Alt+A", "Ctrl+Shift+Alt+S", "Ctrl+Shift+Alt+D",
    "Ctrl+Shift+Alt+F", "Ctrl+Shift+Alt+G",
    "Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5",
    "Alt+6", "Alt+7", "Alt+8", "Alt+9", "Alt+0",
]


def is_reserved_chord(chord: str) -> bool:
    return chord.strip() in _RESERVED_CHORDS


def suggested_chords() -> list[str]:
    return list(_SUGGESTED_CHORDS)


def _get_shortcut_capture_component():
    from pathlib import Path
    import streamlit.components.v1 as components
    _dir = Path(__file__).with_name("shortcut_capture_component")
    return components.declare_component("shortcut_capture", path=str(_dir))


def shortcut_capture(current: str, key: str) -> str:
    """
    Keyboard-chord capture widget. Renders a focusable box; when focused, the
    next non-modifier keystroke (with any combination of Ctrl/Shift/Alt/Meta)
    is captured, the browser default is prevented, and the normalised chord
    (e.g. 'Ctrl+Shift+K') is sent back. Returns the current chord (whatever
    the JS side last reported), or `current` if nothing has been recorded yet.

    `key` must be unique per usage so Streamlit tracks the widget's returned
    value across reruns.
    """
    comp = _get_shortcut_capture_component()
    result = comp(initial=current or "", key=key, default={"chord": current or ""})
    if isinstance(result, dict) and "chord" in result:
        return str(result.get("chord") or "")
    return current or ""


def _get_brand_autocomplete_component():
    from pathlib import Path
    import streamlit.components.v1 as components
    _dir = Path(__file__).with_name("brand_autocomplete_component")
    return components.declare_component("brand_autocomplete", path=str(_dir))


def brand_autocomplete(current: str, brands: list[str], key: str) -> str:
    """
    Text box backed by a native browser datalist, so typing e.g. "de" shows a
    live dropdown of every brand in `brands` containing that text. The value
    is sent back to Python on Enter or on losing focus (not per keystroke).
    Returns the committed value, or `current` if nothing committed yet.
    """
    comp = _get_brand_autocomplete_component()
    result = comp(initial=current or "", brands=brands, key=key, default={"value": current or ""})
    if isinstance(result, dict) and "value" in result:
        return str(result.get("value") or "")
    return current or ""


def right_feedback_panel(item: dict, warnings: list[str], key_prefix: str = "feedback") -> None:
    st.markdown('<div class="vo-panel-title">Validation</div>', unsafe_allow_html=True)
    if warnings:
        with st.expander(f"⚠ Warnings - not filled ({len(warnings)})", expanded=False):
            for warning in warnings:
                st.markdown(f'<div class="vo-warning">{warning}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="vo-success-box">All fields look good.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="vo-panel-gap">&#8203;</div>', unsafe_allow_html=True)
    with st.expander("Item notes", expanded=False):
        item["details"]["comments"] = st.text_area(
            "Item-level comment",
            value=item["details"].get("comments", ""),
            key=f"{key_prefix}_item_comment_{item['details']['item_no']}",
            height=100,
        )
