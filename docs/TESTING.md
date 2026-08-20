# Testing

## Run the tests

From the repo root:

```bash
pip install -r requirements.txt -r requirements-dev.txt   # first time only
pytest
```

You should see `110 passed` in ~2 seconds. Every push and pull request also runs
this automatically via GitHub Actions (`.github/workflows/tests.yml`).

## How the suite is organised

Tests live in `tests/`, one file per module under test. Shared setup (small fake
SKUs, a controlled rule table, a parent/child batch builder) lives in
`tests/conftest.py` as pytest fixtures.

| File | Covers | Tests |
|---|---|---:|
| `test_text_rules.py` | The "Format" engine + line/cell parsing | 25 |
| `test_validation.py` | Submit gating + warnings | 22 |
| `test_category_mapping.py` | Taxonomy + spec-template prefill | 15 |
| `test_excel_roundtrip.py` | Export → re-import; HTML sanitizing | 12 |
| `test_variants.py` | Var Opts grouping/completeness/export | 10 |
| `test_relationships.py` | Parent/child role logic | 8 |
| `test_clone.py` | "Similar To" clone | 8 |
| `test_workbook_io.py` | Uploaded-workbook parsing | 6 |
| `test_models.py` | Item-record factory | 4 |

## What is and isn't covered

**Covered (well):** the business-logic core in `services/` — the modules where a
bug means silently wrong data in someone's Excel. Targeted-module line coverage
runs 61–100%.

**Not covered (yet):**
- The **UI layer** (`pages/`, `ui/`) — 0%. Streamlit UI can't be unit-tested; it
  needs a live server. It should be covered by **end-to-end browser tests**
  (Playwright), driving the app like a user. None are committed yet — they've
  only been run ad-hoc.
- `services/worksave.py` (the autosave/load system), `state.py` beyond clone,
  and the smaller support modules (`git_sync`, `metrics`, `rules_store`,
  `html_rules`, `reference_store`). These are logic and *should* have tests;
  `worksave.py` is the highest-priority gap since it controls users' saved work.

To see current numbers:

```bash
pip install coverage
coverage run --source=sku_manager -m pytest -q
coverage report
```

## Writing a new test

1. Prefer testing a **pure function in `services/`**. If the behaviour you want
   to test lives in a page, consider moving the decision into a service first —
   it's easier to test and better structured.
2. Add it to the matching `tests/test_<module>.py`, or create a new one.
3. Reuse fixtures from `conftest.py` (`valid_item`, `rules_df`,
   `parent_child_batch`, `variants_data`) rather than rebuilding data.
4. **One test, one reason to fail.** A test that checks five things gives a vague
   red; five small tests point at the exact break.
5. If the code reads `st.session_state`, set the keys you need at the top of the
   test — the autouse `_clear_session_state` fixture wipes it between tests, so
   there's no cross-contamination.

## The philosophy (short version)

Don't chase 100%. Test the code where a bug is *dangerous and silent* (data
logic) heavily; test cosmetic UI lightly via a few end-to-end journeys. The goal
is confidence to change the app, not a vanity number.
