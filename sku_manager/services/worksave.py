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
from sku_manager.services import metrics


SAVE_DIR = Path(__file__).resolve().parents[1] / "data" / "saves"
LOCK_DIR = SAVE_DIR / ".locks"
SAVE_VERSION = 1
EXPIRY_HOURS = 72
LEASE_SECONDS = 5 * 60
LOCK_STALE_SECONDS = 30
LEASE_REFRESH_SECONDS = 2 * 60
FULL_SWEEP_SECONDS = 30

# Session-state keys for the per-session save cache. Everything here is a
# cache over the user's save file; reset_session_cache() must drop all of it
# whenever the save user changes or their lease is released.
_FPS_KEY = "_worksave_saved_fps"        # dict[item_no, fingerprint] at last save
_META_KEY = "_worksave_saved_meta"      # fingerprint of queue/variants/current at last save
_STAMPS_KEY = "_worksave_item_stamps"   # dict[item_no, iso timestamp] at last save
_LEASE_TS_KEY = "_worksave_lease_ts"    # monotonic time of last on-disk lease refresh
_SWEEP_TS_KEY = "_worksave_sweep_ts"    # monotonic time of last full change sweep


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


def force_acquire_user_lease(user: str) -> tuple[bool, dict[str, Any]]:
    """Overwrite any existing lease for this user.

    For when the lease holder is a dead session (closed tab, crashed browser,
    server restart) and the real person is locked out. If the old session is
    in fact still alive, it loses the lease on its next refresh (at most
    LEASE_REFRESH_SECONDS later) and its autosave stops cleanly.
    """
    user = str(user or "").strip()
    if not user:
        return False, {"reason": "missing_user"}
    lease = _lease_payload(user)
    _write_json_atomic(_lease_path(user), lease)
    st.session_state[_LEASE_TS_KEY] = time.monotonic()
    st.session_state.pop("_worksave_lease_conflict", None)
    return True, lease


def refresh_user_lease(user: str) -> bool:
    ok, info = acquire_user_lease(user)
    if ok:
        st.session_state[_LEASE_TS_KEY] = time.monotonic()
        st.session_state.pop("_worksave_lease_conflict", None)
        return True
    st.session_state.pop(_LEASE_TS_KEY, None)
    st.session_state["_worksave_lease_conflict"] = info
    return False


def ensure_user_lease(user: str) -> bool:
    """Keep the lease alive without touching disk on every rerun.

    A lease refreshed less than LEASE_REFRESH_SECONDS ago is trusted as-is:
    while it is fresh no other session can take it over, so re-checking the
    file would only confirm what we already know.
    """
    if not st.session_state.get("_worksave_lease_conflict"):
        last = st.session_state.get(_LEASE_TS_KEY)
        if last is not None and time.monotonic() - float(last) < LEASE_REFRESH_SECONDS:
            return True
    return refresh_user_lease(user)


def reset_session_cache() -> None:
    """Drop every per-session save cache (call when the save user changes)."""
    for key in (_FPS_KEY, _META_KEY, _STAMPS_KEY, _LEASE_TS_KEY, _SWEEP_TS_KEY):
        st.session_state.pop(key, None)


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


