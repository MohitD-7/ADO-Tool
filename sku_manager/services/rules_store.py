"""
Persistence layer for editor rules.
Rules are stored in data/editor_rules.json next to the app root.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "editor_rules.json")
_RULES_PATH = os.path.normpath(_RULES_PATH)

RULES_PATH = Path(_RULES_PATH)


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(_RULES_PATH), exist_ok=True)


def load_rules() -> list[dict]:
    if not os.path.exists(_RULES_PATH):
        return []
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_rules(rules: list[dict]) -> None:
    _ensure_dir()
    with open(_RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


def add_rule(rule: dict) -> list[dict]:
    rules = load_rules()
    rules.append(rule)
    save_rules(rules)
    return rules


def update_rule(name: str, updated: dict) -> list[dict]:
    rules = load_rules()
    rules = [updated if r["name"] == name else r for r in rules]
    save_rules(rules)
    return rules


def delete_rule(name: str) -> list[dict]:
    rules = [r for r in load_rules() if r["name"] != name]
    save_rules(rules)
    return rules
