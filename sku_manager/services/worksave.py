"""Per-user autosave of the in-progress workspace to local JSON files.

Each user gets one file under data/saves/. Every item carries its own
"last edited" timestamp; items expire EXPIRY_HOURS after their last edit,
so today's work survives 3 days and tomorrow's work 3 days from then.

All disk I/O for work-in-progress lives here, so switching to remote
storage (e.g. a private GitHub data repo) later only touches this module.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from sku_manager.config import QUEUE_COLUMNS


SAVE_DIR = Path(__file__).resolve().parents[1] / "data" / "saves"
LOCK_DIR = SAVE_DIR / ".locks"
SAVE_VERSION = 1
EXPIRY_HOURS = 72
LEASE_SECONDS = 20 * 60
LOCK_STALE_SECONDS = 30


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


def _save_key(user: str) -> str:
    user_text = str(user or "").strip()
    digest = hashlib.sha256(user_text.encode("utf-8")).hexdigest()[:12]
    return f"{_slug(user_text)}-{digest}"


def save_path(user: str) -> Path:
    return SAVE_DIR / f"{_save_key(user)}.json"


def _legacy_save_path(user: str) -> Path:
    return SAVE_DIR / f"{_slug(user)}.json"


def _lease_path(user: str) -> Path:
    return LOCK_DIR / f"{_save_key(user)}.lease.json"


def _write_lock_path(user: str) -> Path:
    return LOCK_DIR / f"{_save_key(user)}.write.lock"


def _read_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


@contextmanager
def _exclusive_lock(path: Path, *, timeout: float = 5.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    token = f"{os.getpid()}:{uuid.uuid4().hex}"
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
                lock_file.write(token)
            break
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
                if age > LOCK_STALE_SECONDS:
                    path.unlink()
                    continue
            except OSError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock {path.name}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def session_id() -> str:
    sid = st.session_state.get("_worksave_session_id")
    if not sid:
        sid = uuid.uuid4().hex
        st.session_state["_worksave_session_id"] = sid
    return str(sid)


def _fresh_lease(data: dict | None) -> bool:
    if not data:
        return False
    expires_at = _parse_ts(data.get("expires_at"))
    return bool(expires_at and expires_at > _now())


def _lease_payload(user: str) -> dict[str, Any]:
    now = _now()
    return {
        "version": SAVE_VERSION,
        "user": user,
        "session_id": session_id(),
        "updated_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(seconds=LEASE_SECONDS)).isoformat(timespec="seconds"),
    }


def acquire_user_lease(user: str) -> tuple[bool, dict[str, Any]]:
    user = str(user or "").strip()
    if not user:
        return False, {"reason": "missing_user"}

    path = _lease_path(user)
    lease = _lease_payload(user)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        current = _read_file(path)
        if _fresh_lease(current) and current.get("session_id") != session_id():
            return False, {
                "reason": "active_elsewhere",
                "user": str(current.get("user", user)),
                "expires_at": str(current.get("expires_at", "")),
            }
        _write_json_atomic(path, lease)
        return True, lease
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as lease_file:
            json.dump(lease, lease_file, ensure_ascii=False, default=str)
        return True, lease


def refresh_user_lease(user: str) -> bool:
    ok, info = acquire_user_lease(user)
    if ok:
        st.session_state.pop("_worksave_lease_conflict", None)
        return True
    st.session_state["_worksave_lease_conflict"] = info
    return False


def release_user_lease(user: str) -> None:
    user = str(user or "").strip()
    if not user:
        return
    path = _lease_path(user)
    data = _read_file(path)
    if data and data.get("session_id") == session_id():
        try:
            path.unlink()
        except OSError:
            pass


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
    if not refresh_user_lease(user):
        return None

    path = save_path(user)
    with _exclusive_lock(_write_lock_path(user)):
        previous = _read_file(path) or _read_file(_legacy_save_path(user)) or {}
        prev_items = previous.get("items") or {}
        prev_stamps = previous.get("item_saved_at") or {}

        now_iso = _now().isoformat(timespec="seconds")
        item_saved_at: dict[str, str] = {}
        for ino, item in payload["items"].items():
            prev_stamp = prev_stamps.get(ino)
            unchanged = ino in prev_items and _item_fingerprint(item) == _item_fingerprint(prev_items[ino])
            item_saved_at[ino] = prev_stamp if prev_stamp and unchanged else now_iso

        data = {
            "version": SAVE_VERSION,
            "user": user,
            "save_key": _save_key(user),
            "saved_at": now_iso,
            **payload,
            "item_saved_at": item_saved_at,
        }
        _write_json_atomic(path, data)
    return now_iso


def load_workspace(user: str) -> dict | None:
    """Read the user's save, dropping items older than EXPIRY_HOURS.

    Returns None when there is no save or everything in it has expired
    (the stale file is deleted in that case).
    """
    path = save_path(user)
    data = _read_file(path)
    if data is None:
        legacy_path = _legacy_save_path(user)
        if legacy_path != path:
            data = _read_file(legacy_path)
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
    if not refresh_user_lease(user):
        return
    digest = workspace_digest()
    if digest == st.session_state.get("_worksave_digest"):
        return
    try:
        saved_at = save_workspace(user)
    except Exception as exc:
        from sku_manager.services import metrics
        metrics.record_error(user, exc)
        return
    if saved_at:
        st.session_state["_worksave_digest"] = digest
        st.session_state["_worksave_saved_at"] = saved_at


def all_saves_summary() -> list[dict[str, Any]]:
    """Live per-user rollup of the saved batches, for the admin dashboard.

    Each malformed file is skipped rather than raising.
    """
    summary: list[dict[str, Any]] = []
    if not SAVE_DIR.exists():
        return summary

    for path in sorted(SAVE_DIR.glob("*.json")):
        data = _read_file(path)
        if not data or not isinstance(data.get("items"), dict):
            continue

        queue = data.get("queue") or []
        completed = sum(
            1 for row in queue if str(row.get("Status", "")).strip().lower() == "completed"
        )
        sku_count = len(data["items"])

        batch = ""
        for row in queue:
            jira = str(row.get("JIRA", "")).strip()
            if jira:
                batch = jira
                break
        if not batch and queue:
            batch = str(queue[0].get("Item No", "")).strip()

        stamps = [_parse_ts(v) for v in (data.get("item_saved_at") or {}).values()]
        stamps = [ts for ts in stamps if ts]
        if stamps:
            oldest_age_h = (_now() - min(stamps)).total_seconds() / 3600
            hours_to_expiry = round(EXPIRY_HOURS - oldest_age_h, 1)
        else:
            hours_to_expiry = None

        summary.append({
            "user": str(data.get("user", path.stem)),
            "batch": batch,
            "sku_count": sku_count,
            "completed": completed,
            "in_progress": max(0, sku_count - completed),
            "saved_at": str(data.get("saved_at", "")),
            "hours_to_expiry": hours_to_expiry,
        })
    return summary


def save_dir_stats() -> dict[str, Any]:
    """File count and total size (KB) of the save folder."""
    if not SAVE_DIR.exists():
        return {"files": 0, "kb": 0.0}
    files = list(SAVE_DIR.glob("*.json"))
    total = sum(f.stat().st_size for f in files if f.exists())
    return {"files": len(files), "kb": round(total / 1024, 1)}


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
