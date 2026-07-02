from __future__ import annotations

import streamlit as st

from sku_manager.pages import description, features, general, highlights, preview_export, specs
from sku_manager.state import current_item, sync_description_state
from sku_manager.ui.layout import workspace_topbar


def _render_selling_points() -> None:
    st.markdown("### Feature Bullets")
    features.render(show_header=False)
    st.markdown('<div class="vo-divider"></div>', unsafe_allow_html=True)
    st.markdown("### PDP Highlights")
    highlights.render(show_header=False)


def render() -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return

    sync_description_state(item)

    active_tab = workspace_topbar()

    st.markdown("<div class='vo-workspace-content-gap'></div>", unsafe_allow_html=True)

    if active_tab == "Basics":
        general.render(show_header=False)
    elif active_tab == "Description":
        description.render(show_header=False)
    elif active_tab == "Features & Highlights":
        _render_selling_points()
    elif active_tab == "Specs":
        specs.render(show_header=False)
    else:
        preview_export.render(show_header=False)