from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

import pandas as pd

from sku_manager.config import QUEUE_COLUMNS


REQUIRED_COLUMNS = ["Item No", "Title", "Mfg Item"]

ALIASES = {
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

    queue_df = df[REQUIRED_COLUMNS].copy()
    queue_df = queue_df.rename(columns={col: col for col in REQUIRED_COLUMNS})
    queue_df["Status"] = ""
    queue_df["Done By"] = ""
    queue_df = queue_df[QUEUE_COLUMNS]
    queue_df = queue_df[queue_df["Item No"].astype(str).str.strip() != ""]
    return WorkbookLoadResult(True, queue_df, [], original_columns)
