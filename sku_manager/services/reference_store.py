from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from sku_manager.data.defaults import (
    default_battery_materials,
    default_battery_types,
    default_category_mapping,
    default_html_template,
    default_special_character_rules,
    default_warranty,
)


REFERENCE_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "reference_data.json"

TABLE_DEFINITIONS = {
    "battery_materials_df": ("battery_materials", default_battery_materials),
    "battery_types_df": ("battery_types", default_battery_types),
    "special_rules_df": ("special_rules", default_special_character_rules),
    "warranty_df": ("warranty", default_warranty),
    "category_mapping_df": ("category_mapping", default_category_mapping),
}


def coerce_uploaded_frame(df: pd.DataFrame, state_key: str) -> pd.DataFrame:
    """Align an uploaded replacement table to a reference table's expected columns/types."""
    _, default_factory = TABLE_DEFINITIONS[state_key]
    return _coerce_frame(df.to_dict("records"), default_factory)

def _append_missing_default_rows(df: pd.DataFrame, default_df: pd.DataFrame) -> pd.DataFrame:
    """Keep existing reference rows, then append shipped default rows that are missing."""
    if "Symbol" not in df.columns or "Symbol" not in default_df.columns:
        return df

    existing_symbols = {str(value).strip() for value in df["Symbol"].tolist() if str(value).strip()}
    missing_rows = []
    for _, row in default_df.iterrows():
        symbol = str(row.get("Symbol", "")).strip()
        if not symbol or symbol in existing_symbols:
            continue
        missing_rows.append(row.to_dict())
        existing_symbols.add(symbol)

    if not missing_rows:
        return df
    return pd.concat([df, pd.DataFrame(missing_rows, columns=default_df.columns)], ignore_index=True)

def _coerce_frame(raw_rows: Any, default_factory) -> pd.DataFrame:
    default_df = default_factory()
    if isinstance(raw_rows, pd.DataFrame):
        df = raw_rows.copy()
    elif isinstance(raw_rows, list):
        df = pd.DataFrame(raw_rows)
    else:
        df = default_df.copy()

    for column in default_df.columns:
        if column not in df.columns:
            df[column] = default_df[column] if len(default_df) == len(df) else ""

    df = df[list(default_df.columns)].copy()
    for column in df.columns:
        if default_df[column].dtype == bool:
            df[column] = df[column].fillna(False).astype(bool)
        else:
            df[column] = df[column].fillna("").astype(str)

    if default_factory is default_special_character_rules:
        df = _append_missing_default_rows(df, default_df)
    return df


def load_reference_data() -> dict[str, Any]:
    raw: dict[str, Any] = {}
    if REFERENCE_DATA_PATH.exists():
        try:
            raw = json.loads(REFERENCE_DATA_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}

    data: dict[str, Any] = {}
    for state_key, (payload_key, default_factory) in TABLE_DEFINITIONS.items():
        data[state_key] = _coerce_frame(raw.get(payload_key), default_factory)
    data["html_template"] = str(raw.get("html_template") or default_html_template())
    return data


@st.cache_data(show_spinner=False)
def _load_reference_cached(mtime: float) -> dict[str, Any]:
    return load_reference_data()


def get_reference_data() -> dict[str, Any]:
    """Cached reference data, invalidated when reference_data.json changes on disk."""
    try:
        mtime = REFERENCE_DATA_PATH.stat().st_mtime
    except OSError:
        mtime = 0.0
    return _load_reference_cached(mtime)


def save_reference_data(state: Mapping[str, Any]) -> None:
    payload: dict[str, Any] = {}
    for state_key, (payload_key, default_factory) in TABLE_DEFINITIONS.items():
        df = _coerce_frame(state.get(state_key), default_factory)
        payload[payload_key] = df.to_dict("records")
    payload["html_template"] = str(state.get("html_template") or "")

    REFERENCE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _load_reference_cached.clear()
