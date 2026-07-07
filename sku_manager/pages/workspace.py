from __future__ import annotations

import streamlit as st

from sku_manager.pages import description, features, general, highlights, preview_export, specs
from sku_manager.services.validation import item_warnings
from sku_manager.state import current_item, sync_description_state
from sku_manager.ui.components import links_panel, right_feedback_panel
from sku_manager.ui.layout import workspace_topbar


def _section_gap() -> None:
    st.markdown('<div class="vo-workspace-content-gap">&#8203;</div>', unsafe_allow_html=True)


def _render_content_tab(item: dict) -> None:
    main, pane = st.columns([3.5, 1])

    with main:
        general.render(
            show_header=False,
            embedded=True,
            show_links=False,
            show_feedback=False,
            show_format=False,
        )
        _section_gap()
        description.render(
            show_header=False,
            show_links=False,
            show_validation=False,
            show_item_notes=False,
        )
        _section_gap()
        st.markdown("### Feature Bullets")
        features.render(show_header=False, embedded=True, show_links=False, show_feedback=False)
        _section_gap()
        st.markdown("### PDP Highlights")
        highlights.render(show_header=False, embedded=True, show_links=False, show_feedback=False)
        _section_gap()
        links_panel(item, key_suffix="content")

    with pane:
        details = item["details"]
        right_feedback_panel(
            item,
            item_warnings(
                details,
                item["features"],
                item["specs"],
                item["highlights"],
                st.session_state.get("special_rules_df"),
                includes=item.get("includes", []),
            ),
            key_prefix="content_feedback",
        )


def render() -> None:
    item = current_item()
    if not item:
        st.warning("Upload and select a SKU first.")
        return

    sync_description_state(item)
    active_tab = workspace_topbar()

    st.markdown('<div class="vo-workspace-content-gap">&#8203;</div>', unsafe_allow_html=True)

    if active_tab == "Content":
        _render_content_tab(item)
    elif active_tab == "Specs":
        specs.render(show_header=False)
    else:
        preview_export.render(show_header=False)