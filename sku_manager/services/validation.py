from __future__ import annotations

import re

from sku_manager.services.text_rules import find_violations


LIMITS = {
    "title": 110,
    "short_title": 75,
    "include_text": 350,
    "description": 10000,
    "mfg_model": 25,
    "feature": 350,
    "feature_bulk": 450,
    "highlight": 90,
    "highlight_bulk": 100,
    "spec_key": 40,
    "spec_value": 450,
}


def char_count_status(value: str, limit: int) -> tuple[int, bool]:
    count = len(value or "")
    return count, count <= limit


def submit_blockers(item: dict) -> list[str]:
    """
    Return a list of blocking reasons the current item cannot be submitted.
    Empty list = ready to submit. Used by the Review page's Submit button.
    """
    details = item.get("details", {}) or {}
    features = item.get("features", []) or []
    specs = item.get("specs", []) or []
    includes = item.get("includes", []) or []
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
    for key, limit in [
        ("title", LIMITS["title"]),
        ("short_title", LIMITS["short_title"]),
        ("description", LIMITS["description"]),
        ("mfg_model", LIMITS["mfg_model"]),
    ]:
        value = str(details.get(key, ""))
        if len(value) > limit:
            warnings.append(f"{key.replace('_', ' ').title()} exceeds {limit} characters.")
    for idx, entry in enumerate(includes, start=1):
        text = str(entry.get("text", "") or "")
        sku = str(entry.get("sku", "") or "").strip()
        if text and sku:
            warnings.append(f"Include #{idx * 10}: cannot have both text and SKU. Clear one.")
        if len(text) > LIMITS["include_text"]:
            warnings.append(f"Include #{idx * 10} text exceeds {LIMITS['include_text']} characters.")
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
