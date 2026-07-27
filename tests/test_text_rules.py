"""Tests for text formatting/cleaning rules (sku_manager/services/text_rules.py).

This is the engine behind the "Format Visible Text" button.
"""
from __future__ import annotations

import pandas as pd

from sku_manager.services.text_rules import (
    action_kind,
    find_violations,
    flatten_cell_text,
    format_text,
    parse_lines,
    parse_tabbed_specs,
    split_cell_lines,
)


# ── action_kind: normalising the free-text "Action required" column ──────────
def test_action_kind_delete():
    assert action_kind("Delete") == "delete"


def test_action_kind_replace_variants():
    assert action_kind("Replace") == "replace"
    assert action_kind("replace with") == "replace"


def test_action_kind_flag():
    assert action_kind("Flag only") == "flag"


def test_action_kind_blank():
    assert action_kind("") == ""


# ── format_text: the actual cleaning ─────────────────────────────────────────
def test_format_text_curly_quotes(rules_df):
    assert format_text("“hi”", rules_df) == '"hi"'


def test_format_text_em_dash(rules_df):
    assert format_text("a—b", rules_df) == "a-b"


def test_format_text_grey_lowercase(rules_df):
    assert format_text("grey", rules_df) == "gray"


def test_format_text_grey_uppercase_keeps_case(rules_df):
    assert format_text("GREY", rules_df) == "GRAY"


def test_format_text_word_boundary_leaves_greyhound(rules_df):
    # "grey" inside "greyhound" must not be replaced (ASCII word-boundary guard).
    assert format_text("greyhound", rules_df) == "greyhound"


def test_format_text_delete_and_double_space(rules_df):
    # © is deleted; the space it leaves behind collapses to a single space.
    assert format_text("A © B", rules_df) == "A B"


def test_format_text_collapses_double_space_without_rules(empty_rules):
    assert format_text("a  b", empty_rules) == "a b"


def test_format_text_strips_ends(empty_rules):
    assert format_text("  trimmed  ", empty_rules) == "trimmed"


def test_format_text_none_is_empty(rules_df):
    assert format_text(None, rules_df) == ""


# ── find_violations: what the validation panel flags ─────────────────────────
def test_find_violations_detects_curly_quote(rules_df):
    violations = find_violations("“hi”", rules_df)
    symbols = {v["symbol"] for v in violations}
    assert "“" in symbols


def test_find_violations_clean_text_none(rules_df):
    assert find_violations("perfectly clean text", rules_df) == []


def test_find_violations_action_filter(rules_df):
    only_deletes = find_violations("A © “ text", rules_df, actions={"delete"})
    kinds = {v["action_kind"] for v in only_deletes}
    assert kinds == {"delete"}


# ── line / cell helpers ──────────────────────────────────────────────────────
def test_parse_lines_splits_and_strips():
    assert parse_lines("a\nb\n\n c ") == ["a", "b", "c"]


def test_parse_lines_handles_carriage_returns():
    assert parse_lines("a\r\nb") == ["a", "b"]


def test_split_cell_lines_none():
    assert split_cell_lines(None) == []


def test_split_cell_lines_multiline():
    assert split_cell_lines("a\nb") == ["a", "b"]


def test_split_cell_lines_nan():
    assert split_cell_lines(pd.NA) == []


def test_flatten_cell_text_joins_with_space():
    assert flatten_cell_text("a\nb\nc") == "a b c"


def test_parse_tabbed_specs_tab():
    assert parse_tabbed_specs("Color\tBlack") == [{"Spec": "Color", "Value": "Black"}]


def test_parse_tabbed_specs_colon():
    assert parse_tabbed_specs("Color: Black") == [{"Spec": "Color", "Value": "Black"}]


def test_parse_tabbed_specs_skips_unseparated():
    assert parse_tabbed_specs("no separator here") == []
