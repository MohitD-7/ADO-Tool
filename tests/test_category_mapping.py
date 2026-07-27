"""Tests for category-taxonomy helpers (sku_manager/services/category_mapping.py)."""
from __future__ import annotations

import pandas as pd

from sku_manager.services.category_mapping import (
    MAPPING_COLUMNS,
    canonical_path,
    category_labels,
    delete_taxonomy,
    display_path,
    leaf_name,
    merge_template_into_specs,
    normalize_mapping_frame,
    parse_template_lines,
    replace_taxonomy_rows,
    taxonomy_parts,
)


# ── path parsing ─────────────────────────────────────────────────────────────
def test_taxonomy_parts_double_arrow():
    assert taxonomy_parts("A>>B>>C") == ["A", "B", "C"]


def test_taxonomy_parts_single_arrow():
    assert taxonomy_parts("A > B") == ["A", "B"]


def test_canonical_path_normalizes_separator():
    assert canonical_path("A > B > C") == "A>>B>>C"


def test_leaf_name():
    assert leaf_name("A>>B>>C") == "C"


def test_display_path():
    assert display_path("A>>B>>C") == "A > B > C"


# ── dropdown labels ──────────────────────────────────────────────────────────
def test_category_labels_disambiguate_colliding_leaves():
    paths = ["Photography>>Cameras>>Lenses", "Video>>Rigs>>Lenses"]
    labels = category_labels(paths)
    # Same leaf "Lenses" in two paths -> disambiguated by parent.
    assert labels["Photography>>Cameras>>Lenses"] == "Lenses (Cameras)"
    assert labels["Video>>Rigs>>Lenses"] == "Lenses (Rigs)"


def test_category_labels_unique_leaf_plain():
    labels = category_labels(["A>>B>>Widget"])
    assert labels["A>>B>>Widget"] == "Widget"


# ── template merging into specs ──────────────────────────────────────────────
def test_merge_template_adds_rows():
    import streamlit as st
    st.session_state["category_mapping_df"] = pd.DataFrame(
        [
            {"Taxonomy Path": "A>>B", "Value1 (Category)": "B", "Value3 (Group)": "General", "Value4 (Spec)": "Color"},
            {"Taxonomy Path": "A>>B", "Value1 (Category)": "B", "Value3 (Group)": "General", "Value4 (Spec)": "Weight"},
        ]
    )
    specs: list[dict] = []
    added = merge_template_into_specs(specs, "A>>B")
    assert added == 2
    assert {s["Spec"] for s in specs} == {"Color", "Weight"}


def test_merge_template_skips_existing():
    import streamlit as st
    st.session_state["category_mapping_df"] = pd.DataFrame(
        [{"Taxonomy Path": "A>>B", "Value1 (Category)": "B", "Value3 (Group)": "General", "Value4 (Spec)": "Color"}]
    )
    specs = [{"category": "B", "group": "General", "Spec": "Color", "Value": "Red"}]
    added = merge_template_into_specs(specs, "A>>B")
    assert added == 0
    assert len(specs) == 1  # existing row untouched


# ── pasted-line parsing ──────────────────────────────────────────────────────
def test_parse_template_lines_three_columns():
    df = parse_template_lines("Cat\tGeneral\tColor")
    assert df.iloc[0]["Value1 (Category)"] == "Cat"
    assert df.iloc[0]["Value3 (Group)"] == "General"
    assert df.iloc[0]["Value4 (Spec)"] == "Color"


def test_parse_template_lines_two_columns():
    df = parse_template_lines("General\tColor")
    assert df.iloc[0]["Value3 (Group)"] == "General"
    assert df.iloc[0]["Value4 (Spec)"] == "Color"


# ── frame normalisation and taxonomy editing ─────────────────────────────────
def test_normalize_mapping_frame_renames_aliases():
    raw = pd.DataFrame([{"path": "A>>B", "category": "B", "group": "G", "spec": "Color"}])
    out = normalize_mapping_frame(raw)
    assert list(out.columns) == MAPPING_COLUMNS
    assert out.iloc[0]["Taxonomy Path"] == "A>>B"


def test_normalize_mapping_frame_drops_empty_rows():
    raw = pd.DataFrame([{"Taxonomy Path": "A>>B", "Value3 (Group)": "", "Value4 (Spec)": ""}])
    out = normalize_mapping_frame(raw)
    assert out.empty


def test_delete_taxonomy_removes_path():
    df = normalize_mapping_frame(
        pd.DataFrame(
            [
                {"Taxonomy Path": "A>>B", "Value1 (Category)": "B", "Value3 (Group)": "G", "Value4 (Spec)": "Color"},
                {"Taxonomy Path": "X>>Y", "Value1 (Category)": "Y", "Value3 (Group)": "G", "Value4 (Spec)": "Size"},
            ]
        )
    )
    out = delete_taxonomy(df, "A>>B")
    assert "A>>B" not in out["Taxonomy Path"].tolist()
    assert "X>>Y" in out["Taxonomy Path"].tolist()


def test_replace_taxonomy_rows_keeps_others():
    df = normalize_mapping_frame(
        pd.DataFrame(
            [
                {"Taxonomy Path": "A>>B", "Value1 (Category)": "B", "Value3 (Group)": "G", "Value4 (Spec)": "Color"},
                {"Taxonomy Path": "X>>Y", "Value1 (Category)": "Y", "Value3 (Group)": "G", "Value4 (Spec)": "Size"},
            ]
        )
    )
    new_rows = pd.DataFrame([{"Value1 (Category)": "B", "Value3 (Group)": "G", "Value4 (Spec)": "Material"}])
    out = replace_taxonomy_rows(df, "A>>B", new_rows)
    a_specs = out[out["Taxonomy Path"] == "A>>B"]["Value4 (Spec)"].tolist()
    assert a_specs == ["Material"]                       # replaced
    assert "X>>Y" in out["Taxonomy Path"].tolist()       # untouched
