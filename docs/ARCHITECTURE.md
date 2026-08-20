# Architecture

## What the app does

SKU Manager takes a batch of products ("SKUs") from an uploaded Excel file and
walks a user through filling in each SKU's marketing/technical content, then
exports everything in the row format a downstream system ingests. It also has a
**Review** mode that reverses the export back into an editable batch so a second
person can check the work.

There is **no database**. All live data sits in Streamlit's per-session memory
(`st.session_state`), backed by per-user JSON autosave files on disk.

## Layers

The code is layered. Higher layers may import lower ones, never the reverse.

```
streamlit_app.py            ← entry point (calls app.main)
        │
sku_manager/app.py          ← routing + per-run lifecycle
        │
sku_manager/pages/*.py      ← one render() per screen (UI)
sku_manager/ui/*.py         ← shared UI widgets (grid, editor, layout, components)
        │
sku_manager/services/*.py   ← business logic (PURE where possible — this is what tests target)
sku_manager/state.py        ← session-state shape + helpers
sku_manager/models.py       ← the item-record factory
sku_manager/config.py       ← constants (column names, user list, options)
        │
sku_manager/data/           ← seed data (defaults.py, reference_data.json, *.tsv)
                              + runtime saves/ (gitignored, written at runtime)
```

**Rule of thumb:** logic that decides *what the data should be* belongs in
`services/` (and gets a test). Code in `pages/` and `ui/` should be thin — it
wires widgets to services. When a page starts making real decisions, that
decision usually wants to move into a service so it can be tested.

## The data model (what lives in session state)

Four structures matter. Learn these and the app makes sense.

### 1. `queue_df` — the batch
A pandas DataFrame, columns `config.QUEUE_COLUMNS`:
`["ATR Type", "JIRA", "Item No", "Title", "Mfg Item", "Status"]`.

One row per SKU, in display order. **Relationships are encoded positionally in
the `ATR Type` column** (see GOTCHAS):
- `"Parent (N)"` — a parent with N children,
- `""` (blank) — a child of the nearest parent above it,
- `"Standalone"` — neither.

### 2. `items` — the content
A dict `{item_no: item_record}`. Each record is built by
`models.new_item_record()` and has this shape:

```python
{
  "details": {                 # scalar fields
     "item_no", "title", "short_title", "description",
     "mfg_item", "mfg_model", "category", "atr_type", "jira",
     "input_title", "input_mfg_item",   # FROZEN as-uploaded snapshot (see GOTCHAS)
     "warranty_brand", "warranty_months",
     "battery_info", "battery_material", "battery_type", "battery_quantity",
     "video_link", ...
  },
  "features":   [str, ...],          # bullet strings
  "highlights": [str, ...],          # bullet strings
  "includes":   [{"text", "sku"}],   # box-contents rows (fill text OR sku, not both)
  "specs":      [{"category", "group", "Spec", "Value"}],
  "comments":   {field_key: note},   # per-field reviewer notes
  "links":      {"general": [...], "features": [...], ...},   # source/reference links
}
```

### 3. `variants` — the "Var Opts" / "wear off" data
`{parent_sku: {"attributes": [str, ...], "values": {child_sku: {attr: value}}}}`.
Only parents with children have entries. This is what the Var Opts tab edits and
what `services/variants.build_variant_df()` flattens for export.

### 4. Reference tables (shared lookups)
Loaded once from `data/reference_data.json` by `services/reference_store.py`
into these session keys: `battery_materials_df`, `battery_types_df`,
`special_rules_df`, `warranty_df`, `category_mapping_df`, and `html_template`.
`special_rules_df` drives the "Format Visible Text" cleaning;
`category_mapping_df` drives category → spec-template prefill.

## The per-run lifecycle

Streamlit re-runs the whole script top-to-bottom on every interaction.
`app.main()` is that script:

1. `ensure_visible_row_checkboxes()` — a small frontend patch.
2. `st.set_page_config(...)`.
3. `init_state()` — seed session-state defaults + load reference tables (once).
4. `worksave.purge_expired_files_once()` — drop autosaves past their expiry.
5. `inject_styles()` + `enable_global_spellcheck()`.
6. `sync_description_state()` — reconcile the rich-text editor's value (GOTCHAS).
7. `sidebar_nav()` → returns the chosen `page` name.
8. `_maybe_restore_saved_work()` — offer/auto-restore the user's autosave.
9. `PAGE_RENDERERS[page]()` — render the chosen screen.
10. `worksave.autosave_tick()` — persist changes if anything changed.

`PAGE_RENDERERS` (in `app.py`) is the routing table mapping a page name to its
`render()` function.

## The main user flows

### Create flow
`Upload` → `services/workbook_io.read_queue_workbook()` parses the Excel and
canonicalises headers → `state.set_batch()` seeds `queue_df` + `items` →
`Work Queue` (`pages/queue.py`) lists SKUs → **Open** a SKU →
`SKU Workspace` (`pages/workspace.py`), which shows tabs:
- **Content** — embeds `general` + `description` + features + highlights,
- **Specs** — `pages/specs.py`,
- **Var Opts** — `pages/var_opts.py` (only for parents with children),
- **Review** — `pages/preview_export.py` (preview + export + submit).

### Export
`services/export.py` builds the sheets and `excel_bytes()` writes a 5-sheet
workbook:

| Sheet | Builder | Contents |
|---|---|---|
| `Input` | `build_input_sheet_df` | Frozen snapshot of the uploaded batch — **includes children** |
| `-Item Processed Details-` | `build_output_df` | The filled content rows — **parents/standalones only** |
| `Video Links` | `build_video_links_df` | Per-SKU video links |
| `Warranty` | `build_warranty_export_df` | Warranty rows matched to the master list |
| `Variant Options` | `variants.build_variant_df` | Flattened Var Opts |

`text_bytes()` produces the tab-separated Notepad export (stops at Value5).

### Review flow (the reverse)
`pages/review.py` uploads one or more exported files →
`export.parse_output_excel()` reverses each workbook back into
`(queue_df, items, variants)` → merged into one batch → the same Workspace UI,
restricted to the Review tab.

## Where to look for X

| I want to change… | Look in |
|---|---|
| A validation/required-field rule | `services/validation.py` |
| The text-cleaning ("Format") behaviour | `services/text_rules.py` |
| Excel export or re-import | `services/export.py` |
| Parent/child logic | `services/relationships.py`, `services/workbook_io.py` |
| Variant options | `services/variants.py`, `pages/var_opts.py` |
| Category → spec prefill | `services/category_mapping.py` |
| Autosave / restore | `services/worksave.py`, `app._maybe_restore_saved_work` |
| The rich-text description editor | `ui/editor.py` + `ui/html_editor_component/` |
| A data grid (features/includes/specs) | `ui/grid.py` (`stable_data_editor`) |
| Navigation / tabs / header | `ui/layout.py` |
