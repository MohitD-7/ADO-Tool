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


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    inject_styles()
    enable_global_spellcheck()
    sync_description_state()
    page = sidebar_nav()
    PAGE_RENDERERS[page]()