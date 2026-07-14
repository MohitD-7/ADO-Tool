from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import streamlit as st

from sku_manager.config import SAVE_USERS
from sku_manager.services import worksave
from sku_manager.state import current_item, has_batch, set_current_item, sync_description_state


_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "VO-Logo.png"


@st.cache_data(show_spinner=False)
def _logo_bytes(path: str, mtime: float) -> bytes:
    return Path(path).read_bytes()


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
        st.sidebar.image(_logo_bytes(str(_LOGO_PATH), _LOGO_PATH.stat().st_mtime), use_container_width=True)
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
    _sidebar_save_controls()
    st.sidebar.markdown(
        '<div class="vo-sidebar-credit">&copy; 2026 Developed by Mohit Dhaker</div>',
        unsafe_allow_html=True,
    )
    return page


_USER_PLACEHOLDER = "— select user —"


def _save_users() -> list[str]:
    try:
        users = st.secrets.get("save_users")
    except Exception:
        users = None
    if users:
        return [str(user) for user in users]
    return SAVE_USERS


def _clear_save_context() -> None:
    st.session_state["save_user"] = ""
    worksave.reset_session_cache()
    st.session_state.pop("_worksave_saved_at", None)
    st.session_state.pop("_worksave_restore_handled", None)


def _user_selector_key() -> str:
    rev = int(st.session_state.get("_worksave_user_selector_rev", 0) or 0)
    return f"worksave_user_selector_{rev}"


def _reset_user_selector() -> None:
    rev = int(st.session_state.get("_worksave_user_selector_rev", 0) or 0)
    st.session_state["_worksave_user_selector_rev"] = rev + 1


def _on_user_change(selector_key: str) -> None:
    selection = st.session_state.get(selector_key, _USER_PLACEHOLDER)
    _clear_save_context()
    if selection == _USER_PLACEHOLDER:
        st.session_state.pop("_worksave_lease_conflict", None)
        return

    selected_user = str(selection)
    ok, info = worksave.acquire_user_lease(selected_user)
    if ok:
        st.session_state["save_user"] = selected_user
        st.session_state.pop("_worksave_lease_conflict", None)
    else:
        st.session_state["_worksave_lease_conflict"] = info
        _reset_user_selector()


def _last_saved_caption() -> str:
    saved_at = st.session_state.get("_worksave_saved_at")
    if not saved_at:
        if st.session_state.get("_worksave_lease_conflict"):
            return "Auto-save is blocked until that user is free."
        if not st.session_state.get("save_user"):
            return "Select your name to enable auto-save."
        return "Not saved yet — auto-saves as you work."
    try:
        stamp = datetime.fromisoformat(saved_at).astimezone().strftime("%H:%M:%S")
    except ValueError:
        stamp = str(saved_at)
    return f"Last saved {stamp}"


def _lease_conflict_message() -> str:
    conflict = st.session_state.get("_worksave_lease_conflict") or {}
    expires_at = conflict.get("expires_at", "")
    try:
        expires = datetime.fromisoformat(str(expires_at)).astimezone().strftime("%H:%M:%S")
    except ValueError:
        expires = "soon"
    return f"That user is already active in another session. Try again after {expires}, or ask them to end their autosave session."


def _release_current_save_user() -> None:
    user = st.session_state.get("save_user", "")
    if user:
        worksave.release_user_lease(user)
    _clear_save_context()
    st.session_state.pop("_worksave_lease_conflict", None)
    _reset_user_selector()
    st.rerun()


def _sidebar_save_controls() -> None:
    st.sidebar.markdown("---")
    users = _save_users()
    current = st.session_state.get("save_user", "")
    if current and not worksave.ensure_user_lease(current):
        _clear_save_context()
        _reset_user_selector()
        current = ""
    options = [_USER_PLACEHOLDER, *users]
    if current and current not in users:
        options.append(current)
    locked = bool(current)
    selector_key = _user_selector_key()
    st.sidebar.selectbox(
        "User",
        options,
        index=options.index(current) if current in options else 0,
        key=selector_key,
        on_change=_on_user_change,
        args=(selector_key,),
        disabled=locked,
        help=(
            "User is locked for this session. Use End autosave session to switch."
            if locked
            else "Pick your name so your work is auto-saved to your own file."
        ),
    )
    if st.session_state.get("_worksave_lease_conflict"):
        st.sidebar.error(_lease_conflict_message())

    user = st.session_state.get("save_user", "")
    blocked = bool(st.session_state.get("_worksave_lease_conflict"))
    if st.sidebar.button(
        "💾 Save now",
        use_container_width=True,
        disabled=not user or blocked or not st.session_state.get("items"),
    ):
        saved_at = worksave.save_workspace(user)
        if saved_at:
            st.session_state["_worksave_saved_at"] = saved_at
    if locked and st.sidebar.button("End autosave session", use_container_width=True):
        _release_current_save_user()
    st.sidebar.caption(_last_saved_caption())

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
    """SKU switcher for the Review page — plain button row, no decorative pills.
    Child SKUs (ATR Type == '') are rendered disabled; they are never worked on
    directly but instead via the parent's Var Opts tab.
    """
    items = st.session_state.get("items", {})
    if not items:
        return

    # Build a lookup of ATR Type from queue_df so we can identify children.
    queue_df = st.session_state.get("queue_df")
    atr_by_ino: dict[str, str] = {}
    if queue_df is not None and not queue_df.empty and "Item No" in queue_df.columns:
        for _, qrow in queue_df.iterrows():
            qino = str(qrow["Item No"]).strip()
            if qino:
                atr_by_ino[qino] = str(qrow.get("ATR Type", "")).strip()

    current_ino = st.session_state.get("current_item_no", "")
    ino_list    = list(items.keys())
    cols        = st.columns(min(len(ino_list), 10))
    clicked_ino = None
    for i, ino in enumerate(ino_list):
        atr = atr_by_ino.get(ino, "Standalone")
        is_child = atr == ""
        is_active = ino == current_ino
        if cols[i % len(cols)].button(
            ino,
            key=f"reviewbar_sku_{ino}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
            disabled=is_child,
            help="Child variants are configured under the parent's Var Opts tab." if is_child else None,
        ):
            clicked_ino = ino

    if clicked_ino and clicked_ino != current_ino:
        set_current_item(clicked_ino)
        st.session_state["workspace_tab"] = "Content"
        st.rerun()
