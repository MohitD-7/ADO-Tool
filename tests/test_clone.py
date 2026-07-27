"""Tests for the "Similar To" clone (sku_manager/state.clone_item_from_similar).

Guards the 2026-07-25 fixes: MFG Item must now clone, the target's identity
(item_no / input snapshot) must stay put, and the category must come across.
"""
from __future__ import annotations

import streamlit as st

from sku_manager.models import new_item_record
from sku_manager.state import clone_item_from_similar


def _seed_two_items() -> None:
    source = new_item_record(item_no="SRC", title="Source Title", mfg_item="MFG-SRC")
    source["details"].update(
        {
            "short_title": "Short Source",
            "description": "Source description",
            "mfg_model": "Model-SRC",
            "category": "A>>B>>C",
        }
    )
    source["features"] = ["F1", "F2"]
    target = new_item_record(item_no="TGT", title="Target Title", mfg_item="MFG-TGT")
    st.session_state["items"] = {"SRC": source, "TGT": target}


def test_clone_copies_core_fields():
    _seed_two_items()
    assert clone_item_from_similar("TGT", "SRC") is True
    tgt = st.session_state["items"]["TGT"]["details"]
    assert tgt["title"] == "Source Title"
    assert tgt["short_title"] == "Short Source"
    assert tgt["description"] == "Source description"
    assert tgt["mfg_model"] == "Model-SRC"


def test_clone_copies_mfg_item():
    # 2026-07-25 fix: mfg_item used to be excluded from cloning.
    _seed_two_items()
    clone_item_from_similar("TGT", "SRC")
    assert st.session_state["items"]["TGT"]["details"]["mfg_item"] == "MFG-SRC"


def test_clone_copies_category():
    _seed_two_items()
    clone_item_from_similar("TGT", "SRC")
    assert st.session_state["items"]["TGT"]["details"]["category"] == "A>>B>>C"


def test_clone_copies_lists():
    _seed_two_items()
    clone_item_from_similar("TGT", "SRC")
    assert st.session_state["items"]["TGT"]["features"] == ["F1", "F2"]


def test_clone_preserves_target_identity():
    _seed_two_items()
    clone_item_from_similar("TGT", "SRC")
    tgt = st.session_state["items"]["TGT"]["details"]
    assert tgt["item_no"] == "TGT"                 # never overwritten
    assert tgt["input_title"] == "Target Title"    # frozen upload snapshot kept
    assert tgt["input_mfg_item"] == "MFG-TGT"


def test_clone_resets_category_widget_key():
    # 2026-07-25 fix: the category selectbox must remount so it doesn't keep
    # showing the target's stale selection after a clone.
    _seed_two_items()
    st.session_state["category_select_TGT"] = "old-value"
    clone_item_from_similar("TGT", "SRC")
    assert "category_select_TGT" not in st.session_state


def test_clone_same_source_and_target_is_noop():
    _seed_two_items()
    assert clone_item_from_similar("TGT", "TGT") is False


def test_clone_missing_source_returns_false():
    _seed_two_items()
    assert clone_item_from_similar("TGT", "GHOST") is False
