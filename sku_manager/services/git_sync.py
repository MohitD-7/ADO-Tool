"""
Best-effort git commit+push for data files that are checked into the repo
but also written at runtime (reference_data.json, editor_rules.json, the
category_mapping/warranty TSVs). The deploy host redeploys from git on every
push and has an ephemeral filesystem, so any admin edit that only lands on
local disk is lost the next time anyone pushes code. Pushing here keeps git
current so a redeploy never reverts a live edit.

No-ops silently (never raises) when no token is configured or the push
fails, so a save in the UI never breaks because of a git problem.

Token lookup checks, in order: the SKU_GIT_TOKEN env var, then
st.secrets["git_token"] (the Streamlit Cloud secrets convention already
used for reference_data_password / openai_api_key in this app).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TIMEOUT = 20


def _token() -> str:
    env_token = os.getenv("SKU_GIT_TOKEN", "").strip()
    if env_token:
        return env_token
    try:
        import streamlit as st
        return str(st.secrets.get("git_token", "")).strip()
    except Exception:
        return ""


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=_TIMEOUT, check=True,
    )


def _push_url(token: str) -> str | None:
    try:
        origin = _run(["git", "remote", "get-url", "origin"]).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if not origin.startswith("https://"):
        return None
    return origin.replace("https://", f"https://x-access-token:{token}@", 1)


def commit_and_push(paths: list[Path], message: str) -> bool:
    """Stage, commit, and push the given paths. Returns True if a push happened."""
    token = _token()
    if not token:
        return False

    rel_paths = [str(p.resolve().relative_to(_REPO_ROOT)) for p in paths]
    try:
        _run(["git", "add", *rel_paths])
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=_REPO_ROOT, capture_output=True, timeout=_TIMEOUT,
        )
        if staged.returncode == 0:
            return False  # nothing actually changed

        _run([
            "git", "-c", "user.email=sku-manager-bot@users.noreply.github.com",
            "-c", "user.name=SKU Manager Bot",
            "commit", "-m", message,
        ])

        push_url = _push_url(token)
        if push_url:
            _run(["git", "push", push_url, "HEAD:main"])
        else:
            _run(["git", "push"])
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
