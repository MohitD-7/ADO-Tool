from __future__ import annotations

import streamlit as st

from sku_manager.config import APP_TITLE
from sku_manager.pages import (
    description,
    editor_rules,
    features,
    general,
    highlights,
    preview_export,
    queue,
    reference_data,
    review,
    specs,
    upload,
    workspace,
)
from sku_manager.services import worksave
from sku_manager.state import init_state, sync_description_state
from sku_manager.styles import inject_styles
from sku_manager.ui.components import enable_global_spellcheck
from sku_manager.ui.layout import sidebar_nav


PAGE_RENDERERS = {
    "Upload": upload.render,
    "SKU Batch": queue.render,
    "SKU Workspace": workspace.render,
    "General": general.render,
    "Description": description.render,
    "Features": features.render,
    "Specs": specs.render,
    "Highlights": highlights.render,
    "Preview & Export": preview_export.render,
    "Reference Data": reference_data.render,
    "Editor Rules": editor_rules.render,
    "Review": review.render,
}


def _maybe_offer_restore() -> None:
    """Offer to restore the picked user's saved work when the session is empty."""
    user = st.session_state.get("save_user", "")
    if not user or st.session_state.get("_worksave_restore_handled"):
        return
    if st.session_state.get("items"):
        st.session_state["_worksave_restore_handled"] = True
        return
    payload = worksave.load_workspace(user)
    if not payload:
        st.session_state["_worksave_restore_handled"] = True
        return

    saved_at = payload.get("saved_at", "")
    item_count = len(payload.get("items") or {})
    st.info(
        f"Found saved work for **{user}** from {saved_at} — {item_count} SKU(s). "
        f"Items expire {worksave.EXPIRY_HOURS // 24} days after their last edit."
    )
    restore_col, fresh_col, _ = st.columns([1, 1, 3])
    if restore_col.button("Restore saved work", type="primary", use_container_width=True):
        worksave.restore_workspace(payload)
        st.session_state["_worksave_restore_handled"] = True
        st.session_state["_worksave_digest"] = worksave.workspace_digest()
        st.rerun()
    if fresh_col.button("Start fresh", use_container_width=True):
        st.session_state["_worksave_restore_handled"] = True
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    worksave.purge_expired_files_once()
    inject_styles()
    enable_global_spellcheck()
    sync_description_state()
    page = sidebar_nav()
    _maybe_offer_restore()
    PAGE_RENDERERS[page]()
    worksave.autosave_tick()