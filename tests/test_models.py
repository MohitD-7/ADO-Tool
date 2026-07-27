"""Tests for the item-record factory (sku_manager/models.py)."""
from __future__ import annotations

from sku_manager.models import new_item_record


def test_new_item_record_sets_identity():
    item = new_item_record(item_no="SKU-1", title="Title", mfg_item="MFG-1")
    assert item["details"]["item_no"] == "SKU-1"
    assert item["details"]["title"] == "Title"
    assert item["details"]["mfg_item"] == "MFG-1"


def test_new_item_record_seeds_input_snapshot():
    # input_title / input_mfg_item are the frozen "as uploaded" values.
    item = new_item_record(item_no="SKU-1", title="Title", mfg_item="MFG-1")
    assert item["details"]["input_title"] == "Title"
    assert item["details"]["input_mfg_item"] == "MFG-1"


def test_new_item_record_has_empty_collections():
    item = new_item_record(item_no="SKU-1")
    assert item["features"] == []
    assert item["specs"] == []
    assert item["highlights"] == []
    assert item["includes"] == []


def test_new_item_record_independent_copies():
    # Two records must not share the same nested list objects.
    a = new_item_record(item_no="A")
    b = new_item_record(item_no="B")
    a["features"].append("x")
    assert b["features"] == []
