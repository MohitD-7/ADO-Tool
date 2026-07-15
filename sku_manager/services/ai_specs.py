from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import streamlit as st


DEFAULT_MODEL = "o3"
MAX_SOURCE_CHARS = 24000


class AISpecsError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpecPromptRow:
    i: int
    group: str
    spec: str


@dataclass(frozen=True)
class SpecSuggestion:
    i: int
    value: str


DEVELOPER_PROMPT = """
You are a strict SKU specification extraction engine.

Your task:
Fill only the V5 spec values for the provided rows using only the provided source content.

Rules:
1. Return JSON only. No explanation, no markdown.
2. Preserve row indexes exactly.
3. Do not create new specs.
4. Do not change V3 group or V4 spec names.
5. If the source does not clearly provide a value, return an empty string.
6. Do not guess, infer, or use marketing language.
7. Keep values short and cell-ready.
8. Capitalize the first letter of each spec value when the value is text.
9. If a spec has multiple values, separate them with <br> or <br><br>.
10. Use ' for feet and " for inches.
11. For numerical specs with metric values, convert to Imperial and keep metric in parentheses.
12. Do not add spaces between number and unit, except for lbs and oz.

Numerical formatting examples:
- Source says: 2.5 cm
  Output: 1" (2.5cm)
- Source says: 50 mm
  Output: 2" (50mm)
- Source says: 1.2 kg
  Output: 2.6 lbs (1.2kg)
- Source says: 300 g
  Output: 10.6 oz (300g)
- Source says: 20 cm x 30 cm
  Output: 7.9 x 11.8" (20 x 30cm)

Output format:
{"values":[{"i":0,"value":"Black"},{"i":1,"value":"2.6 lbs (1.2kg)"},{"i":2,"value":""}]}
""".strip()


def configured_model() -> str:
    env_model = os.getenv("OPENAI_MODEL", "").strip()
    if env_model:
        return env_model
    try:
        secret_model = str(st.secrets.get("openai_model", "")).strip()
    except Exception:
        secret_model = ""
    return secret_model or DEFAULT_MODEL


def api_key() -> str:
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        return str(st.secrets.get("openai_api_key", "")).strip()
    except Exception:
        return ""


def is_configured() -> bool:
    return bool(api_key())


def _trim_source_text(text: str) -> str:
    return str(text or "").strip()[:MAX_SOURCE_CHARS]


def build_prompt_rows(specs: list[dict[str, Any]]) -> list[SpecPromptRow]:
    rows: list[SpecPromptRow] = []
    for index, entry in enumerate(specs):
        value = str(entry.get("Value", "") or "").strip()
        group = str(entry.get("group", "") or "").strip()
        spec = str(entry.get("Spec", "") or "").strip()
        if value or not spec:
            continue
        rows.append(SpecPromptRow(i=index, group=group, spec=spec))
    return rows


def fill_v5_values(
    *,
    details: dict[str, Any],
    rows: list[SpecPromptRow],
    source_text: str,
) -> list[SpecSuggestion]:
    if not rows:
        return []
    source_text = _trim_source_text(source_text)
    if not source_text:
        raise AISpecsError("Provide source text before using AI fill.")

    key = api_key()
    if not key:
        raise AISpecsError("OpenAI API key is not configured.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AISpecsError("The openai package is not installed. Run pip install -r requirements.txt.") from exc

    payload = {
        "product": {
            "title": str(details.get("title", "") or details.get("input_title", "") or ""),
            "mfg_item": str(details.get("mfg_item", "") or details.get("input_mfg_item", "") or ""),
            "mfg_model": str(details.get("mfg_model", "") or ""),
        },
        "rows": [{"i": row.i, "group": row.group, "spec": row.spec} for row in rows],
        "source_text": source_text,
    }

    client = OpenAI(api_key=key, timeout=90)
    try:
        response = client.responses.create(
            model=configured_model(),
            input=[
                {"role": "developer", "content": DEVELOPER_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            store=False,
        )
    except Exception as exc:
        raise AISpecsError(_friendly_openai_error(exc)) from exc

    return _parse_suggestions(_response_text(response), {row.i for row in rows})


def _friendly_openai_error(exc: Exception) -> str:
    message = str(exc)
    status_code = getattr(exc, "status_code", None)
    lowered = message.lower()
    if status_code == 429 and "insufficient_quota" in lowered:
        return (
            "OpenAI quota is exhausted for this API key. Add billing/credits in the OpenAI platform, "
            "or switch .streamlit/secrets.toml openai_model to a model your account can use. "
            "No specs were changed."
        )
    if "insufficient_quota" in lowered or "exceeded your current quota" in lowered:
        return (
            "OpenAI quota is exhausted for this API key. Add billing/credits in the OpenAI platform, "
            "then try again. No specs were changed."
        )
    if status_code == 429 or "rate_limit" in lowered:
        return "OpenAI rate limit reached. Wait a moment and try again. No specs were changed."
    if status_code == 401 or "invalid_api_key" in lowered:
        return "OpenAI API key is invalid. Check .streamlit/secrets.toml. No specs were changed."
    if status_code == 403:
        return "OpenAI rejected access for this key or model. Check model access and billing. No specs were changed."
    return f"OpenAI request failed: {message}"


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", "")
    if output_text:
        return str(output_text)
    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", "")
            if text:
                parts.append(str(text))
    return "\n".join(parts)


def _parse_suggestions(raw_text: str, allowed_indexes: set[int]) -> list[SpecSuggestion]:
    text = str(raw_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    if not text:
        raise AISpecsError("AI returned an empty response.")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AISpecsError("AI returned malformed JSON. No specs were changed.") from exc

    values = payload.get("values") if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        raise AISpecsError("AI JSON did not include a values list. No specs were changed.")

    suggestions: list[SpecSuggestion] = []
    for entry in values:
        if not isinstance(entry, dict):
            continue
        try:
            index = int(entry.get("i"))
        except (TypeError, ValueError):
            continue
        if index not in allowed_indexes:
            continue
        value = str(entry.get("value", "") or "").strip()
        suggestions.append(SpecSuggestion(i=index, value=value))
    return suggestions
