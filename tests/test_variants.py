"""Tests for variant-option ("Var Opts" / "wear off") logic
(sku_manager/services/variants.py)."""
from __future__ import annotations

import pandas as pd

from sku_manager.services.variants import (
    build_variant_df,
    parent_child_groups,
    variant_completeness,
)


def _queue(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["ATR Type", "Item No", "Title"])


def _pc_queue():
    return _queue(
        [
            {"ATR Type": "Parent (2)", "Item No": "P1", "Title": "Parent"},
            {"ATR Type": "", "Item No": "C1", "Title": "Child A"},
            {"ATR Type": "", "Item No": "C2", "Title": "Child B"},
            {"ATR Type": "Standalone", "Item No": "S1", "Title": "Solo"},
        ]
    )


# ── parent_child_groups ──────────────────────────────────────────────────────
def test_groups_basic():
    groups = parent_child_groups(_pc_queue())
    assert len(groups) == 1
    assert groups[0]["parent_sku"] == "P1"
    assert [c["sku"] for c in groups[0]["children"]] == ["C1", "C2"]


def test_groups_standalone_closes_group():
    # S1 (standalone) after the children must not be swept into the group.
    groups = parent_child_groups(_pc_queue())
    child_skus = [c["sku"] for c in groups[0]["children"]]
    assert "S1" not in child_skus


def test_groups_childless_parent_dropped():
    queue = _queue([{"ATR Type": "Parent (0)", "Item No": "P1", "Title": "Lonely parent"}])
    assert parent_child_groups(queue) == []


def test_groups_empty_queue():
    assert parent_child_groups(pd.DataFrame()) == []


# ── variant_completeness ─────────────────────────────────────────────────────
def test_completeness_all_filled():
    variants = {"P1": {"attributes": ["Color"], "values": {"C1": {"Color": "Red"}, "C2": {"Color": "Blue"}}}}
    complete, problems = variant_completeness(_pc_queue(), variants)
    assert complete is True
    assert problems == []


def test_completeness_untouched_parent_is_skipped():
    # A parent with no attributes defined yet hasn't been started - it should
    # be skipped (excluded from the export) rather than blocking the download.
    variants = {"P1": {"attributes": [], "values": {}}}
    complete, problems = variant_completeness(_pc_queue(), variants)
    assert complete is True
    assert problems == []


def test_completeness_missing_child_value():
    variants = {"P1": {"attributes": ["Color"], "values": {"C1": {"Color": "Red"}}}}  # C2 missing
    complete, problems = variant_completeness(_pc_queue(), variants)
    assert complete is False
    assert any("C2" in p for p in problems)


def test_completeness_no_groups():
    complete, problems = variant_completeness(pd.DataFrame(), {})
    assert complete is False
    assert problems  # a non-empty explanation


def test_completeness_one_parent_filled_other_untouched():
    # Two parents: P1 fully filled, P2 never started. Should be downloadable -
    # P2 is simply left out of the export, not treated as blocking.
    queue = _queue(
        [
            {"ATR Type": "Parent (2)", "Item No": "P1", "Title": "Parent 1"},
            {"ATR Type": "", "Item No": "C1", "Title": "Child A"},
            {"ATR Type": "", "Item No": "C2", "Title": "Child B"},
            {"ATR Type": "Parent (1)", "Item No": "P2", "Title": "Parent 2"},
            {"ATR Type": "", "Item No": "C3", "Title": "Child C"},
        ]
    )
    variants = {
        "P1": {"attributes": ["Color"], "values": {"C1": {"Color": "Red"}, "C2": {"Color": "Blue"}}},
        # P2 untouched - no attributes defined.
    }
    complete, problems = variant_completeness(queue, variants)
    assert complete is True
    assert problems == []


# ── build_variant_df ─────────────────────────────────────────────────────────
def test_build_variant_df_rows():
    variants = {"P1": {"attributes": ["Color"], "values": {"C1": {"Color": "Red"}, "C2": {"Color": "Blue"}}}}
    df = build_variant_df(_pc_queue(), variants)
    assert list(df.columns) == ["PSKU", "CSEQ", "CSKU", "ASEQ", "ATTRIBUTE", "VALUE", "DISCONT"]
    assert df["VALUE"].tolist() == ["Red", "Blue"]


def test_build_variant_df_sequences_increment():
    variants = {"P1": {"attributes": ["Color", "Size"], "values": {
        "C1": {"Color": "Red", "Size": "S"}, "C2": {"Color": "Blue", "Size": "L"}}}}
    df = build_variant_df(_pc_queue(), variants)
    c1 = df[df["CSKU"] == "C1"]
    assert c1["CSEQ"].tolist() == [10, 10]      # same child shares one CSEQ
    assert c1["ASEQ"].tolist() == [10, 20]      # attributes step 10, 20
    assert df[df["CSKU"] == "C2"]["CSEQ"].tolist() == [20, 20]
