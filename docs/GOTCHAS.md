# Gotchas — read before editing a page

These are the non-obvious traps in this codebase. Most of the app's historical
bugs (see the long list of "Fix…" commits) come from the first one. If you
understand these five, you'll avoid re-introducing bugs that have already been
fixed once.

---

## 1. Streamlit widgets keep their OWN copy of state 🔴 (the big one)

**The trap.** When you render a widget with a `key=`, Streamlit stores that
widget's value in `st.session_state[key]` and treats *that* as the source of
truth — not your data model. So this does **not** work the way it looks:

```python
details["title"] = "New value"          # you change the model
st.text_input("Title", key=f"title_{ino}", value=details["title"])
# ...the box STILL shows the old value, because st.session_state["title_..."]
# already exists and wins over `value=`.
```

Worse, on the next rerun the widget writes its stale value *back* into
`details["title"]`, silently undoing your change.

**Where this bites and how the code handles it:**

- **Text fields** (`title`, `short_title`, `mfg_model`): "Format Visible Text"
  runs `state.format_all_visible_text()`, which reads from the *widget keys*,
  formats, and writes back into the widget keys via `set_basic_info_state()`.
  It must do this before widgets are re-instantiated — either from an
  `on_click` callback (the General tab's button) or, for the full-screen
  editor's toolbar button, from `state.apply_pending_format_all()`, which
  `app.main()` runs before `PAGE_RENDERERS[page]()` on the rerun the editor
  queues via `PENDING_FORMAT_ALL_KEY`. Doing either inline mid-script instead
  raises `StreamlitAPIException`.

- **Data grids** (features, includes, highlights, specs): rendered through
  `ui/grid.stable_data_editor()`. It deliberately avoids remounting the grid
  while the user is mid-edit (so typing/pasting isn't wiped). To make a
  *programmatic* change (like Format) show up immediately, you must call
  `reset_stable_data_editor(key)` so the grid remounts from the model. This is
  exactly the fix for "Format didn't update Features/Includes."

- **Category dropdown** (`category_select_{ino}`): a selectbox ignores its
  `index=` once its key exists, so after a clone the model was correct but the
  dropdown showed the old pick. Fix: `state._should_reset_item_widget_key()`
  clears that key on clone.

- **The description editor** (`ui/editor.py` + `ui/html_editor_component/`): a
  custom CodeMirror component. It has its own value-sync dance
  (`state.sync_description_state`, the component's `commitValue`/forced-sync).
  When the value is changed programmatically it must be *pushed* to the
  component and *reported back* to Streamlit, or a tab-switch reverts it.

**The lesson:** if you change `details[...]` or an `items[...]` list from
outside a widget (a button, a callback, a clone, a format pass) and it doesn't
show up, the culprit is almost always a stale widget key. Reset the key.
`state.reset_item_widget_state()` is the central list of per-item widget keys —
add new widgets there.

---

## 2. Parent/child relationships are encoded positionally in `queue_df`

There is no `parent_id` column. The `ATR Type` column encodes structure by
*position*:

- `"Parent (N)"` marks a parent,
- a **blank** `""` marks a child of the **nearest parent above it**,
- `"Standalone"` (or anything else) is neither and closes the current parent
  group.

`services/relationships.current_relationships()` decodes this;
`apply_relationships()` rewrites it (and reorders rows so children sit directly
under their parent). `services/variants.parent_child_groups()` re-derives groups
the same way. If you touch queue ordering, preserve this invariant or
parent/child structure silently corrupts.

---

## 3. Children carry no content — and that asymmetry breaks round-trips

Child SKUs are configured through their parent's Var Opts, so they produce **no
rows** in the content export (`build_output_df` skips them). But they **do**
appear in the `Input` sheet (`build_input_sheet_df` keeps them).

The trap (a real bug fixed 2026-07-25): on re-import, `parse_output_excel()`
must take the item list from the **Input sheet** (which has children), *not*
from the content sheet (which never does). Intersecting the two silently drops
every child. The `Input` sheet order is authoritative.

---

## 4. Deploys wipe user saves 🔴

The deploy host has an **ephemeral filesystem**: it rebuilds from git on every
push. Anything written only to local disk at runtime is gone after a redeploy.

- **User autosaves** (`data/saves/`, gitignored) are on borrowed time. Tell
  users to **export to Excel before any deploy**.
- **Reference-data edits** (rules, categories, warranty) survive only because
  `services/git_sync.py` pushes them *back into git* when an admin saves them.
  If `git_sync` has no token configured, those edits are also ephemeral.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full picture.

---

## 5. `input_title` / `input_mfg_item` are frozen — never overwrite them

`details["input_title"]` and `details["input_mfg_item"]` are the **as-uploaded**
snapshot. The editable `title` / `mfg_item` can change, but the Input sheet and
the queue must still show what was originally uploaded. So:

- These two are in `state._CLONE_PRESERVED_DETAIL_FIELDS` — a "Similar To" clone
  copies everything *except* the target's identity fields (`item_no`,
  `atr_type`, `jira`, `input_title`, `input_mfg_item`).
- Note `mfg_item` (the editable one) **is** cloned; only `input_mfg_item` is
  preserved. Mixing these up was a bug fixed 2026-07-25.

---

## Bonus: `unsafe_allow_html=True` is everywhere — sanitize user text

The UI builds a lot of raw HTML (60+ sites). Any time you interpolate a
user-typed value into HTML, run it through `html.escape()` (or, for the
description, `export.sanitize_description_html()`) first, or you reintroduce the
stored-XSS bug that was already patched once.
