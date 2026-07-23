from __future__ import annotations

import time

import streamlit as st

from sku_manager.config import APP_TITLE
from sku_manager.frontend_patch import ensure_visible_row_checkboxes
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
from sku_manager.services import metrics, worksave
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


def _maybe_restore_saved_work() -> None:
    """Bring back the picked user's saved work without making them ask for it.

    An empty session restores the save automatically (uploading a new batch
    replaces it anyway, so this is always safe). Only when the session already
    holds work AND a save exists does the user get an explicit choice; until
    they choose, auto-save stays off so the saved file cannot be clobbered.
    """
    notice = st.session_state.pop("_worksave_restore_notice", None)
    if notice:
        st.toast(notice, icon="✅")

    user = st.session_state.get("save_user", "")
    if not user or st.session_state.get("_worksave_restore_handled"):
        return
    payload = worksave.load_workspace(user)
    if not payload:
        st.session_state["_worksave_restore_handled"] = True
        return

    saved_items = len(payload.get("items") or {})
    if not st.session_state.get("items"):
        worksave.restore_workspace(payload)
        worksave.mark_workspace_clean()
        st.session_state["_worksave_restore_handled"] = True
        st.session_state["_worksave_restore_notice"] = (
            f"Restored {saved_items} saved SKU(s) for {user}."
        )
        st.rerun()

    loaded_items = len(st.session_state.get("items") or {})
    st.warning(
        f"**{user}** has saved work from {payload.get('saved_at', '')} "
        f"({saved_items} SKU(s)), but this session already has {loaded_items} "
        "SKU(s) loaded. Pick which one to keep - auto-save is paused until you do."
    )
    load_col, keep_col, _ = st.columns([1, 1, 2])
    if load_col.button(
        "Load saved work",
        type="primary",
        use_container_width=True,
        help="Replaces what is currently loaded in this session.",
    ):
        worksave.restore_workspace(payload)
        worksave.mark_workspace_clean()
        st.session_state["_worksave_restore_handled"] = True
        st.rerun()
    if keep_col.button(
        "Keep what's loaded here",
        use_container_width=True,
        help="Auto-save resumes and replaces the old save as you work.",
    ):
        st.session_state["_worksave_restore_handled"] = True
        st.rerun()


def main() -> None:
    ensure_visible_row_checkboxes()
    st.set_page_config(
        page_title=APP_TITLE,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    t0 = time.perf_counter()
    with metrics.timer("init_state"):
        init_state()
    worksave.purge_expired_files_once()
    with metrics.timer("styles"):
        inject_styles()
        enable_global_spellcheck()
    sync_description_state()
    with metrics.timer("sidebar_nav"):
        page = sidebar_nav()
    _maybe_restore_saved_work()
    with metrics.timer("page_render"):
        PAGE_RENDERERS[page]()
    with metrics.timer("autosave_tick"):
        worksave.autosave_tick()
    metrics.record_render((time.perf_counter() - t0) * 1000)