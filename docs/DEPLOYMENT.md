# Deployment & data persistence

## How it runs

- **Local:** `streamlit run streamlit_app.py` (Python 3.12, deps from
  `requirements.txt`). `runtime.txt` pins `python-3.12`.
- **Hosted:** deployed on a Streamlit-style host that **redeploys from git on
  every push** onto an **ephemeral filesystem**.

That second fact drives everything below.

## The ephemeral-filesystem trap 🔴

On redeploy, the container's disk is wiped and rebuilt from the git repo.
**Anything written only to local disk at runtime is lost.** Two kinds of
runtime data are affected, handled very differently:

### 1. User autosaves — NOT persisted across deploys
`services/worksave.py` autosaves each user's in-progress work to
`data/saves/<user>.json`. That folder is **gitignored** (correctly — you don't
want half-finished work in git), which means it is **not** rebuilt on redeploy
and is **wiped**.

- Autosaves expire after `EXPIRY_HOURS = 72` anyway.
- Concurrent editing is guarded by lease locks under `data/saves/.locks/`
  (`LEASE_SECONDS`, `LOCK_STALE_SECONDS`) so two sessions don't clobber one
  save. These locks are also local/ephemeral.

**Operational rule: tell users to export their work to Excel before any
deploy.** A deploy is effectively "wipe the scratch disk."

### 2. Reference-data edits — persisted via git_sync
Admin edits to the reference tables (special-char rules, category mapping,
warranty master, editor rules) are written to tracked files
(`data/reference_data.json`, the `*.tsv` files). To survive a redeploy those
changes must reach git, so `services/git_sync.py` **commits and pushes them
back to `origin/main`** when an admin saves.

Key facts about `git_sync`:
- It needs a token: `SKU_GIT_TOKEN` env var, or `st.secrets["git_token"]`. With
  no token, `is_configured()` is False and edits stay ephemeral (lost on
  redeploy).
- It only pushes over an **HTTPS** `origin` remote (injects the token into the
  URL).
- It **never raises** — any git failure (missing binary, network, non-fast-
  forward) is swallowed so a UI save never crashes. That means a failed push is
  *silent*; the admin's change is saved locally but may not reach GitHub.
- It handles the **non-fast-forward race**: if someone pushed code elsewhere,
  the container's frozen git history is behind `origin/main`. A blind push is
  rejected, so it retries once via `fetch` + `rebase`, and aborts the rebase
  cleanly if that also fails.

## Secrets / configuration

Configured via environment variables or Streamlit secrets
(`.streamlit/secrets.toml`, gitignored):

| Key | Purpose |
|---|---|
| `OPENAI_API_KEY` / `openai_api_key` | AI spec autofill (`services/ai_specs.py`) |
| `OPENAI_MODEL` | Optional; defaults to `o3` |
| `SKU_GIT_TOKEN` / `git_token` | Lets `git_sync` push reference-data edits |
| `reference_data_password` | Gates edits to the reference tables |
| `save_users` | Optional override of the sidebar user list (`config.SAVE_USERS`) |

Never commit real secrets. `.gitignore` already excludes
`.streamlit/secrets.toml`.

## Deploy checklist

1. Ensure CI is green (the `Tests` workflow) on the commit you're deploying.
2. Warn active users to **export their work** — the deploy wipes `data/saves/`.
3. Confirm `SKU_GIT_TOKEN` is set in the host if admins edit reference data,
   or those edits won't persist.
4. Push to `main` → host redeploys from git.

## Longer-term note

The single-point design (session state + local JSON saves) is fine for the
current user count. The README already flags that multi-user durability would
mean moving the save store to a real backend (Supabase / a database / a private
data repo). All disk I/O for saves is deliberately isolated in
`services/worksave.py`, so that migration touches one module.
