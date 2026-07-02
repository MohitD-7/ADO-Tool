from __future__ import annotations

import streamlit as st

from sku_manager.state import current_item, has_batch, set_current_item, sync_description_state


PAGE_LABELS = {
    "Upload":        "Upload Batch",
    "SKU Batch":     "Work Queue",
    "SKU Workspace": "SKU Workspace",
    "Reference Data":"Reference Data",
    "Editor Rules":  "Editor Rules",
    "Review":        "Review",
}

WORKSPACE_TABS = {
    "Basics":               "Name, brand, model, warranty, battery",
    "Description":          "Description and includes",
    "Features & Highlights":"Features and highlights",
    "Specs":                "Technical specifications",
    "Review":               "Preview and export",
}

WORKSPACE_PAGE_ALIASES = {
    "General":          "Basics",
    "Description":      "Description",
    "Features":         "Features & Highlights",
    "Highlights":       "Features & Highlights",
    "Selling Points":   "Features & Highlights",
    "Specs":            "Specs",
    "Preview & Export": "Review",
}

_LEGACY_TAB_MAP = {
    "1 Basics": "Basics", "2 Description": "Description",
    "3 Selling Points": "Features & Highlights",
    "Selling Points": "Features & Highlights",
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
    st.sidebar.markdown('<div class="vo-brand">VirtualOps</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="vo-subtle">SKU Manager &nbsp;·&nbsp; Batch v2.4.0</div>', unsafe_allow_html=True)
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
    return page


def workspace_topbar() -> str:
    """
    Sticky context bar rendered at the top of the main content area.
    Shows the SKU number and product title on top, and standard button navigation below.
    Returns the active tab name.
    """
    raw = st.session_state.get("workspace_tab", "Basics")
    if raw in _LEGACY_TAB_MAP:
        raw = _LEGACY_TAB_MAP[raw]
    if raw not in WORKSPACE_TABS:
        raw = "Basics"
    active_tab = raw
    st.session_state["workspace_tab"] = active_tab

    item = current_item()
    if item:
        details = item["details"]
        item_no = details.get("item_no", "")
        mfg_item = details.get("mfg_item", "")
        title = details.get("title", "")
        mfg_str = f' <span class="vo-topbar-label" style="margin-left: 12px;">Mfg Item:</span> <span class="vo-topbar-ino">{mfg_item}</span>' if mfg_item else ''
        st.markdown(
            f"""
            <div class="vo-topbar">
              <div class="vo-topbar-sku">
                <span class="vo-topbar-label">SKU:</span>
                <span class="vo-topbar-ino">{item_no}</span>
                {mfg_str}
                <span class="vo-topbar-title" style="margin-left: 15px;">- {title}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    tab_names = list(WORKSPACE_TABS.keys())
    btn_cols  = st.columns(len(tab_names))
    clicked   = None
    for col, tab_name in zip(btn_cols, tab_names):
        if col.button(
            tab_name,
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
        st.session_state["workspace_tab"] = "Basics"
        st.rerun()
