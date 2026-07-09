from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import BinaryIO

import pandas as pd

from sku_manager.config import QUEUE_COLUMNS


REQUIRED_COLUMNS = ["Item No", "Title", "Mfg Item"]
ATR_COLUMN = "ATR Type"
JIRA_COLUMN = "JIRA"

ALIASES = {
    "atr": ATR_COLUMN,
    "atr type": ATR_COLUMN,
    "atrtype": ATR_COLUMN,
    "parent child": ATR_COLUMN,
    "parent/child": ATR_COLUMN,
    "relationship": ATR_COLUMN,
    "jira": JIRA_COLUMN,
    "jira #": JIRA_COLUMN,
    "jira#": JIRA_COLUMN,
    "jira no": JIRA_COLUMN,
    "jira number": JIRA_COLUMN,
    "item no": "Item No",
    "item number": "Item No",
    "item#": "Item No",
    "item #": "Item No",
    "sku": "Item No",
    "sku item": "Item No",
    "title": "Title",
    "product title": "Title",
    "mfg item": "Mfg Item",
    "mfgitem": "Mfg Item",
    "mfgitem#": "Mfg Item",
    "mfgitem #": "Mfg Item",
    "manufacturer item": "Mfg Item",
    "mfr item": "Mfg Item",
    "mfg item no": "Mfg Item",
}


@dataclass
class WorkbookLoadResult:
    ok: bool
    queue_df: pd.DataFrame
    missing_columns: list[str]
    original_columns: list[str]
    message: str = ""


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in df.columns:
        normalized = str(column).strip().lower()
        if normalized in ALIASES:
            rename_map[column] = ALIASES[normalized]
    return df.rename(columns=rename_map)


def _clean(value) -> str:
    return str(value or "").strip()


def _sku_key(value) -> str:
    return _clean(value).lower()


def _is_parent_marker(value) -> bool:
    text = _clean(value).lower()
    return text == "parent" or text.startswith("parent (")


def _child_parent_sku(value) -> str:
    text = _clean(value)
    if not text or _is_parent_marker(text):
        return ""
    lower = text.lower()
    if lower.startswith("child of "):
        return text[len("child of "):].strip()
    return text


def _relationship_queue(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if ATR_COLUMN not in work.columns:
        work[ATR_COLUMN] = ""
    if JIRA_COLUMN not in work.columns:
        work[JIRA_COLUMN] = ""

    for column in [ATR_COLUMN, JIRA_COLUMN, *REQUIRED_COLUMNS]:
        work[column] = work[column].fillna("").astype(str).map(_clean)

    work = work[work["Item No"] != ""].copy()
    if work.empty:
        return pd.DataFrame(columns=[ATR_COLUMN, JIRA_COLUMN, *REQUIRED_COLUMNS])

    child_rows_by_parent: dict[str, list[int]] = defaultdict(list)
    parent_indices_by_sku: dict[str, int] = {}

    for idx, row in work.iterrows():
        raw_atr = row[ATR_COLUMN]
        item_no = row["Item No"]
        if _is_parent_marker(raw_atr):
            parent_indices_by_sku[_sku_key(item_no)] = idx
            continue
        parent_sku = _child_parent_sku(raw_atr)
        if parent_sku:
            child_rows_by_parent[_sku_key(parent_sku)].append(idx)

    ordered_indices: list[int] = []
    seen: set[int] = set()

    def add_index(idx: int) -> None:
        if idx not in seen:
            ordered_indices.append(idx)
            seen.add(idx)

    for idx, row in work.iterrows():
        if idx in seen:
            continue
        raw_atr = row[ATR_COLUMN]
        item_no = row["Item No"]
        if _is_parent_marker(raw_atr):
            add_index(idx)
            for child_idx in child_rows_by_parent.get(_sku_key(item_no), []):
                add_index(child_idx)
            continue
        parent_sku = _child_parent_sku(raw_atr)
        if parent_sku and _sku_key(parent_sku) in parent_indices_by_sku:
            continue
        add_index(idx)

    for idx in work.index:
        add_index(idx)

    def label(row) -> str:
        raw_atr = row[ATR_COLUMN]
        item_no = row["Item No"]
        if _is_parent_marker(raw_atr):
            child_count = len(child_rows_by_parent.get(_sku_key(item_no), []))
            return f"Parent ({child_count})"
        parent_sku = _child_parent_sku(raw_atr)
        if parent_sku:
            return ""
        return "Standalone"

    work[ATR_COLUMN] = work.apply(label, axis=1)
    return work.loc[ordered_indices, [ATR_COLUMN, JIRA_COLUMN, *REQUIRED_COLUMNS]].reset_index(drop=True)


def read_queue_workbook(file: BinaryIO, sheet_name: str | int = 0) -> WorkbookLoadResult:
    try:
        df = pd.read_excel(file, sheet_name=sheet_name, dtype=str).fillna("")
    except Exception as exc:
        return WorkbookLoadResult(False, pd.DataFrame(), REQUIRED_COLUMNS, [], str(exc))

    original_columns = [str(col) for col in df.columns]
    df = canonicalize_columns(df)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return WorkbookLoadResult(False, pd.DataFrame(), missing, original_columns)

    queue_df = _relationship_queue(df)
    queue_df["Status"] = ""
    queue_df = queue_df[QUEUE_COLUMNS]
    return WorkbookLoadResult(True, queue_df, [], original_columns)