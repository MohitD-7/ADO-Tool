from __future__ import annotations

import re

from sku_manager.services.text_rules import find_violations


LIMITS = {
    "title": 110,
    "short_title": 75,
    "include_text": 100,
    "description": 10000,
    "mfg_model": 25,
    "feature": 350,
    "feature_bulk": 450,
    "highlight": 80,
    "highlight_bulk": 100,
    "spec_group": 40,
    "spec_key": 40,
    "spec_value": 500,
}


def char_count_status(value: str, limit: int) -> tuple[int, bool]:
    count = len(value or "")
    return count, count <= limit


def _limit_flag(text: str) -> str:
    """Match the red/bold styling item_warnings() already uses for
    special-char and double-space violations, so limit violations are
    visually highlighted wherever warnings/blockers are rendered with
    unsafe_allow_html=True (not just present in a plain bullet list)."""
    return f"<span style='color:#c62828;font-weight:700;'>{text}</span>"


def _limit_violations(details: dict, features: list, specs: list, highlights: list, includes: list) -> list[str]:
    """Character-limit checks shared by item_warnings() (shown per-page) and
    submit_blockers() (shown in the submit confirm dialog, per the fields
    the business defined limits for)."""
    violations: list[str] = []
    for key, label in [
        ("title", "Title"),
        ("short_title", "Short Title"),
        ("mfg_model", "MFG Model"),
        ("description", "Description"),
    ]:
        value = str(details.get(key, ""))
        limit = LIMITS[key]
        if len(value) > limit:
            violations.append(_limit_flag(f"{label} exceeds {limit} characters (currently {len(value)})."))

    for idx, feature in enumerate(features, start=1):
        text = str(feature or "")
        if len(text) > LIMITS["feature"]:
            violations.append(_limit_flag(f"Feature #{idx * 10} exceeds {LIMITS['feature']} characters (currently {len(text)})."))

    for idx, highlight in enumerate(highlights, start=1):
        text = str(highlight or "")
        if len(text) > LIMITS["highlight"]:
            violations.append(_limit_flag(f"Highlight #{idx * 10} exceeds {LIMITS['highlight']} characters (currently {len(text)})."))

    for idx, entry in enumerate(includes, start=1):
        text = str(entry.get("text", "") or "")
        if len(text) > LIMITS["include_text"]:
            violations.append(_limit_flag(f"Include #{idx * 10} text exceeds {LIMITS['include_text']} characters (currently {len(text)})."))

    for idx, spec in enumerate(specs, start=1):
        group = str(spec.get("group", "") or "")
        name = str(spec.get("Spec", "") or "")
        value = str(spec.get("Value", "") or "")
        if len(group) > LIMITS["spec_group"]:
            violations.append(_limit_flag(f"Spec #{idx * 10} Group (V3) exceeds {LIMITS['spec_group']} characters (currently {len(group)})."))
        if len(name) > LIMITS["spec_key"]:
            violations.append(_limit_flag(f"Spec #{idx * 10} Name (V4) exceeds {LIMITS['spec_key']} characters (currently {len(name)})."))
        if len(value) > LIMITS["spec_value"]:
            violations.append(_limit_flag(f"Spec #{idx * 10} Value (V5) exceeds {LIMITS['spec_value']} characters (currently {len(value)})."))

    return violations


def submit_blockers(item: dict) -> list[str]:
    """
    Return a list of blocking reasons the current item cannot be submitted.
    Empty list = ready to submit. Used by the Review page's Submit button.
    """
    details = item.get("details", {}) or {}
    features = item.get("features", []) or []
    specs = item.get("specs", []) or []
    includes = item.get("includes", []) or []
    highlights = item.get("highlights", []) or []
    problems: list[str] = []

    def _need(field_key: str, label: str) -> None:
        if not str(details.get(field_key, "")).strip():
            problems.append(f"{label} is empty.")

    _need("title",       "Title")
    _need("short_title", "Short Title")
    _need("description", "Description")
    _need("mfg_model",   "MFG Model")

    non_empty_includes = [
        i for i in includes
        if str(i.get("text", "") or "").strip() or str(i.get("sku", "") or "").strip()
    ]
    if not non_empty_includes:
        problems.append("Includes has no rows.")

    source_links = [
        link for link in (item.get("links", {}) or {}).get("general", [])
        if str(link or "").strip()
    ]
    if not source_links:
        problems.append("Need at least 1 Source Link.")

    non_empty_features = [f for f in features if str(f).strip()]
    if len(non_empty_features) < 2:
        problems.append(f"Need at least 2 Features (have {len(non_empty_features)}).")

    non_empty_specs = [
        s for s in specs
        if str(s.get("Spec", "") or "").strip() and str(s.get("Value", "") or "").strip()
    ]
    if len(non_empty_specs) < 2:
        problems.append(f"Need at least 2 Specs with both name and value (have {len(non_empty_specs)}).")

    if not str(details.get("battery_info", "")).strip():
        problems.append("Battery Info is not set.")

    problems.extend(_limit_violations(details, features, specs, highlights, includes))

    return problems


def item_warnings(
    details: dict,
    features: list,
    specs: list,
    highlights: list,
    rules_df=None,
    includes: list | None = None,
) -> list[str]:
    warnings = []
    includes = includes or []
    if not str(details.get("title", "")).strip():
        warnings.append("Product title is required.")
    if details.get("battery_info") != "no battery used":
        quantity = str(details.get("battery_quantity", "")).strip()
        if not quantity.isdigit():
            warnings.append("Battery quantity must be numeric when battery info is selected.")
    warnings.extend(_limit_violations(details, features, specs, highlights, includes))
    for idx, entry in enumerate(includes, start=1):
        text = str(entry.get("text", "") or "")
        sku = str(entry.get("sku", "") or "").strip()
        if text and sku:
            warnings.append(f"Include #{idx * 10}: cannot have both text and SKU. Clear one.")
    if len(highlights) > 8:
        warnings.append("Highlights should not exceed 8 rows.")

    # Special-character / double-space violations across all text fields
    fields = {
        "Title":       details.get("title", ""),
        "Short Title": details.get("short_title", ""),
        "Description": details.get("description", ""),
        "Mfg Model":   details.get("mfg_model", ""),
    }
    include_text_blob = " ".join(str(e.get("text", "") or "") for e in includes)
    if include_text_blob.strip():
        fields["Includes"] = include_text_blob
    for feat in features:
        fields["Features"] = fields.get("Features", "") + " " + str(feat)
    for spec in specs:
        fields["Specs"] = (fields.get("Specs", "") + " "
            + str(spec.get("Spec", "")) + " " + str(spec.get("Value", "")))

    if rules_df is not None and not rules_df.empty:
        seen = set()
        for field_label, text in fields.items():
            for v in find_violations(text, rules_df):
                k = f"{v['symbol']}:{field_label}"
                if k in seen:
                    continue
                seen.add(k)
                action_desc = (
                    "delete it"
                    if v["action"].lower() == "delete"
                    else f"replace with \"{v['replacement']}\""
                )
                warnings.append(
                    f"<span style='color:#c62828;font-weight:700;'>"
                    f"Special char in {field_label}:</span> "
                    f"<code>{v['symbol']}</code> ({v['meaning']}) - {action_desc}. "
                    f"Click <em>Format</em> to fix."
                )

    for field_label, text in fields.items():
        if re.search(r"[ \t]{2,}", str(text)):
            warnings.append(
                f"<span style='color:#c62828;font-weight:700;'>"
                f"Double space in {field_label}:</span> "
                f"collapse to a single space. Click <em>Format</em> to fix."
            )

    return warnings
