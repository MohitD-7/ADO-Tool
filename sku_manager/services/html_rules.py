"""Rule logic used by the custom HTML description editor."""
from __future__ import annotations


def apply_rule(text: str, rule: dict) -> str:
    """
    Apply a single editor rule to text.
    If rule has apply_per_line=True, each line is processed independently.
    """
    if rule.get("apply_per_line", False):
        lines = text.splitlines() or [""]
        return "\n".join(_apply_modifications(line, rule) for line in lines)
    return _apply_modifications(text, rule)


def _apply_modifications(text: str, rule: dict) -> str:
    result = text
    start_text = rule.get("start_text", "")
    end_text = rule.get("end_text", "")
    tag = rule.get("tag", "").strip() if rule.get("add_tags", False) else ""

    opening = f"<{tag}>" if tag else ""
    closing = f"</{tag}>" if tag else ""

    if tag and rule.get("add_tags", False):
        if rule.get("add_start", False) and start_text:
            if rule.get("start_after_tag", False):
                result = opening + start_text + result
            else:
                result = start_text + opening + result
        else:
            result = opening + result

        if rule.get("add_end", False) and end_text:
            if rule.get("end_before_tag", False):
                result = result + end_text + closing
            else:
                result = result + closing + end_text
        else:
            result = result + closing
    else:
        if rule.get("add_start", False) and start_text:
            result = start_text + result
        if rule.get("add_end", False) and end_text:
            result = result + end_text

    return result


def validate_rule(rule: dict, existing_rules: list[dict], editing_name: str | None = None) -> list[str]:
    errors: list[str] = []
    if not rule.get("name", "").strip():
        errors.append("Rule name is required.")
    has_action = any(
        [
            rule.get("add_start") and rule.get("start_text", "").strip(),
            rule.get("add_end") and rule.get("end_text", "").strip(),
            rule.get("add_tags") and rule.get("tag", "").strip(),
        ]
    )
    if not has_action:
        errors.append("At least one modification (start text, end text, or tag) must be set.")
    shortcut = rule.get("shortcut", "").strip()
    if shortcut:
        for existing_rule in existing_rules:
            if existing_rule["name"] == editing_name:
                continue
            if existing_rule.get("shortcut", "").strip() == shortcut:
                errors.append(f"Shortcut already used by rule '{existing_rule['name']}'.")
                break
    return errors
