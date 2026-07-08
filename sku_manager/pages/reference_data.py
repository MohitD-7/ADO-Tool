from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from sku_manager.services.reference_store import (
    REFERENCE_DATA_PATH,
    coerce_uploaded_frame,
    load_reference_data,
    save_reference_data,
)
from sku_manager.ui.components import page_header


TABLES = [
    ("Manufacturers", "manufacturers_df"),
    ("Battery Materials", "battery_materials_df"),
    ("Battery Types", "battery_types_df"),
    ("Special Characters", "special_rules_df"),
    ("Checklist", "checklist_df"),
    ("Warranty Brands", "warranty_df"),
]

# When a table is replaced via file upload, also write it out to this file so the
# checked-in default stays in sync with whatever admins load through the UI.
_SYNCED_SOURCE_FILES = {
    "warranty_df": Path(__file__).resolve().parents[1] / "data" / "warranty_master.tsv",
}


def _sync_source_files(state) -> None:
    """Keep the checked-in default files in lockstep with whatever is live in session state."""
    for state_key, path in _SYNCED_SOURCE_FILES.items():
        df = state.get(state_key)
        if df is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, sep="\t", index=False, encoding="utf-8")


def _read_uploaded_table(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith((".tsv", ".txt")):
        return pd.read_csv(uploaded_file, sep="\t", dtype=str)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file, dtype=str)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file, dtype=str)
    raise ValueError("Unsupported file type. Use .tsv, .csv, .txt, or .xlsx.")


def _configured_password() -> str:
    env_password = os.getenv("SKU_REFERENCE_DATA_PASSWORD", "")
    if env_password:
        return env_password
    try:
        return str(st.secrets.get("reference_data_password", ""))
    except Exception:
        return ""


def _reload_reference_data() -> None:
    for key, value in load_reference_data().items():
        st.session_state[key] = value


def _render_auth_controls() -> bool:
    is_admin = bool(st.session_state.get("reference_data_admin", False))
    password = _configured_password()

    if is_admin:
        c1, c2, c3 = st.columns([1, 1, 3])
        if c1.button("Save Changes", type="primary", width="stretch"):
            save_reference_data(st.session_state)
            _sync_source_files(st.session_state)
            st.success(f"Reference data saved to {REFERENCE_DATA_PATH.name}.")
        if c2.button("Lock Editing", width="stretch"):
            st.session_state["reference_data_admin"] = False
            st.rerun()
        return True

    c1, c2, c3 = st.columns([1.5, 1, 2.5])
    with c1:
        entered = st.text_input("Admin password", type="password", disabled=not bool(password))
    with c2:
        st.write("")
        if st.button("Unlock Editing", width="stretch", disabled=not bool(password)):
            if entered and entered == password:
                st.session_state["reference_data_admin"] = True
                st.rerun()
            st.error("Incorrect admin password.")
    with c3:
        if password:
            st.info("Viewing is open. Editing requires admin unlock.")
        else:
            st.info("Viewing is open. Set SKU_REFERENCE_DATA_PASSWORD or st.secrets['reference_data_password'] to enable editing.")
    return False


def _render_table(label: str, state_key: str, editable: bool) -> None:
    df = st.session_state[state_key]
    st.caption(f"{len(df):,} rows")

    if editable:
        uploaded = st.file_uploader(
            f"Replace {label} from a file (.tsv, .csv, .xlsx)",
            type=["tsv", "csv", "txt", "xlsx", "xls"],
            key=f"{state_key}_upload",
        )
        if uploaded is not None:
            signature = (uploaded.name, uploaded.size)
            sig_key = f"{state_key}_upload_sig"
            if st.session_state.get(sig_key) != signature:
                try:
                    raw_df = _read_uploaded_table(uploaded)
                    coerced_df = coerce_uploaded_frame(raw_df, state_key)
                except Exception as exc:
                    st.error(f"Could not read that file: {exc}")
                else:
                    st.session_state[state_key] = coerced_df
                    st.session_state[sig_key] = signature
                    save_reference_data(st.session_state)
                    _sync_source_files(st.session_state)
                    st.success(f"Loaded {len(coerced_df):,} rows into {label} and saved to {REFERENCE_DATA_PATH.name}.")
                    st.rerun()

        st.session_state[state_key] = st.data_editor(
            df,
            num_rows="dynamic",
            width="stretch",
            key=f"{state_key}_editor",
        )
    else:
        st.dataframe(df, width="stretch", hide_index=True)


def render() -> None:
    page_header("Admin", "Reference Data")
    st.caption("These tables replace the validation/configuration sheets from the legacy workbook.")

    editable = _render_auth_controls()
    if st.button("Reload From Backend", width="stretch"):
        _reload_reference_data()
        st.rerun()

    tab_labels = [label for label, _ in TABLES] + ["HTML Template"]
    tabs = st.tabs(tab_labels)
    for tab, (label, state_key) in zip(tabs, TABLES):
        with tab:
            _render_table(label, state_key, editable)

    with tabs[-1]:
        if editable:
            st.session_state["html_template"] = st.text_area(
                "HTML Template",
                value=st.session_state["html_template"],
                height=520,
            )
        else:
            st.code(st.session_state["html_template"], language="html")
