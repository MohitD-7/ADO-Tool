"""Tests for uploaded-workbook reading (sku_manager/services/workbook_io.py)."""
from __future__ import annotations

from io import BytesIO

import pandas as pd

from sku_manager.services.workbook_io import canonicalize_columns, read_queue_workbook


def _excel_bytes(df: pd.DataFrame) -> BytesIO:
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer


# ── header canonicalisation ──────────────────────────────────────────────────
def test_canonicalize_columns_aliases():
    df = pd.DataFrame(columns=["SKU", "Product Title", "MFGItem#", "JIRA#"])
    out = canonicalize_columns(df)
    assert "Item No" in out.columns
    assert "Title" in out.columns
    assert "Mfg Item" in out.columns
    assert "JIRA" in out.columns


# ── read_queue_workbook ──────────────────────────────────────────────────────
def test_read_valid_workbook():
    df = pd.DataFrame({"Item No": ["A1"], "Title": ["Thing"], "Mfg Item": ["M1"]})
    result = read_queue_workbook(_excel_bytes(df))
    assert result.ok is True
    assert result.queue_df.iloc[0]["Item No"] == "A1"


def test_read_missing_required_columns():
    df = pd.DataFrame({"Title": ["Thing"]})
    result = read_queue_workbook(_excel_bytes(df))
    assert result.ok is False
    assert "Item No" in result.missing_columns
    assert "Mfg Item" in result.missing_columns


def test_read_adds_status_column():
    df = pd.DataFrame({"Item No": ["A1"], "Title": ["Thing"], "Mfg Item": ["M1"]})
    result = read_queue_workbook(_excel_bytes(df))
    assert "Status" in result.queue_df.columns


def test_read_groups_child_under_parent():
    df = pd.DataFrame(
        {
            "ATR Type": ["Parent", "P1"],   # C1's ATR "P1" means "child of P1"
            "Item No": ["P1", "C1"],
            "Title": ["Parent", "Child"],
            "Mfg Item": ["MP", "MC"],
        }
    )
    result = read_queue_workbook(_excel_bytes(df))
    order = result.queue_df["Item No"].tolist()
    assert order == ["P1", "C1"]
    labels = dict(zip(result.queue_df["Item No"], result.queue_df["ATR Type"]))
    assert labels["P1"] == "Parent (1)"
    assert labels["C1"] == ""


def test_read_standalone_labeling():
    df = pd.DataFrame({"Item No": ["A1"], "Title": ["Thing"], "Mfg Item": ["M1"]})
    result = read_queue_workbook(_excel_bytes(df))
    assert result.queue_df.iloc[0]["ATR Type"] == "Standalone"


def test_read_duplicate_alias_columns_gives_friendly_message():
    # "ATR" and "Relationship" both canonicalize to "ATR Type" - without a
    # guard this used to crash with a raw pandas ValueError deep in a helper.
    df = pd.DataFrame(
        {
            "Item No": ["A1"],
            "Title": ["Thing"],
            "Mfg Item": ["M1"],
            "ATR": ["Parent"],
            "Relationship": ["Parent"],
        }
    )
    result = read_queue_workbook(_excel_bytes(df))
    assert result.ok is False
    assert "ATR" in result.message
    assert "Relationship" in result.message
    assert "ATR Type" in result.message