def _meta_fingerprint(payload: dict[str, Any]) -> str:
    """Fingerprint of everything in the payload except item content."""
    raw = json.dumps(
        {
            "current_item_no": payload["current_item_no"],
            "queue": payload["queue"],
            "variants": payload["variants"],
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _workspace_changed(payload: dict[str, Any]) -> bool:
    """True when the workspace differs from the last saved state.

    Stays O(current item) on a normal rerun: only the current item is
    fingerprinted, plus the small queue/variants meta blob. Item add/remove
    is caught by the key-set comparison. As insurance against a flow that
    mutates a non-current item, every item is swept at most once per
    FULL_SWEEP_SECONDS (a save always fingerprints everything anyway).
    """
    saved_fps = st.session_state.get(_FPS_KEY)
    if saved_fps is None:
        return True
    if st.session_state.get(_META_KEY) != _meta_fingerprint(payload):
        return True
    items = payload["items"]
    if items.keys() != saved_fps.keys():
        return True
    ino = payload["current_item_no"]
    if ino in items and _item_fingerprint(items[ino]) != saved_fps.get(ino):
        return True

    now = time.monotonic()
    last_sweep = float(st.session_state.get(_SWEEP_TS_KEY) or 0.0)
    if now - last_sweep >= FULL_SWEEP_SECONDS:
        st.session_state[_SWEEP_TS_KEY] = now
        return any(_item_fingerprint(item) != saved_fps.get(key) for key, item in items.items())
    return False


def mark_workspace_clean() -> None:
    """Record the current workspace as already saved (e.g. right after a restore).

    Item timestamps are left unset so the next real save re-seeds them from
    the file on disk, preserving each item's rolling expiry.
    """
    payload = _workspace_payload()
    st.session_state[_FPS_KEY] = {
        ino: _item_fingerprint(item) for ino, item in payload["items"].items()
    }
    st.session_state[_META_KEY] = _meta_fingerprint(payload)
    st.session_state.pop(_STAMPS_KEY, None)


def save_workspace(user: str) -> str | None:
    """Atomically write the current workspace to the user's file.

    Returns the ISO save timestamp, or None when there is nothing to save.
    Per-item timestamps only advance for items whose content changed, which
    gives each item its own rolling EXPIRY_HOURS lifetime. The previous
    save's fingerprints and timestamps are cached in session state (the
    lease guarantees no other session writes this file), so the old file is
    read back at most once per session.
    """
    user = str(user or "").strip()
    payload = _workspace_payload()
    if not user or not payload["items"]:
        return None
    if not refresh_user_lease(user):
        return None

    path = save_path(user)
    with _exclusive_lock(_write_lock_path(user)):
        prev_fps = st.session_state.get(_FPS_KEY)
        prev_stamps = st.session_state.get(_STAMPS_KEY)
        if prev_fps is None or prev_stamps is None:
            previous = _read_file(path) or _read_file(_legacy_save_path(user)) or {}
            prev_items = previous.get("items") or {}
            prev_fps = {ino: _item_fingerprint(item) for ino, item in prev_items.items()}
            prev_stamps = {
                str(ino): str(stamp)
                for ino, stamp in (previous.get("item_saved_at") or {}).items()
            }

        now_iso = _now().isoformat(timespec="seconds")
        new_fps: dict[str, str] = {}
        item_saved_at: dict[str, str] = {}
        for ino, item in payload["items"].items():
            fp = _item_fingerprint(item)
            new_fps[ino] = fp
            prev_stamp = prev_stamps.get(ino)
            unchanged = bool(prev_stamp) and prev_fps.get(ino) == fp
            item_saved_at[ino] = prev_stamp if unchanged else now_iso

        data = {
            "version": SAVE_VERSION,
            "user": user,
            "save_key": _save_key(user),
            "saved_at": now_iso,
            **payload,
            "item_saved_at": item_saved_at,
        }
        _write_json_atomic(path, data)

    st.session_state[_FPS_KEY] = new_fps
    st.session_state[_STAMPS_KEY] = item_saved_at
    st.session_state[_META_KEY] = _meta_fingerprint(payload)
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
    every edit is on disk by the end of the rerun that produced it. An
    unchanged rerun costs one current-item fingerprint and no disk I/O.
    """
    user = str(st.session_state.get("save_user", "") or "")
    if not user or not st.session_state.get("items"):
        return
    if not st.session_state.get("_worksave_restore_handled"):
        # A restore decision is still pending for this user; saving now would
        # overwrite the very file the user may be about to load.
        return
    if not ensure_user_lease(user):
        return
    if not _workspace_changed(_workspace_payload()):
        return
    try:
        with metrics.timer("worksave_save"):
            saved_at = save_workspace(user)
    except Exception as exc:
        metrics.record_error(user, exc)
        return
    if saved_at:
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
