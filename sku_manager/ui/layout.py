from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from sku_manager.state import current_item, has_batch, set_current_item, sync_description_state


_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "VO-Logo.png"


PAGE_LABELS = {
    "Upload":        "Batch Input",
    "SKU Batch":     "Work Queue",
    "SKU Workspace": "SKU Editor",
    "Reference Data":"Reference Data",
    "Editor Rules":  "Editor Rules",
    "Review":        "Review",
}

WORKSPACE_TABS = {
    "Content": "General information, description, features, and highlights",
    "Specs":   "Technical specifications",
    "VarOpts": "Variant options for child SKUs",
    "Review":  "Preview and export",
}

WORKSPACE_PAGE_ALIASES = {
    "General":          "Content",
    "Basics":           "Content",
    "Description":      "Content",
    "Features":         "Content",
    "Highlights":       "Content",
    "Selling Points":   "Content",
    "Specs":            "Specs",
    "Var Opts":         "VarOpts",
    "VarOpts":          "VarOpts",
    "Preview & Export": "Review",
}

_LEGACY_TAB_MAP = {
    "Basics": "Content", "1 Basics": "Content", "2 Description": "Content",
    "Description": "Content", "Features & Highlights": "Content",
    "3 Selling Points": "Content", "Selling Points": "Content",
    "4 Specs": "Specs", "5 Review": "Review",
}


def _visible_pages() -> list[str]:
    if has_batch():
        return ["Upload", "SKU Batch", "SKU Workspace", "Reference Data", "Editor Rules", "Review"]
    return ["Upload", "Reference Data", "Editor Rules", "Review"]


def _page_for_label(label: str) -> str:
    for page, lbl in PAGE_LABELS.items():
        if lbl == label:
            return page
    return "Upload"


def sidebar_nav() -> str:
    """Render sidebar brand + page nav. Returns the active page key."""
    # ── Brand ─────────────────────────────────────────────────────────────
    if _LOGO_PATH.exists():
        st.sidebar.image(str(_LOGO_PATH), use_container_width=True)
    st.sidebar.markdown('<div class="vo-brand">SKU Manager</div>', unsafe_allow_html=True)
    st.sidebar.markdown("---")

    # ── Resolve active page ───────────────────────────────────────────────
    active_page = st.session_state.get("active_page", "Upload")
    if active_page in WORKSPACE_PAGE_ALIASES and has_batch():
        st.session_state["workspace_tab"] = WORKSPACE_PAGE_ALIASES[active_page]
        active_page = "SKU Workspace"
        st.session_state["active_page"] = active_page

    visible_pages = _visible_pages()
    if active_page not in visible_pages:
        active_page = "Upload"
        st.session_state["active_page"] = active_page

    labels = [PAGE_LABELS[p] for p in visible_pages]
    st.session_state["nav_page_selector"] = PAGE_LABELS[active_page]

    def _set_page() -> None:
        sync_description_state()
        st.session_state["active_page"] = _page_for_label(
            st.session_state.get("nav_page_selector", PAGE_LABELS["Upload"])
        )

    selected_label = st.sidebar.radio(
        "nav", labels,
        index=labels.index(PAGE_LABELS[active_page]),
        key="nav_page_selector",
        on_change=_set_page,
        label_visibility="collapsed",
    )
    page = _page_for_label(selected_label)
    st.session_state["active_page"] = page
    st.sidebar.markdown(
        '<div class="vo-sidebar-credit">&copy; 2026 Developed by Mohit Dhaker</div>',
        unsafe_allow_html=True,
    )
    return page


_DV2_TAB_LABELS = {
    "Content": "General Description",
    "Specs":   "Specs",
    "VarOpts": "Var Opts",
    "Review":  "Review",
}


def _dv2_workspace_header(details: dict) -> None:
    """Render the DESIGN.md-style SKU header card using immutable input metadata."""
    raw_item_no = str(details.get("item_no", ""))
    queue_title = ""
    queue_mfg_item = ""
    queue = st.session_state.get("queue_df")
    if queue is not None and not queue.empty and "Item No" in queue.columns:
        match = queue[queue["Item No"].astype(str) == raw_item_no]
        if not match.empty:
            queue_title = str(match.iloc[0].get("Title", ""))
            queue_mfg_item = str(match.iloc[0].get("Mfg Item", ""))

    item_no = html.escape(raw_item_no)
    title_text = details.get("input_title", "") or queue_title or details.get("title", "") or "Untitled SKU"
    mfg_text = details.get("input_mfg_item", "") or queue_mfg_item or details.get("mfg_item", "") or details.get("mfg_model", "")
    title = html.escape(str(title_text))
    mfg_item = html.escape(str(mfg_text))
    category = html.escape(str(details.get("category", "") or ""))

    meta_bits = []
    if mfg_item:
        meta_bits.append(f'<span class="dv2-lbl">MPN:</span> <span class="dv2-mono">{mfg_item}</span>')
    if category:
        meta_bits.append(f'<span class="dv2-lbl">Category:</span> {category}')
    meta_html = ' <span class="dv2-sep">|</span> '.join(meta_bits)

    st.markdown(
        f"""
        <div class="dv2-header">
          <div class="dv2-header-left">
            <div class="dv2-chip-row">
              <span class="dv2-id-chip">ID: {item_no}</span>
              <span class="dv2-status-chip dv2-status-draft">Draft</span>
            </div>
            <h1 class="dv2-header-title" title="{title}">{title}</h1>
            <p class="dv2-header-meta">{meta_html}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def workspace_topbar() -> str:
    """
    DESIGN.md-styled workspace top region:
      1. Product header card (ID, DRAFT, title, MPN)
      2. Underlined sub-tabs (General / Description / Features/Highlights / Specs / Review)
    Returns the active tab name (internal key).
    """
    raw = st.session_state.get("workspace_tab", "Content")
    if raw in _LEGACY_TAB_MAP:
        raw = _LEGACY_TAB_MAP[raw]
    if raw not in WORKSPACE_TABS:
        raw = "Content"
    active_tab = raw
    st.session_state["workspace_tab"] = active_tab

    item = current_item()
    if item:
        _dv2_workspace_header(item["details"])

    tab_names = list(WORKSPACE_TABS.keys())
    btn_cols  = st.columns(len(tab_names))
    clicked   = None
    for col, tab_name in zip(btn_cols, tab_names):
        display = _DV2_TAB_LABELS.get(tab_name, tab_name)
        if col.button(
            display,
            key=f"topbar_tab_{tab_name}",
            type="primary" if tab_name == active_tab else "secondary",
            use_container_width=True,
        ):
            clicked = tab_name
    if clicked and clicked != active_tab:
        sync_description_state()
        st.session_state["workspace_tab"] = clicked
        st.rerun()

    return active_tab


def review_sku_bar() -> None:
    """SKU switcher for the Review page — plain button row, no decorative pills."""
    items = st.session_state.get("items", {})
    if not items:
        return

    current_ino = st.session_state.get("current_item_no", "")
    ino_list    = list(items.keys())
    cols        = st.columns(min(len(ino_list), 10))
    clicked_ino = None
    for i, ino in enumerate(ino_list):
        if cols[i % len(cols)].button(ino, key=f"reviewbar_sku_{ino}", use_container_width=True):
            clicked_ino = ino

    if clicked_ino and clicked_ino != current_ino:
        set_current_item(clicked_ino)
        st.session_state["workspace_tab"] = "Content"
        st.rerun()
