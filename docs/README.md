# SKU Manager — Developer Documentation

This folder is the project's "second brain": the knowledge needed to understand
and safely change the app, written down so it doesn't live only in one person's
memory.

Start here, then read in this order:

| Doc | Read it when you want to… |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Understand what the app is, how it's laid out, the data model, and what happens on every page load. **Read this first.** |
| [GOTCHAS.md](GOTCHAS.md) | Change existing behaviour without re-triggering old bugs. This is the hard-won stuff — read it before editing any page. |
| [TESTING.md](TESTING.md) | Run the tests, understand what's covered, or add new tests. |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deploy, or understand why saved work can disappear. |

For the *why* behind having tests and CI at all (written for a
non-engineer), see [../REPO_HEALTH_GUIDE.md](../REPO_HEALTH_GUIDE.md).

## The 30-second version

VirtualOps SKU Manager is a **Streamlit** app that replaces a legacy
Excel/VBA workbook for preparing product (SKU) data. A user uploads an Excel
queue of SKUs, edits each one through a set of tabs (title, description,
features, specs, highlights, variant options), and exports a formatted Excel +
text file in the shape the downstream system expects. A separate **Review**
mode re-imports an exported file so a second person can check and correct it.

- **Language/stack:** Python 3.12, Streamlit 1.50, pandas.
- **Entry point:** `streamlit_app.py` → `sku_manager.app.main()`.
- **State:** everything lives in Streamlit **session state** (in memory) plus
  per-user JSON autosaves on disk. There is no database.
- **Run it:** `streamlit run streamlit_app.py`
- **Test it:** `pytest`
