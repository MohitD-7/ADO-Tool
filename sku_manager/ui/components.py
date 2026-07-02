from __future__ import annotations

import streamlit as st

from sku_manager.services.validation import char_count_status


def page_header(kicker: str, title: str, status: str | None = None) -> None:
    badge = f'<span class="vo-badge">{status}</span>' if status else ""
    st.markdown(
        f"""
        <div class="vo-header">
          <div class="vo-kicker">{kicker}{badge}</div>
          <div class="vo-title">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def character_counter(value: str, limit: int) -> None:
    count, ok = char_count_status(value, limit)
    cls = "vo-count-ok" if ok else "vo-count-bad"
    st.markdown(f'<div class="{cls}">{count} / {limit} characters</div>', unsafe_allow_html=True)


def hidden_notes(item: dict, field_key: str) -> None:
    with st.expander("Comments and source links", expanded=False):
        comments = item.setdefault("comments", {})
        comments[field_key] = st.text_area(
            "Comment",
            value=comments.get(field_key, ""),
            key=f"comment_{item['details']['item_no']}_{field_key}",
            height=80,
        )
        links = item.setdefault("links", {})
        field_links = links.setdefault(field_key, [""])
        text_value = "\n".join(field_links)
        updated = st.text_area(
            "Links",
            value=text_value,
            key=f"links_{item['details']['item_no']}_{field_key}",
            height=80,
        )
        links[field_key] = [line.strip() for line in updated.splitlines() if line.strip()]


def drag_reorder(labels: list[str]) -> list[int] | None:
    """
    Draggable list. Returns a permutation (list of original indices in new order)
    when the user commits a reorder, otherwise None. Consumers should apply the
    permutation to their data list and st.rerun().
    """
    import json
    import streamlit.components.v1 as components

    payload = json.dumps([{"i": idx, "label": (lbl or "").strip() or "(empty)"} for idx, lbl in enumerate(labels)])
    height = max(60, 42 * len(labels) + 12)

    html = """
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; color: #1a2330; background: transparent; }
  ol { list-style: none; margin: 0; padding: 0; }
  li {
    display: flex; align-items: center; gap: 8px;
    background: #f8fafc; border: 1px solid #dde3ea; border-radius: 6px;
    padding: 6px 10px; margin-bottom: 4px; cursor: grab;
    transition: background .1s, box-shadow .1s;
  }
  li.dragging { opacity: 0.45; }
  li.drag-over { border-color: #2f6f73; box-shadow: 0 0 0 2px rgba(47,111,115,.18); }
  .handle { color: #98a5b3; font-size: 14px; line-height: 1; user-select: none; }
  .order  { font-weight: 700; color: #6f8090; min-width: 28px; text-align: right; }
  .label  { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #1a2330; }
</style></head><body>
<ol id="list"></ol>
<script>
  const ITEMS = __PAYLOAD__;
  const list = document.getElementById('list');
  let order = ITEMS.map(x => x.i);

  function labelOf(i) {
    const item = ITEMS.find(x => x.i === i);
    return item ? item.label : '';
  }

  function render() {
    list.innerHTML = '';
    order.forEach((origIdx, pos) => {
      const li = document.createElement('li');
      li.draggable = true;
      li.dataset.pos = String(pos);
      li.innerHTML = `<span class="handle">⋮⋮</span><span class="order">${(pos+1)*10}</span><span class="label"></span>`;
      li.querySelector('.label').textContent = labelOf(origIdx);
      li.addEventListener('dragstart', (e) => {
        li.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', String(pos));
      });
      li.addEventListener('dragend', () => {
        li.classList.remove('dragging');
        document.querySelectorAll('li.drag-over').forEach(el => el.classList.remove('drag-over'));
      });
      li.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        li.classList.add('drag-over');
      });
      li.addEventListener('dragleave', () => li.classList.remove('drag-over'));
      li.addEventListener('drop', (e) => {
        e.preventDefault();
        const from = Number(e.dataTransfer.getData('text/plain'));
        const to = Number(li.dataset.pos);
        if (Number.isNaN(from) || Number.isNaN(to) || from === to) return;
        const moved = order.splice(from, 1)[0];
        order.splice(to, 0, moved);
        render();
        commit();
      });
      list.appendChild(li);
    });
    resizeFrame();
  }

  function resizeFrame() {
    const h = document.body.scrollHeight;
    window.parent.postMessage({ isStreamlitMessage: true, type: 'streamlit:setFrameHeight', height: h }, '*');
  }

  let seq = 0;
  function commit() {
    window.parent.postMessage({
      isStreamlitMessage: true,
      type: 'streamlit:setComponentValue',
      value: { order: order.slice(), rev: ++seq },
      dataType: 'json'
    }, '*');
  }

  window.addEventListener('message', (e) => {
    if (e.data && e.data.type === 'streamlit:render') render();
  });
  window.parent.postMessage({ isStreamlitMessage: true, type: 'streamlit:componentReady', apiVersion: 1 }, '*');
  render();
</script></body></html>
"""
    html = html.replace("__PAYLOAD__", payload)
    result = components.html(html, height=height, scrolling=False)
    if not isinstance(result, dict):
        return None
    order = result.get("order")
    if not isinstance(order, list) or len(order) != len(labels):
        return None
    coerced: list[int] = []
    for v in order:
        try:
            coerced.append(int(v))
        except (TypeError, ValueError):
            return None
    if sorted(coerced) != list(range(len(labels))):
        return None
    if coerced == list(range(len(labels))):
        return None
    return coerced


def links_panel(item: dict) -> None:
    """
    Shared 'Links' section for every workspace tab.

    One textarea; one link per line. Stored under item['links']['general'] as a
    list. Exports as a single Excel cell with each link on its own line inside
    the cell.
    """
    ino = item["details"]["item_no"]
    st.markdown(
        '<div style="background:#fff;border:1px solid #dde3ea;border-left:4px solid #8a4d00;border-radius:8px;padding:0.5rem 0.8rem 0.4rem 0.8rem;margin:0.4rem 0;">',
        unsafe_allow_html=True,
    )
    st.markdown("### Links")
    st.caption("One link per line. Exports as a single cell with all links stacked.")
    existing = item.setdefault("links", {}).setdefault("general", [])
    if not isinstance(existing, list):
        existing = [str(existing)] if existing else []
    text_value = "\n".join(str(x) for x in existing if str(x).strip())
    updated = st.text_area(
        "Links",
        value=text_value,
        key=f"links_shared_{ino}",
        height=140,
        label_visibility="collapsed",
        placeholder="https://example.com/source-1\nhttps://example.com/source-2",
    )
    item["links"]["general"] = [line.strip() for line in updated.splitlines() if line.strip()]
    st.markdown("</div>", unsafe_allow_html=True)


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


def right_feedback_panel(item: dict, warnings: list[str], key_prefix: str = "feedback") -> None:
    st.markdown(
        '<div style="background:#f8fafc;border:1px solid #dde3ea;border-radius:8px;padding:0.65rem 0.8rem 0.6rem 0.8rem;font-size:0.85rem;">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-weight:700;font-size:0.8rem;text-transform:uppercase;letter-spacing:.04em;color:#6f8090;margin-bottom:6px;">Validation</div>',
        unsafe_allow_html=True,
    )
    if warnings:
        for warning in warnings:
            st.markdown(f'<div class="vo-warning">{warning}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="background:#f0faf3;border:1px solid #7cba8c;border-left:3px solid #2e8b57;border-radius:6px;padding:.45rem .7rem;color:#1b5e30;font-size:.83rem;font-weight:600;">All fields look good.</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("Item notes", expanded=False):
        item["details"]["comments"] = st.text_area(
            "Item-level comment",
            value=item["details"].get("comments", ""),
            key=f"{key_prefix}_item_comment_{item['details']['item_no']}",
            height=100,
        )
