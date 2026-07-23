"""Hidden /admin dashboard — live throughput, performance, and system health.

Reached only by typing https://<app>/admin (not linked anywhere; Streamlit's
auto page-nav is hidden via .streamlit/config.toml). Gated by the shared admin
password on top of the hidden URL.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from sku_manager.pages.reference_data import admin_password
from sku_manager.services import metrics, worksave


def _git_sha() -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return sha.decode().strip() or "unknown"
    except Exception:
        pass
    # Fallback: read .git without invoking git.
    try:
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            sha = (root / ".git" / ref).read_text(encoding="utf-8").strip()
            return sha[:7]
        return head[:7]
    except Exception:
        return "unknown"


def _fmt_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _gate() -> bool:
    if st.session_state.get("_admin_dash_ok"):
        return True

    st.title("🔒 Admin")
    password = admin_password()
    if not password:
        st.error(
            "No admin password configured. Set `reference_data_password` in "
            "Streamlit secrets or the SKU_REFERENCE_DATA_PASSWORD env var."
        )
        return False

    entered = st.text_input("Password", type="password")
    if st.button("Enter", type="primary"):
        if entered and entered == password:
            st.session_state["_admin_dash_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def _render_throughput() -> None:
    st.subheader("Throughput")
    rows = worksave.all_saves_summary()
    if not rows:
        st.info("No saved work on the server right now.")
        return

    total_skus = sum(r["sku_count"] for r in rows)
    total_done = sum(r["completed"] for r in rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Active users", len(rows))
    c2.metric("SKUs in flight", total_skus)
    c3.metric("Completed", total_done)

    df = pd.DataFrame(rows)
    chart_df = df.set_index("user")[["completed", "in_progress"]]
    st.bar_chart(chart_df)

    display = df.rename(columns={
        "user": "User",
        "batch": "Batch",
        "sku_count": "SKUs",
        "completed": "Completed",
        "in_progress": "In progress",
        "saved_at": "Last saved",
        "hours_to_expiry": "Hrs to expiry",
    })
    st.dataframe(display, hide_index=True, width="stretch")


def _render_performance() -> None:
    st.subheader("Performance & speed")
    snap = metrics.snapshot()
    render = snap["render"]
    if render["count"] == 0:
        st.info("No render timings collected yet - use the app, then refresh.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Last render", f"{render['last']:.0f} ms")
        c2.metric("Mean", f"{render['mean']:.0f} ms")
        c3.metric("p95", f"{render['p95']:.0f} ms")
        c4.metric("Slowest", f"{render['max']:.0f} ms")
        st.caption(
            f"Across the last {render['count']} reruns from all sessions. "
            "The first render per session is the slow one (caches cold); "
            "steady-state is what users feel."
        )

    phases = snap["phases"]
    if phases:
        phase_df = pd.DataFrame(
            [
                {"Phase": name, "Mean ms": round(v["mean"], 1), "Last ms": round(v["last"], 1), "Samples": v["count"]}
                for name, v in phases.items()
            ]
        )
        st.dataframe(phase_df, hide_index=True, width="stretch")


def _render_health() -> None:
    st.subheader("App & system health")
    snap = metrics.snapshot()
    stats = worksave.save_dir_stats()

    c1, c2, c3 = st.columns(3)
    c1.metric("Deployed commit", _git_sha())
    c2.metric("Uptime", _fmt_uptime(snap["uptime_seconds"]))
    c3.metric("Save files", stats["files"])

    c4, c5, c6 = st.columns(3)
    c4.metric("Python", platform.python_version())
    c5.metric("Streamlit", st.__version__)
    c6.metric("Saves size", f"{stats['kb']:.0f} KB")

    err = snap["last_error"]
    if err:
        st.error(
            f"Last autosave error ({err['at']}, user '{err['user']}'): {err['message']}"
        )
    else:
        st.success("No autosave errors recorded.")

    st.caption(f"Python build: {sys.version.split()[0]} • snapshot resets on redeploy.")


def render() -> None:
    st.set_page_config(page_title="Admin", layout="wide")
    if not _gate():
        return

    head_l, head_r = st.columns([4, 1])
    head_l.title("📊 Admin Dashboard")
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    head_r.caption(f"As of {now}")
    if head_r.button("🔄 Refresh", width="stretch"):
        st.rerun()

    _render_throughput()
    st.divider()
    _render_performance()
    st.divider()
    _render_health()


render()
