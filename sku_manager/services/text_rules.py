from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd


_DELETE_ACTIONS = {"delete", "remove", "strip"}
_REPLACE_ACTIONS = {"replace", "replace value", "replace with"}
_FLAG_ACTIONS = {"flag", "flag only", "review", "manual review", "warn", "warning", "alert"}


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
    return rows


def _symbol_pattern(symbol: str) -> re.Pattern[str]:
    flags = re.IGNORECASE if any(char.isalpha() for char in symbol) else 0
    return re.compile(re.escape(symbol), flags)


def _match_case(replacement: str, matched: str) -> str:
    if not replacement or not any(char.isalpha() for char in replacement):
        return replacement
    if matched.isupper():
        return replacement.upper()
    if matched.islower():
        return replacement.lower()
    if matched[:1].isupper() and matched[1:].islower():
        return replacement[:1].upper() + replacement[1:].lower()
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
    value = re.sub(r"\s{2,}", " ", value)
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