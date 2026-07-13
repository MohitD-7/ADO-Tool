"""Per-user autosave of the in-progress workspace to local JSON files.

Each user gets one file under data/saves/. Every item carries its own
"last edited" timestamp; items expire EXPIRY_HOURS after their last edit,
so today's work survives 3 days and tomorrow's work 3 days from then.

All disk I/O for work-in-progress lives here, so switching to remote
storage (e.g. a private GitHub data repo) later only touches this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from sku_manager.config import QUEUE_COLUMNS


SAVE_DIR = Path(__file__).resolve().parents[1] / "data" / "saves"
SAVE_VERSION = 1
EXPIRY_HOURS = 72


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _slug(user: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(user).strip().lower()).strip("-")
    return slug or "user"


def save_path(user: str) -> Path:
    return SAVE_DIR / f"{_slug(user)}.json"


def _read_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _item_fingerprint(item: Any) -> str:
    return json.dumps(item, sort_keys=True, default=str)


def _workspace_payload() -> dict[str, Any]:
    queue_df = st.session_state.get("queue_df")
    if isinstance(queue_df, pd.DataFrame) and not queue_df.empty:
        queue = queue_df.fillna("").astype(str).to_dict("records")
    else:
        queue = []
    return {
        "current_item_no": str(st.session_state.get("current_item_no", "")),
        "queue": queue,
        "items": st.session_state.get("items", {}) or {},
        "variants": st.session_state.get("variants", {}) or {},
    }


def workspace_digest() -> str:
    payload = _workspace_payload()
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def save_workspace(user: str) -> str | None:
    """Atomically write the current workspace to the user's file.

    Returns the ISO save timestamp, or None when there is nothing to save.
    Per-item timestamps only advance for items whose content changed, which
    gives each item its own rolling EXPIRY_HOURS lifetime.
    """
    user = str(user or "").strip()
    payload = _workspace_payload()
    if not user or not payload["items"]:
        return None

    path = save_path(user)
    previous = _read_file(path) or {}
    prev_items = previous.get("items") or {}
    prev_stamps = previous.get("item_saved_at") or {}

    now_iso = _now().isoformat(timespec="seconds")
    item_saved_at: dict[str, str] = {}
    for ino, item in payload["items"].items():
        prev_stamp = prev_stamps.get(ino)
        if prev_stamp and ino in prev_items and _item_fingerprint(item) == _item_fingerprint(prev_items[ino]):
            item_saved_at[ino] = prev_stamp
        else:
            item_saved_at[ino] = now_iso

    data = {
        "version": SAVE_VERSION,
        "user": user,
        "saved_at": now_iso,
        **payload,
        "item_saved_at": item_saved_at,
    }
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp_path, path)
    return now_iso


def load_workspace(user: str) -> dict | None:
    """Read the user's save, dropping items older than EXPIRY_HOURS.

    Returns None when there is no save or everything in it has expired
    (the stale file is deleted in that case).
    """
    path = save_path(user)
    data = _read_file(path)
    if not data or not isinstance(data.get("items"), dict):
        return None

    cutoff = _now() - timedelta(hours=EXPIRY_HOURS)
    fallback_ts = _parse_ts(data.get("saved_at")) or _now()
    stamps = data.get("item_saved_at") or {}

    fresh_items = {
        ino: item
        for ino, item in data["items"].items()
        if (_parse_ts(stamps.get(ino)) or fallback_ts) >= cutoff
    }
    if not fresh_items:
        try:
            path.unlink()
        except OSError:
            pass
        return None

    data["items"] = fresh_items
    data["queue"] = [
        row
        for row in (data.get("queue") or [])
        if str(row.get("Item No", "")).strip() in fresh_items
    ]
    if data.get("current_item_no") not in fresh_items:
        data["current_item_no"] = next(iter(fresh_items), "")
    return data


def restore_workspace(payload: dict) -> None:
    """Load a saved payload into session state (mirrors the Review load-back)."""
    from sku_manager.state import set_batch, set_description_state

    items = payload.get("items") or {}
    queue_rows = payload.get("queue") or []
    if not queue_rows:
        # Fallback: rebuild minimal queue rows from the items themselves.
        queue_rows = [
            {
                "ATR Type": items[ino].get("details", {}).get("atr_type", "Standalone"),
                "JIRA": items[ino].get("details", {}).get("jira", ""),
                "Item No": ino,
                "Title": items[ino].get("details", {}).get("input_title", "")
                or items[ino].get("details", {}).get("title", ""),
                "Mfg Item": items[ino].get("details", {}).get("input_mfg_item", "")
                or items[ino].get("details", {}).get("mfg_item", ""),
                "Status": "",
            }
            for ino in items
        ]

    set_batch(pd.DataFrame(queue_rows, columns=QUEUE_COLUMNS))
    st.session_state["items"] = items
    st.session_state["variants"] = payload.get("variants") or {}
    current = payload.get("current_item_no") or ""
    st.session_state["current_item_no"] = current if current in items else next(iter(items), "")
    for ino, item in items.items():
        set_description_state(ino, item.get("details", {}).get("description", ""))
    st.session_state["active_page"] = "SKU Workspace"


def autosave_tick() -> None:
    """Save the workspace whenever its content changed since the last save.

    Called at the end of every rerun; a local write costs milliseconds, so
    every edit is on disk by the end of the rerun that produced it.
    """
    user = str(st.session_state.get("save_user", "") or "")
    if not user or not st.session_state.get("items"):
        return
    digest = workspace_digest()
    if digest == st.session_state.get("_worksave_digest"):
        return
    try:
        saved_at = save_workspace(user)
    except Exception:
        return
    if saved_at:
        st.session_state["_worksave_digest"] = digest
        st.session_state["_worksave_saved_at"] = saved_at


def purge_expired_files() -> None:
    """Delete save files whose newest item edit is older than EXPIRY_HOURS."""
    if not SAVE_DIR.exists():
        return
    cutoff = _now() - timedelta(hours=EXPIRY_HOURS)
    for path in SAVE_DIR.glob("*.json"):
        data = _read_file(path)
        if data is None:
            continue
        stamps = [_parse_ts(value) for value in (data.get("item_saved_at") or {}).values()]
        stamps = [ts for ts in stamps if ts] or [_parse_ts(data.get("saved_at"))]
        newest = max((ts for ts in stamps if ts), default=None)
        if newest is None or newest < cutoff:
            try:
                path.unlink()
            except OSError:
                pass


@st.cache_resource(show_spinner=False)
def purge_expired_files_once() -> bool:
    """Run the purge once per server process, never failing the app."""
    try:
        purge_expired_files()
    except Exception:
        pass
    return True
