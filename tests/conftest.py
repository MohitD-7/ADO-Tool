"""Shared fixtures and small data builders for the test suite.

The app's business logic lives in sku_manager/services and sku_manager/state.
These fixtures build the minimal in-memory shapes those functions expect
(rules frames, item records, parent/child batches) so each test can exercise
one behaviour in isolation without the Streamlit UI running.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sku_manager.models import new_item_record
from sku_manager.services.relationships import ROLE_CHILD, ROLE_PARENT, apply_relationships


@pytest.fixture(autouse=True)
def _clear_session_state():
    """Streamlit's session_state is process-global in bare mode, so wipe it
    between tests to stop one test's state leaking into the next."""
    import streamlit as st
    try:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
    except Exception:
        pass
    yield


@pytest.fixture
def rules_df() -> pd.DataFrame:
    """A small, controlled special-character rule table.

    Deterministic on purpose - not loaded from reference_data.json - so these
    tests never break just because someone edits the live rule list.
    """
    return pd.DataFrame(
        [
            {"Symbol": "“", "Action required": "Replace", "Replace Value": '"', "Symbol Meaning": "Curly open quote"},
            {"Symbol": "”", "Action required": "Replace", "Replace Value": '"', "Symbol Meaning": "Curly close quote"},
            {"Symbol": "—", "Action required": "Replace", "Replace Value": "-", "Symbol Meaning": "Em dash"},
            {"Symbol": "grey", "Action required": "Replace", "Replace Value": "gray", "Symbol Meaning": "Grey to gray"},
            {"Symbol": "©", "Action required": "Delete", "Replace Value": "", "Symbol Meaning": "Copyright"},
        ]
    )


@pytest.fixture
def empty_rules() -> pd.DataFrame:
    return pd.DataFrame(columns=["Symbol", "Action required", "Replace Value", "Symbol Meaning"])


@pytest.fixture
def valid_item() -> dict:
    """A SKU that passes every submit_blockers() check."""
    return {
        "details": {
            "item_no": "SKU-1",
            "title": "A Title",
            "short_title": "Short",
            "description": "Description text",
            "mfg_model": "Model-1",
            "battery_info": "no battery used",
        },
        "features": ["Feature one", "Feature two"],
        "specs": [
            {"Spec": "Color", "Value": "Black"},
            {"Spec": "Weight", "Value": "1kg"},
        ],
        "highlights": ["Highlight one"],
        "includes": [{"text": "USB cable", "sku": ""}],
        "links": {"general": ["https://example.com/source"]},
    }


def make_parent_child_batch() -> tuple[pd.DataFrame, dict]:
    """A queue of one parent (P1) with two children (C1, C2), wired through the
    real relationship editor so ATR labels/order match production exactly."""
    queue = pd.DataFrame(
        {
            "ATR Type": ["Standalone", "Standalone", "Standalone"],
            "JIRA": ["", "", ""],
            "Item No": ["P1", "C1", "C2"],
            "Title": ["Parent Item", "Child A", "Child B"],
            "Mfg Item": ["MP1", "MC1", "MC2"],
            "Status": ["", "", ""],
        }
    )
    items = {
        row["Item No"]: new_item_record(
            item_no=row["Item No"], title=row["Title"], mfg_item=row["Mfg Item"], atr_type=row["ATR Type"]
        )
        for _, row in queue.iterrows()
    }
    assignments = {
        "P1": (ROLE_PARENT, ""),
        "C1": (ROLE_CHILD, "P1"),
        "C2": (ROLE_CHILD, "P1"),
    }
    new_queue, _ = apply_relationships(queue, assignments)
    for _, row in new_queue.iterrows():
        items[str(row["Item No"]).strip()]["details"]["atr_type"] = str(row["ATR Type"])
    return new_queue, items


@pytest.fixture
def parent_child_batch() -> tuple[pd.DataFrame, dict]:
    return make_parent_child_batch()


@pytest.fixture
def variants_data() -> dict:
    """Var Opts ("wear off") data matching the parent_child_batch fixture."""
    return {
        "P1": {
            "attributes": ["Color"],
            "values": {"C1": {"Color": "Red"}, "C2": {"Color": "Blue"}},
        }
    }
