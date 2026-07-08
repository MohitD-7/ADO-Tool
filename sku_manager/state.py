from __future__ import annotations

import pandas as pd
import streamlit as st

from sku_manager.config import QUEUE_COLUMNS
from sku_manager.models import new_item_record
from sku_manager.services.reference_store import load_reference_data


DESCRIPTION_PREFIX = "_desc_"
DESCRIPTION_WIDGET_SUFFIX = "_w"
DESCRIPTION_FORCE_SUFFIX = "_force"
DESCRIPTION_COMPONENT_SUFFIX = "_component"
DESCRIPTION_EVENT_SUFFIX = "_last_event"


def init_state() -> None:
    reference_data = load_reference_data()
    defaults = {
        "queue_df": pd.DataFrame(columns=QUEUE_COLUMNS),
        "items": {},
        "current_item_no": "",
        "active_page": "Upload",
        "reference_data_admin": False,
        **reference_data,
    }
    for key, value in defaults.items():
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


def sync_description_state(item: dict | None = None) -> str:
    item = item if item is not None else current_item()
    if not item:
        return ""

    details = item["details"]
    item_no = str(details.get("item_no", "")).strip()
    if not item_no:
        return str(details.get("description", "") or "")

    sync_key, widget_key, _ = description_state_keys(item_no)
    if widget_key in st.session_state:
        value = st.session_state[widget_key]
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


def mark_status(item_no: str, status: str, done_by: str | None = None) -> None:
    queue = st.session_state["queue_df"].copy()
    mask = queue["Item No"].astype(str) == str(item_no)
    queue.loc[mask, "Status"] = status
    if done_by is not None:
        queue.loc[mask, "Done By"] = done_by
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
    if queue is not None and "ATR Type" in queue.columns:
        match = queue[queue["Item No"].astype(str) == str(item_no)]
        if not match.empty:
            item["details"]["atr_type"] = str(match.iloc[0].get("ATR Type", ""))