from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from sku_manager.data.defaults import (
    default_battery_materials,
    default_battery_types,
    default_checklist,
    default_html_template,
    default_manufacturers,
    default_special_character_rules,
)


REFERENCE_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "reference_data.json"

TABLE_DEFINITIONS = {
    "manufacturers_df": ("manufacturers", default_manufacturers),
    "battery_materials_df": ("battery_materials", default_battery_materials),
    "battery_types_df": ("battery_types", default_battery_types),
    "special_rules_df": ("special_rules", default_special_character_rules),
    "checklist_df": ("checklist", default_checklist),
}


def _coerce_frame(raw_rows: Any, default_factory) -> pd.DataFrame:
    default_df = default_factory()
    if isinstance(raw_rows, list):
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


def save_reference_data(state: Mapping[str, Any]) -> None:
    payload: dict[str, Any] = {}
    for state_key, (payload_key, default_factory) in TABLE_DEFINITIONS.items():
        df = _coerce_frame(state.get(state_key), default_factory)
        payload[payload_key] = df.to_dict("records")
    payload["html_template"] = str(state.get("html_template") or "")

    REFERENCE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
