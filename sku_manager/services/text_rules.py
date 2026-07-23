from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd


_DELETE_ACTIONS = {"delete", "remove", "strip"}
_REPLACE_ACTIONS = {"replace", "replace value", "replace with"}
_FLAG_ACTIONS = {"flag", "flag only", "review", "manual review", "warn", "warning", "alert"}


_COMMON_VARIANTS = {
    "(c)": ["\u00a9", "&copy;", "&#169;", "&#xA9;", "&#xa9;", "\u00c2\u00a9"],
    "\u00a9": ["(c)", "(C)", "&copy;", "&#169;", "&#xA9;", "&#xa9;", "\u00c2\u00a9"],
    "(r)": ["\u00ae", "&reg;", "&#174;", "&#xAE;", "&#xae;", "\u00c2\u00ae"],
    "\u00ae": ["(r)", "(R)", "&reg;", "&#174;", "&#xAE;", "&#xae;", "\u00c2\u00ae"],
    "tm": ["\u2122", "&trade;", "&#8482;", "&#x2122;", "(tm)"],
    "\u2122": ["tm", "TM", "&trade;", "&#8482;", "&#x2122;", "(tm)", "(TM)"],
    "\u00b0": ["&deg;", "&#176;", "&#xB0;", "&#xb0;", "\u00c2\u00b0"],
    "\u00b1": ["&plusmn;", "&#177;", "&#xB1;", "&#xb1;", "\u00c2\u00b1", "\u0105"],
    "\u0105": ["\u00b1", "&plusmn;", "&#177;", "&#xB1;", "&#xb1;", "\u00c2\u00b1"],
    "\u00d7": ["&times;", "&#215;", "&#xD7;", "&#xd7;", "\u00c3\u0097"],
}


def action_kind(action: str) -> str:
    normalized = re.sub(r"\s+", " ", str(action or "").strip().lower())
    if not normalized:
        return ""
    if normalized in _DELETE_ACTIONS or normalized.startswith("delete"):
        return "delete"
    if normalized in _REPLACE_ACTIONS or normalized.startswith("replace"):
        return "replace"
    if normalized in _FLAG_ACTIONS or any(token in normalized for token in ("flag", "review", "warn", "alert")):
        return "flag"
    return normalized


def _iter_rule_rows(rules_df: pd.DataFrame | None) -> Iterable[dict[str, str]]:
    if rules_df is None or rules_df.empty:
        return []
    rows = []
    for _, row in rules_df.fillna("").iterrows():
        symbol = str(row.get("Symbol", ""))
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "action": str(row.get("Action required", "")).strip(),
                "action_kind": action_kind(row.get("Action required", "")),
                "replacement": str(row.get("Replace Value", "")),
                "meaning": str(row.get("Symbol Meaning", "")),
            }
        )
    # Longer/more specific symbols (e.g. "μV") must be tried before shorter
    # ones they contain (e.g. "µ"), since Unicode case-folding under
    # IGNORECASE makes the micro sign and Greek mu match each other and a
    # generic single-char rule would otherwise consume the match first.
    rows.sort(key=lambda r: len(r["symbol"]), reverse=True)
    return rows


def _symbol_variants(symbol: str) -> list[str]:
    base = str(symbol or "")
    normalized = base.strip()
    keys = {base, normalized, normalized.lower(), normalized.upper()}
    variants: list[str] = []
    for key in keys:
        if not key:
            continue
        variants.append(key)
        variants.extend(_COMMON_VARIANTS.get(key, []))
        variants.extend(_COMMON_VARIANTS.get(key.lower(), []))
    seen = set()
    unique = []
    for variant in sorted(variants, key=len, reverse=True):
        if variant and variant not in seen:
            seen.add(variant)
            unique.append(variant)
    return unique


def _variant_pattern(variant: str, original_symbol: str) -> str:
    escaped = re.escape(variant)
    # Word-boundary guard only applies to plain-ASCII fallback spellings
    # ("tm", "(c)" -> "r", etc.) so we don't match "tm" inside "item".
    # Real Unicode symbols (µ, μ, Ω, ...) are unambiguous even glued to a
    # digit or letter (100µA, 5µF, 10Ω), so they must not be guarded here.
    if variant.isascii() and variant.isalnum() and any(char.isalpha() for char in variant):
        return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return escaped


def _symbol_pattern(symbol: str) -> re.Pattern[str]:
    variants = _symbol_variants(symbol)
    pattern = "|".join(_variant_pattern(variant, symbol) for variant in variants)
    flags = re.IGNORECASE if any(char.isalpha() for char in symbol) else 0
    return re.compile(pattern or re.escape(symbol), flags)


def _match_case(replacement: str, matched: str) -> str:
    if not replacement or not any(char.isalpha() for char in replacement):
        return replacement
    if str(matched).startswith("&") and str(matched).endswith(";"):
        return replacement
    if not any(("A" <= char <= "Z") or ("a" <= char <= "z") for char in str(matched)):
        return replacement
    if matched.isupper():
        return replacement.upper()
    if matched.islower():
        return replacement.lower()
    if matched[:1].isupper() and matched[1:].islower():
        return replacement
    return replacement


def format_text(text: str, rules_df: pd.DataFrame) -> str:
    value = "" if text is None else str(text)
    for rule in _iter_rule_rows(rules_df):
        kind = rule["action_kind"]
        if kind not in {"delete", "replace"}:
            continue
        pattern = _symbol_pattern(rule["symbol"])
        if kind == "delete":
            value = pattern.sub("", value)
        elif kind == "replace":
            replacement = rule["replacement"]
            value = pattern.sub(lambda match: _match_case(replacement, match.group(0)), value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def find_violations(text: str, rules_df: pd.DataFrame, actions: set[str] | None = None) -> list[dict]:
    """Return rule violations found in text.

    Each item includes: symbol, matched, action, action_kind, replacement, meaning.
    Matching is case-insensitive for alphabetic symbols so Reference Data rows like
    Grey -> Gray also catch GREY -> GRAY.
    """
    if not text:
        return []
    value = str(text)
    violations = []
    wanted = {action_kind(action) for action in actions} if actions else None
    for rule in _iter_rule_rows(rules_df):
        kind = rule["action_kind"] or "flag"
        if wanted is not None and kind not in wanted:
            continue
        match = _symbol_pattern(rule["symbol"]).search(value)
        if not match:
            continue
        violations.append(
            {
                "symbol": rule["symbol"],
                "matched": match.group(0),
                "action": rule["action"],
                "action_kind": kind,
                "replacement": _match_case(rule["replacement"], match.group(0)),
                "meaning": rule["meaning"],
            }
        )
    return violations


def parse_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text).replace("\r", "\n").split("\n") if line.strip()]


def split_cell_lines(value) -> list[str]:
    """Split a grid cell into its non-empty lines.

    The data editor's clipboard parser treats " as a CSV quote character, so
    pasting text with unmatched inch marks (1/4", 9.5") merges lines into one
    cell with embedded newlines. Splitting the cell back out restores them.
    """
    if value is None:
        return []
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def flatten_cell_text(value) -> str:
    """Collapse newlines a paste embedded in a grid cell back into spaces."""
    return " ".join(split_cell_lines(value))


def parse_tabbed_specs(text: str) -> list[dict[str, str]]:
    specs = []
    for line in parse_lines(text):
        if "\t" in line:
            key, value = line.split("\t", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        value = value.strip()
        if key and value:
            specs.append({"Spec": key, "Value": value})
    return specs