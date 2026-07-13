"""In-process metrics for the hidden /admin dashboard.

Streamlit Community Cloud runs one Python process, so module-level state here
collects timings across every user's reruns. It is a live snapshot only —
everything resets when the app redeploys or restarts. All helpers swallow
their own errors so instrumentation can never break the app.
"""
from __future__ import annotations

import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from statistics import mean
from typing import Any


START_TIME = time.time()

RENDER_MS: deque[float] = deque(maxlen=200)
PHASE_MS: dict[str, deque[float]] = {}
LAST_ERROR: dict[str, str] | None = None

_PHASE_MAXLEN = 200


def record_render(ms: float) -> None:
    try:
        RENDER_MS.append(float(ms))
    except Exception:
        pass


def record_phase(name: str, ms: float) -> None:
    try:
        bucket = PHASE_MS.get(name)
        if bucket is None:
            bucket = PHASE_MS[name] = deque(maxlen=_PHASE_MAXLEN)
        bucket.append(float(ms))
    except Exception:
        pass


def record_error(user: str, exc: BaseException) -> None:
    global LAST_ERROR
    try:
        LAST_ERROR = {
            "user": str(user or ""),
            "message": f"{type(exc).__name__}: {exc}",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    except Exception:
        pass


@contextmanager
def timer(name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        record_phase(name, (time.perf_counter() - start) * 1000)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[idx]


def snapshot() -> dict[str, Any]:
    renders = list(RENDER_MS)
    phases: dict[str, dict[str, Any]] = {}
    for name, bucket in PHASE_MS.items():
        vals = list(bucket)
        if vals:
            phases[name] = {"mean": mean(vals), "last": vals[-1], "count": len(vals)}
    return {
        "render": {
            "count": len(renders),
            "last": renders[-1] if renders else 0.0,
            "mean": mean(renders) if renders else 0.0,
            "p95": _percentile(renders, 95),
            "max": max(renders) if renders else 0.0,
        },
        "phases": phases,
        "uptime_seconds": max(0.0, time.time() - START_TIME),
        "last_error": LAST_ERROR,
    }
