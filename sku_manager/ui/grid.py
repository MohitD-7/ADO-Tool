from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st


def _normalise_frame(data: pd.DataFrame) -> pd.DataFrame:
    return data.copy().reset_index(drop=True)


def _frame_signature(df: pd.DataFrame) -> str:
    normalised = _normalise_frame(df).astype("object")
    normalised = normalised.where(pd.notna(normalised), "")
    payload = {
        "columns": [str(column) for column in normalised.columns],
        "rows": normalised.values.tolist(),
    }
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _coerce_cell(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return value


def _coerce_row(row: Mapping[str, Any], columns: list[str]) -> dict[str, Any]:
    return {column: _coerce_cell(row.get(column, "")) for column in columns}


def _row_index(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _apply_editor_state(base: pd.DataFrame, state: Mapping[str, Any], columns: list[str]) -> pd.DataFrame:
    df = _normalise_frame(base)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    df = df[columns]

    edited_rows = state.get("edited_rows", {})
    if isinstance(edited_rows, Mapping):
        for raw_index, changes in edited_rows.items():
            row_index = _row_index(raw_index)
            if row_index is None or row_index < 0 or row_index >= len(df):
                continue
            if not isinstance(changes, Mapping):
                continue
            for column, value in changes.items():
                if column in df.columns:
                    df.at[row_index, column] = _coerce_cell(value)

    edited_cells = state.get("edited_cells", {})
    if isinstance(edited_cells, Mapping):
        for cell, value in edited_cells.items():
            try:
                raw_index, column = str(cell).split(":", 1)
            except ValueError:
                continue
            row_index = _row_index(raw_index)
            if row_index is None or row_index < 0 or row_index >= len(df) or column not in df.columns:
                continue
            df.at[row_index, column] = _coerce_cell(value)

    deleted_rows = state.get("deleted_rows", [])
    if isinstance(deleted_rows, (list, tuple, set)):
        drop_indexes = sorted(
            {
                row_index
                for row_index in (_row_index(raw_index) for raw_index in deleted_rows)
                if row_index is not None and 0 <= row_index < len(df)
            },
            reverse=True,
        )
        if drop_indexes:
            df = df.drop(index=drop_indexes).reset_index(drop=True)

    added_rows = state.get("added_rows", [])
    if isinstance(added_rows, list) and added_rows:
        additions = [
            _coerce_row(row, columns)
            for row in added_rows
            if isinstance(row, Mapping)
        ]
        if additions:
            df = pd.concat([df, pd.DataFrame(additions, columns=columns)], ignore_index=True)

    return df.reset_index(drop=True)


def _widget_value_signature(base: pd.DataFrame, widget_state: Any) -> str:
    """Signature of the widget's effective value (baseline + pending deltas).

    Always computed through _apply_editor_state so that signatures from
    different runs compare against each other with identical cell coercion,
    independent of dtype quirks in st.data_editor's own return frame.
    """
    base_df = _normalise_frame(base)
    if not isinstance(widget_state, Mapping):
        return _frame_signature(base_df)
    columns = [str(column) for column in base_df.columns]
    return _frame_signature(_apply_editor_state(base_df, widget_state, columns))


def reset_stable_data_editor(key: str) -> None:
    """Forget all buffered state for a stable_data_editor instance."""
    prefixes = (
        f"{key}__widget_",
    )
    exact_keys = {
        f"{key}__data",
        f"{key}__dirty",  # written by the previous implementation; cleared for old sessions
        f"{key}__rev",
        f"{key}__source_sig",
        f"{key}__value_sig",
        f"{key}__value_changed",
    }
    for state_key in list(st.session_state.keys()):
        if state_key in exact_keys or any(state_key.startswith(prefix) for prefix in prefixes):
            del st.session_state[state_key]


def stable_data_editor(data: pd.DataFrame, *, key: str, **kwargs: Any) -> pd.DataFrame:
    """Render st.data_editor without losing in-flight edits to reruns.

    Callers rebuild ``data`` from the app model every rerun and write the
    returned frame (usually cleaned/formatted) back to the model. Feeding that
    rebuilt frame straight to st.data_editor changes the widget's baseline
    while the frontend still holds edit deltas against the old one, so the
    grid remounts and drops whatever the user is typing or pasting.

    Here the widget keeps a stable key and a stable baseline frame while the
    user edits, letting Streamlit accumulate the deltas natively — no remount,
    no lost input. The baseline is reseeded from ``data`` (remounting the
    widget) only when:

    - there is no live widget state, i.e. the first render or a return to a
      page whose widget state Streamlit already discarded; or
    - the source changed while the user was not editing the grid, meaning some
      other control mutated the model (add/clear buttons, reorder save,
      reference reload, format actions).

    The model changing because the page wrote back a transformed copy of the
    previous return value is expected and never reseeds the grid; the raw text
    stays visible while editing and converges on the next reseed. Call
    reset_stable_data_editor() before st.rerun() when a programmatic change
    must show up immediately in the same interaction.
    """
    source_df = _normalise_frame(data)
    source_signature = _frame_signature(source_df)

    base_key = f"{key}__data"
    source_sig_key = f"{key}__source_sig"
    revision_key = f"{key}__rev"
    value_sig_key = f"{key}__value_sig"
    value_changed_key = f"{key}__value_changed"

    if base_key not in st.session_state:
        st.session_state[base_key] = source_df
        st.session_state[revision_key] = 0

    revision = int(st.session_state.get(revision_key, 0))
    widget_key = f"{key}__widget_{revision}"
    widget_state = st.session_state.get(widget_key)

    reseeded = False
    if not isinstance(widget_state, Mapping):
        # No live widget, so no pending frontend edits to protect: mirror the
        # model directly (covers the first render and page revisits).
        if source_signature != _frame_signature(st.session_state[base_key]):
            st.session_state[base_key] = source_df
        reseeded = True
    elif source_signature != st.session_state.get(source_sig_key):
        pending_signature = _widget_value_signature(st.session_state[base_key], widget_state)
        edit_arrived_this_run = pending_signature != st.session_state.get(value_sig_key)
        edited_last_run = bool(st.session_state.get(value_changed_key))
        if not edit_arrived_this_run and not edited_last_run:
            # Out-of-band model change: adopt it and remount. Any stale deltas
            # were already written into the model by the page, so nothing the
            # user entered is lost.
            st.session_state[base_key] = source_df
            revision += 1
            st.session_state[revision_key] = revision
            widget_key = f"{key}__widget_{revision}"
            reseeded = True

    st.session_state[source_sig_key] = source_signature

    rendered = st.data_editor(
        st.session_state[base_key],
        key=widget_key,
        **kwargs,
    )

    value_signature = _widget_value_signature(
        st.session_state[base_key],
        st.session_state.get(widget_key),
    )
    previous_value_signature = st.session_state.get(value_sig_key)
    st.session_state[value_changed_key] = (
        not reseeded
        and previous_value_signature is not None
        and value_signature != previous_value_signature
    )
    st.session_state[value_sig_key] = value_signature

    return _normalise_frame(rendered)
