"""Tests for submit gating and validation warnings
(sku_manager/services/validation.py)."""
from __future__ import annotations

from copy import deepcopy

from sku_manager.services.validation import char_count_status, item_warnings, submit_blockers


# ── char_count_status ────────────────────────────────────────────────────────
def test_char_count_under_limit():
    count, ok = char_count_status("abc", 10)
    assert count == 3 and ok is True


def test_char_count_over_limit():
    count, ok = char_count_status("abcdef", 3)
    assert count == 6 and ok is False


def test_char_count_none_is_zero():
    count, ok = char_count_status(None, 10)
    assert count == 0 and ok is True


# ── submit_blockers: a complete item passes ──────────────────────────────────
def test_valid_item_has_no_blockers(valid_item):
    assert submit_blockers(valid_item) == []


def test_blocker_missing_title(valid_item):
    valid_item["details"]["title"] = ""
    assert any("Title" in b for b in submit_blockers(valid_item))


def test_blocker_missing_short_title(valid_item):
    valid_item["details"]["short_title"] = ""
    assert any("Short Title" in b for b in submit_blockers(valid_item))


def test_blocker_missing_description(valid_item):
    valid_item["details"]["description"] = ""
    assert any("Description" in b for b in submit_blockers(valid_item))


def test_blocker_missing_mfg_model(valid_item):
    valid_item["details"]["mfg_model"] = ""
    assert any("MFG Model" in b for b in submit_blockers(valid_item))


def test_blocker_no_includes(valid_item):
    valid_item["includes"] = []
    assert any("Includes" in b for b in submit_blockers(valid_item))


def test_blocker_too_few_features(valid_item):
    valid_item["features"] = ["only one"]
    assert any("Features" in b for b in submit_blockers(valid_item))


def test_blocker_too_few_specs(valid_item):
    valid_item["specs"] = [{"Spec": "Color", "Value": "Black"}]
    assert any("Specs" in b for b in submit_blockers(valid_item))


def test_blocker_missing_battery_info(valid_item):
    valid_item["details"]["battery_info"] = ""
    assert any("Battery Info" in b for b in submit_blockers(valid_item))


def test_blocker_missing_source_link(valid_item):
    valid_item["links"]["general"] = []
    assert any("Source Link" in b for b in submit_blockers(valid_item))


def test_blocker_whitespace_only_source_link(valid_item):
    valid_item["links"]["general"] = ["   "]
    assert any("Source Link" in b for b in submit_blockers(valid_item))


def test_blocker_missing_links_key_entirely(valid_item):
    del valid_item["links"]
    assert any("Source Link" in b for b in submit_blockers(valid_item))


# ── item_warnings: non-blocking advisories ───────────────────────────────────
def _details(**over):
    base = {
        "title": "T", "short_title": "S", "description": "D", "mfg_model": "M",
        "battery_info": "no battery used", "battery_quantity": "",
    }
    base.update(over)
    return base


def test_warning_title_required():
    warnings = item_warnings(_details(title=""), ["f"], [], [])
    assert any("title is required" in w.lower() for w in warnings)


def test_warning_battery_quantity_not_numeric():
    details = _details(battery_info="required, included", battery_quantity="abc")
    warnings = item_warnings(details, [], [], [])
    assert any("quantity must be numeric" in w.lower() for w in warnings)


def test_warning_field_exceeds_limit():
    details = _details(title="x" * 200)
    warnings = item_warnings(details, [], [], [])
    assert any("exceeds" in w.lower() for w in warnings)


def test_warning_include_has_both_text_and_sku():
    warnings = item_warnings(
        _details(), [], [], [], includes=[{"text": "cable", "sku": "SKU-9"}]
    )
    assert any("cannot have both" in w.lower() for w in warnings)


def test_warning_too_many_highlights():
    warnings = item_warnings(_details(), [], [], ["h"] * 9)
    assert any("should not exceed 8" in w.lower() for w in warnings)


def test_warning_special_char_flagged(rules_df):
    warnings = item_warnings(_details(title="Hello©"), [], [], [], rules_df=rules_df)
    assert any("Special char" in w for w in warnings)


def test_warning_double_space_flagged():
    warnings = item_warnings(_details(title="two  spaces"), [], [], [])
    assert any("Double space" in w for w in warnings)
