"""Tests for parent/child/standalone relationship logic
(sku_manager/services/relationships.py)."""
from __future__ import annotations

import pandas as pd

from sku_manager.services.relationships import (
    ROLE_CHILD,
    ROLE_PARENT,
    ROLE_STANDALONE,
    apply_relationships,
    current_relationships,
)


def _queue(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["ATR Type", "JIRA", "Item No", "Title", "Mfg Item", "Status"])


def _standalone_queue():
    return _queue(
        [
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "P1", "Title": "Parent", "Mfg Item": "", "Status": ""},
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "C1", "Title": "Child", "Mfg Item": "", "Status": ""},
        ]
    )


# ── current_relationships: reading roles out of the queue encoding ───────────
def test_current_relationships_classifies_roles():
    queue = _queue(
        [
            {"ATR Type": "Parent (1)", "JIRA": "", "Item No": "P1", "Title": "Parent", "Mfg Item": "", "Status": ""},
            {"ATR Type": "", "JIRA": "", "Item No": "C1", "Title": "Child", "Mfg Item": "", "Status": ""},
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "S1", "Title": "Solo", "Mfg Item": "", "Status": ""},
        ]
    )
    records = {r["item_no"]: r for r in current_relationships(queue)}
    assert records["P1"]["role"] == ROLE_PARENT
    assert records["C1"]["role"] == ROLE_CHILD
    assert records["C1"]["parent_sku"] == "P1"
    assert records["S1"]["role"] == ROLE_STANDALONE


def test_current_relationships_empty_df():
    assert current_relationships(pd.DataFrame()) == []


# ── apply_relationships: rewriting roles ─────────────────────────────────────
def test_apply_promotes_standalone_to_parent():
    queue = _standalone_queue()
    new_queue, warnings = apply_relationships(queue, {"C1": (ROLE_CHILD, "P1")})
    records = {r["item_no"]: r for r in current_relationships(new_queue)}
    assert records["P1"]["role"] == ROLE_PARENT
    assert records["C1"]["role"] == ROLE_CHILD
    assert any("promoted to Parent" in w for w in warnings)


def test_apply_child_without_parent_falls_back():
    queue = _standalone_queue()
    new_queue, warnings = apply_relationships(queue, {"C1": (ROLE_CHILD, "")})
    records = {r["item_no"]: r for r in current_relationships(new_queue)}
    assert records["C1"]["role"] == ROLE_STANDALONE
    assert any("without a parent" in w for w in warnings)


def test_apply_child_of_self_falls_back():
    queue = _standalone_queue()
    _, warnings = apply_relationships(queue, {"P1": (ROLE_CHILD, "P1")})
    assert any("its own parent" in w for w in warnings)


def test_apply_parent_not_in_batch_falls_back():
    queue = _standalone_queue()
    _, warnings = apply_relationships(queue, {"C1": (ROLE_CHILD, "GHOST")})
    assert any("not in this batch" in w for w in warnings)


def test_apply_reorders_children_under_parent():
    queue = _queue(
        [
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "P1", "Title": "Parent", "Mfg Item": "", "Status": ""},
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "S1", "Title": "Solo", "Mfg Item": "", "Status": ""},
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "C1", "Title": "Child", "Mfg Item": "", "Status": ""},
        ]
    )
    new_queue, _ = apply_relationships(
        queue, {"P1": (ROLE_PARENT, ""), "C1": (ROLE_CHILD, "P1")}
    )
    order = new_queue["Item No"].tolist()
    # Child must sit immediately after its parent, before the standalone.
    assert order == ["P1", "C1", "S1"]


def test_apply_parent_label_shows_child_count():
    queue = _queue(
        [
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "P1", "Title": "Parent", "Mfg Item": "", "Status": ""},
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "C1", "Title": "Child A", "Mfg Item": "", "Status": ""},
            {"ATR Type": "Standalone", "JIRA": "", "Item No": "C2", "Title": "Child B", "Mfg Item": "", "Status": ""},
        ]
    )
    new_queue, _ = apply_relationships(
        queue, {"P1": (ROLE_PARENT, ""), "C1": (ROLE_CHILD, "P1"), "C2": (ROLE_CHILD, "P1")}
    )
    parent_row = new_queue[new_queue["Item No"] == "P1"].iloc[0]
    assert parent_row["ATR Type"] == "Parent (2)"
