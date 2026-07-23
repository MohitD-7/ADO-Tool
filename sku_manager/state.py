from __future__ import annotations

from copy import deepcopy

import pandas as pd
import streamlit as st

from sku_manager.config import QUEUE_COLUMNS
from sku_manager.models import DETAIL_DEFAULTS, new_item_record
from sku_manager.services.reference_store import TABLE_DEFINITIONS, get_reference_data


DESCRIPTION_PREFIX = "_desc_"
DESCRIPTION_WIDGET_SUFFIX = "_w"
DESCRIPTION_FORCE_SUFFIX = "_force"
DESCRIPTION_COMPONENT_SUFFIX = "_component"
DESCRIPTION_EVENT_SUFFIX = "_last_event"

_CLONE_PRESERVED_DETAIL_FIELDS = {
    "item_no",
    "mfg_item",
    "atr_type",
    "jira",
    "input_title",
    "input_mfg_item",
}


def init_state() -> None:
    defaults = {
        "queue_df": pd.DataFrame(columns=QUEUE_COLUMNS),
        "items": {},
        "variants": {},
        "current_item_no": "",
        "active_page": "Upload",
        "reference_data_admin": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    reference_keys = (*TABLE_DEFINITIONS.keys(), "html_template")
    if any(key not in st.session_state for key in reference_keys):
        for key, value in get_reference_data().items():
            if key not in st.session_state:
                st.session_state[key] = value


def has_batch() -> bool:
    return not st.session_state["queue_df"].empty


def clear_description_state() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(DESCRIPTION_PREFIX):
            del st.session_state[key]


def set_batch(queue_df: pd.DataFrame) -> None:
    clear_description_state()
    queue_df = queue_df.copy()
    had_atr_column = "ATR Type" in queue_df.columns
    for col in QUEUE_COLUMNS:
        if col not in queue_df.columns:
            queue_df[col] = ""
    if not had_atr_column:
        queue_df["ATR Type"] = "Standalone"
    queue_df = queue_df[QUEUE_COLUMNS].fillna("").astype(str)
    st.session_state["queue_df"] = queue_df
    st.session_state["items"] = {}
    st.session_state["variants"] = {}
    for _, row in queue_df.iterrows():
        item_no = str(row["Item No"]).strip()
        if not item_no:
            continue
        st.session_state["items"][item_no] = new_item_record(
            item_no=item_no,
            title=str(row["Title"]),
            mfg_item=str(row["Mfg Item"]),
            atr_type=str(row.get("ATR Type", "")),
        )
    st.session_state["current_item_no"] = next(iter(st.session_state["items"]), "")


def current_item() -> dict | None:
    item_no = st.session_state["current_item_no"]
    if not item_no:
        return None
    return st.session_state["items"].get(item_no)


def description_state_keys(item_no: str) -> tuple[str, str, str]:
    sync_key = f"{DESCRIPTION_PREFIX}{item_no}"
    widget_key = f"{sync_key}{DESCRIPTION_WIDGET_SUFFIX}"
    force_key = f"{sync_key}{DESCRIPTION_FORCE_SUFFIX}"
    return sync_key, widget_key, force_key


def set_description_state(item_no: str, value: str) -> None:
    sync_key, widget_key, force_key = description_state_keys(item_no)
    text = "" if value is None else str(value)
    st.session_state[sync_key] = text
    st.session_state[force_key] = text
    st.session_state.pop(widget_key, None)
    st.session_state.pop(f"{sync_key}{DESCRIPTION_COMPONENT_SUFFIX}", None)
    st.session_state.pop(f"{sync_key}{DESCRIPTION_EVENT_SUFFIX}", None)


def _should_reset_item_widget_key(state_key: str, item_no: str) -> bool:
    sync_key, widget_key, force_key = description_state_keys(item_no)
    exact_keys = {
        sync_key,
        widget_key,
        force_key,
        f"{sync_key}{DESCRIPTION_COMPONENT_SUFFIX}",
        f"{sync_key}{DESCRIPTION_EVENT_SUFFIX}",
        f"title_{item_no}",
        f"mfg_model_{item_no}",
        f"short_title_{item_no}",
        f"warranty_brand_{item_no}",
        f"warranty_months_{item_no}",
        f"similar_to_select_{item_no}",
        f"new_feature_{item_no}",
        f"features_bulk_{item_no}",
        f"highlights_bulk_{item_no}",
        f"inc_bulk_{item_no}",
        f"new_spec_cat_{item_no}",
        f"new_spec_grp_{item_no}",
        f"new_spec_key_{item_no}",
        f"new_spec_value_{item_no}",
        f"specs_editor_rev_{item_no}",
        f"specs_save_message_{item_no}",
    }
    internal_prefixes = (
        f"features_editor_{item_no}__",
        f"highlights_editor_{item_no}__",
        f"specs_editor_{item_no}_",
        f"includes_editor_{item_no}__",
        f"reorder_features_{item_no}_",
        f"reorder_highlights_{item_no}_",
        f"reorder_specs_{item_no}_",
        f"reorder_includes_{item_no}_",
        f"comment_{item_no}_",
    )
    item_suffix_prefixes = (
        "source_links_",
        "video_links_",
        "general_feedback_item_comment_",
        "content_feedback_item_comment_",
        "features_feedback_item_comment_",
        "specs_feedback_item_comment_",
        "highlights_feedback_item_comment_",
        "desc_item_comment_",
    )
    return (
        state_key in exact_keys
        or any(state_key.startswith(prefix) for prefix in internal_prefixes)
        or (
            state_key.endswith(f"_{item_no}")
            and any(state_key.startswith(prefix) for prefix in item_suffix_prefixes)
        )
    )


def reset_item_widget_state(item_no: str) -> None:
    item_no = str(item_no or "").strip()
    if not item_no:
        return
    for state_key in list(st.session_state.keys()):
        if _should_reset_item_widget_key(str(state_key), item_no):
            del st.session_state[state_key]


def clone_item_from_similar(target_item_no: str, source_item_no: str) -> bool:
    """Copy editable SKU content from source to target, preserving target identity."""
    target_item_no = str(target_item_no or "").strip()
    source_item_no = str(source_item_no or "").strip()
    if not target_item_no or not source_item_no or target_item_no == source_item_no:
        return False

    items = st.session_state.get("items", {})
    target = items.get(target_item_no)
    source = items.get(source_item_no)
    if not target or not source:
        return False

    target_details = target.get("details", {})
    preserved_details = {
        field: target_details.get(field, "")
        for field in _CLONE_PRESERVED_DETAIL_FIELDS
    }

    cloned = deepcopy(source)
    cloned_details = deepcopy(DETAIL_DEFAULTS)
    cloned_details.update(cloned.get("details", {}))
    cloned_details.update(preserved_details)
    cloned["details"] = cloned_details

    target.clear()
    target.update(cloned)
    reset_item_widget_state(target_item_no)
    set_description_state(target_item_no, cloned_details.get("description", ""))
    return True


def sync_description_state(item: dict | None = None) -> str:
    item = item if item is not None else current_item()
    if not item:
        return ""

    details = item["details"]
    item_no = str(details.get("item_no", "")).strip()
    if not item_no:
        return str(details.get("description", "") or "")

    sync_key, _, _ = description_state_keys(item_no)
    component_key = f"{sync_key}{DESCRIPTION_COMPONENT_SUFFIX}"
    component_result = st.session_state.get(component_key)
    if isinstance(component_result, dict) and component_result.get("value") is not None:
        # The CodeMirror component's own key - restored by Streamlit before any
        # on_click callback runs, so this reflects what's actually typed right
        # now. `sync_key` is a plain dict entry only refreshed by html_editor()'s
        # own script-body code, which hasn't run yet at callback time - reading
        # it here would silently reformat (or overwrite) stale, pre-edit text.
        value = component_result["value"]
    elif sync_key in st.session_state:
        value = st.session_state[sync_key]
    else:
        value = details.get("description", "")

    value = "" if value is None else str(value)
    st.session_state[sync_key] = value
    details["description"] = value
    return value


def set_current_item(item_no: str) -> None:
    sync_description_state()
    if item_no in st.session_state["items"]:
        st.session_state["current_item_no"] = item_no


def mark_status(item_no: str, status: str) -> None:
    queue = st.session_state["queue_df"].copy()
    mask = queue["Item No"].astype(str) == str(item_no)
    queue.loc[mask, "Status"] = status
    st.session_state["queue_df"] = queue


def sync_item_identity(item_no: str, title: str, mfg_item: str) -> None:
    """Seed title/mfg_item from the queue row only if the item has no value yet."""
    item = st.session_state["items"].get(item_no)
    if not item:
        return
    if not item["details"].get("title"):
        item["details"]["title"] = title
    if not item["details"].get("mfg_item"):
        item["details"]["mfg_item"] = mfg_item
    queue = st.session_state.get("queue_df")
    if queue is not None:
        match = queue[queue["Item No"].astype(str) == str(item_no)]
        if not match.empty:
            row = match.iloc[0]
            item["details"]["atr_type"] = str(row.get("ATR Type", ""))
            item["details"]["jira"] = str(row.get("JIRA", ""))
            item["details"]["input_title"] = str(row.get("Title", title))
            item["details"]["input_mfg_item"] = str(row.get("Mfg Item", mfg_item))