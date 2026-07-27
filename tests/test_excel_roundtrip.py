"""Integration tests for the Excel export/import round-trip and HTML rendering
(sku_manager/services/export.py).

These cover the highest-stakes behaviour in the app: work created, downloaded,
and re-uploaded must come back whole. Two of these guard bugs fixed on
2026-07-25 (children and Var Opts vanishing on reimport).
"""
from __future__ import annotations

from sku_manager.services.export import (
    build_battery_df,
    build_input_sheet_df,
    build_output_df,
    excel_bytes,
    parse_output_excel,
    render_html,
    sanitize_description_html,
    text_bytes,
)
from sku_manager.services.variants import build_variant_df


# ── which SKUs appear where ──────────────────────────────────────────────────
def test_output_sheet_excludes_children(parent_child_batch):
    queue, items = parent_child_batch
    output = build_output_df(queue, items)
    # Children carry no content of their own -> only the parent produces rows.
    assert set(output["Item Number"].unique()) == {"P1"}


def test_input_sheet_includes_children(parent_child_batch):
    queue, items = parent_child_batch
    input_df = build_input_sheet_df(queue, items)
    assert input_df["Item No"].tolist() == ["P1", "C1", "C2"]


# ── the round-trips (today's fixes) ──────────────────────────────────────────
def test_children_survive_round_trip(parent_child_batch):
    queue, items = parent_child_batch
    excel = excel_bytes(build_output_df(queue, items), build_input_sheet_df(queue, items))
    _, items2, _ = parse_output_excel(_readable(excel))
    assert list(items2.keys()) == ["P1", "C1", "C2"]


def test_variant_options_survive_round_trip(parent_child_batch, variants_data):
    queue, items = parent_child_batch
    excel = excel_bytes(
        build_output_df(queue, items),
        build_input_sheet_df(queue, items),
        variant_df=build_variant_df(queue, variants_data),
    )
    _, _, variants2 = parse_output_excel(_readable(excel))
    assert variants2 == variants_data


def test_item_content_survives_round_trip(parent_child_batch):
    queue, items = parent_child_batch
    items["P1"]["details"]["description"] = "A description"
    items["P1"]["features"] = ["Feature one", "Feature two"]
    items["P1"]["specs"] = [{"category": "", "group": "", "Spec": "Color", "Value": "Black"}]
    excel = excel_bytes(build_output_df(queue, items), build_input_sheet_df(queue, items))
    _, items2, _ = parse_output_excel(_readable(excel))
    p1 = items2["P1"]
    assert p1["details"]["description"] == "A description"
    assert p1["features"] == ["Feature one", "Feature two"]
    assert any(s["Spec"] == "Color" and s["Value"] == "Black" for s in p1["specs"])


def test_round_trip_preserves_mfg_item(parent_child_batch):
    queue, items = parent_child_batch
    excel = excel_bytes(build_output_df(queue, items), build_input_sheet_df(queue, items))
    _, items2, _ = parse_output_excel(_readable(excel))
    assert items2["C1"]["details"]["mfg_item"] == "MC1"


# ── other export builders ────────────────────────────────────────────────────
def test_battery_df_only_includes_battery_skus(parent_child_batch):
    queue, items = parent_child_batch
    items["P1"]["details"]["battery_info"] = "required, included"
    items["P1"]["details"]["battery_material"] = "Lithium"
    battery = build_battery_df(queue, items)
    assert battery["SKU"].tolist() == ["P1"]


def test_text_bytes_stops_at_value5(parent_child_batch):
    queue, items = parent_child_batch
    output = build_output_df(queue, items)
    text = text_bytes(output).decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "Comments" not in header
    assert "Source" not in header


# ── HTML safety / rendering ──────────────────────────────────────────────────
def test_sanitize_strips_script():
    cleaned = sanitize_description_html("<script>alert(1)</script>Hello")
    assert "alert" not in cleaned
    assert "Hello" in cleaned


def test_sanitize_keeps_allowed_tags():
    assert sanitize_description_html("<b>Bold</b>") == "<b>Bold</b>"


def test_sanitize_drops_attributes():
    assert sanitize_description_html("<p onclick='x'>Hi</p>") == "<p>Hi</p>"


def test_render_html_substitutes_fields():
    item = {
        "details": {"title": "My Title", "description": "Desc", "item_no": "X1", "mfg_item": "", "mfg_model": ""},
        "includes": [], "features": [], "specs": [], "highlights": [],
    }
    html = render_html(item, "T:--Title-- D:--Description--")
    assert "My Title" in html
    assert "Desc" in html


def _readable(excel_bytes_value):
    """parse_output_excel accepts a file-like; wrap the bytes."""
    from io import BytesIO
    return BytesIO(excel_bytes_value)
