from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from sku_manager.services.category_mapping import (
    delete_taxonomy,
    display_path,
    leaf_name,
    merge_mapping_upload,
    normalize_mapping_frame,
    parse_template_lines,
    replace_taxonomy_rows,
    split_by_taxonomy,
)
from sku_manager.services.git_sync import commit_and_push, is_configured
from sku_manager.services.reference_store import (
    REFERENCE_DATA_PATH,
    coerce_uploaded_frame,
    load_reference_data,
    save_reference_data,
)
from sku_manager.ui.components import page_header
from sku_manager.ui.grid import reset_stable_data_editor, stable_data_editor


TABLES = [
    ("Battery Materials", "battery_materials_df"),
    ("Battery Types", "battery_types_df"),
    ("Special Characters", "special_rules_df"),
    ("Warranty Brands", "warranty_df"),
    ("Category Mapping", "category_mapping_df"),
]

# When a table is replaced via file upload, also write it out to this file so the
# checked-in default stays in sync with whatever admins load through the UI.
_SYNCED_SOURCE_FILES = {
    "warranty_df": Path(__file__).resolve().parents[1] / "data" / "warranty_master.tsv",
    "category_mapping_df": Path(__file__).resolve().parents[1] / "data" / "category_mapping.tsv",
}


def _sync_source_files(state) -> None:
    """Keep the checked-in default files in lockstep with whatever is live in session state."""
    for state_key, path in _SYNCED_SOURCE_FILES.items():
        df = state.get(state_key)
        if df is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, sep="\t", index=False, encoding="utf-8")


def _save_and_push(message: str) -> None:
    """Persist reference data locally, then push to git so the redeploy the deploy
    host does on every code push can never revert this live edit."""
    save_reference_data(st.session_state)
    _sync_source_files(st.session_state)
    paths = [REFERENCE_DATA_PATH] + list(_SYNCED_SOURCE_FILES.values())
    commit_and_push(paths, message)


def _read_uploaded_table(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith((".tsv", ".txt")):
        return pd.read_csv(uploaded_file, sep="\t", dtype=str)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file, dtype=str)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file, dtype=str)
    raise ValueError("Unsupported file type. Use .tsv, .csv, .txt, or .xlsx.")


def admin_password() -> str:
    """The shared admin password (env var wins over Streamlit secrets)."""
    env_password = os.getenv("SKU_REFERENCE_DATA_PASSWORD", "")
    if env_password:
        return env_password
    try:
        return str(st.secrets.get("reference_data_password", ""))
    except Exception:
        return ""


def _configured_password() -> str:
    return admin_password()


def _reload_reference_data() -> None:
    for key, value in load_reference_data().items():
        st.session_state[key] = value


def _render_auth_controls() -> tuple[bool, bool, bool]:
    """Returns (editable, save_requested, push_ack).

    The actual save must happen at the END of render(): the table editors below
    only write their pending edits into session state when they render, so
    saving here would persist the previous state and silently drop the edits.
    """
    is_admin = bool(st.session_state.get("reference_data_admin", False))
    password = _configured_password()

    if is_admin:
        push_ack = True
        if is_configured():
            st.warning(
                "Saving here pushes to GitHub and **redeploys the live app for every user**. "
                "Confirm everyone else has saved or exported their in-progress work before you continue."
            )
            push_ack = st.checkbox(
                "I've confirmed it's safe to push and redeploy now",
                key="reference_data_push_ack",
            )
        c1, c2, c3 = st.columns([1, 1, 3])
        save_requested = c1.button("Save Changes", type="primary", width="stretch", disabled=not push_ack)
        if c2.button("Lock Editing", width="stretch"):
            st.session_state["reference_data_admin"] = False
            st.rerun()
        return True, save_requested, push_ack

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
    return False, False, False


def _render_table(label: str, state_key: str, editable: bool, push_ack: bool) -> None:
    df = st.session_state[state_key]
    st.caption(f"{len(df):,} rows")

    if editable:
        uploaded = st.file_uploader(
            f"Replace {label} from a file (.tsv, .csv, .xlsx)",
            type=["tsv", "csv", "txt", "xlsx", "xls"],
            key=f"{state_key}_upload",
            disabled=not push_ack,
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
                    _save_and_push(f"Auto-sync reference data: replaced {label}")
                    st.success(f"Loaded {len(coerced_df):,} rows into {label} and saved to {REFERENCE_DATA_PATH.name}.")
                    st.rerun()

        st.session_state[state_key] = stable_data_editor(
            df,
            num_rows="dynamic",
            width="stretch",
            key=f"{state_key}_editor",
        )
    else:
        st.dataframe(df, width="stretch", hide_index=True)


def _mapping_section_key(path: str) -> str:
    return hashlib.md5(path.encode("utf-8")).hexdigest()[:10]


def _read_mapping_upload(uploaded_file) -> list[pd.DataFrame]:
    """Read every sheet of an Excel upload (or the single csv/tsv table) as raw frames."""
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls", ".xlsm")):
        sheets = pd.read_excel(uploaded_file, sheet_name=None, dtype=str)
        return [frame.fillna("") for frame in sheets.values()]
    if name.endswith((".tsv", ".txt")):
        return [pd.read_csv(uploaded_file, sep="\t", dtype=str).fillna("")]
    if name.endswith(".csv"):
        return [pd.read_csv(uploaded_file, dtype=str).fillna("")]
    raise ValueError("Unsupported file type. Use .xlsx, .tsv, .csv, or .txt.")


def _save_mapping(df: pd.DataFrame, message: str) -> None:
    st.session_state["category_mapping_df"] = df
    _save_and_push(message)


def _render_category_mapping(editable: bool, push_ack: bool) -> None:
    mapping_df = normalize_mapping_frame(st.session_state["category_mapping_df"])
    sections = split_by_taxonomy(mapping_df)
    st.caption(f"{len(sections)} categor{'y' if len(sections) == 1 else 'ies'}, {len(mapping_df):,} spec rows. Each category below is its own section.")

    message = st.session_state.pop("category_mapping_message", "")
    if message:
        st.success(message)

    if editable:
        uploaded = st.file_uploader(
            "Add or update categories from a file (.xlsx with one sheet per category, or .tsv/.csv). "
            "Categories in the file replace their existing rows; all other categories are kept.",
            type=["xlsx", "xls", "xlsm", "tsv", "csv", "txt"],
            key="category_mapping_upload",
            disabled=not push_ack,
        )
        if uploaded is not None:
            signature = (uploaded.name, uploaded.size)
            if st.session_state.get("category_mapping_upload_sig") != signature:
                try:
                    frames = _read_mapping_upload(uploaded)
                    merged, added, updated = merge_mapping_upload(mapping_df, frames)
                except Exception as exc:
                    st.error(f"Could not read that file: {exc}")
                else:
                    st.session_state["category_mapping_upload_sig"] = signature
                    if not added and not updated:
                        st.warning(
                            "No category rows found in that file. Each sheet needs Taxonomy Path (or Taxo), "
                            "Group (V3), and Spec (V4) columns."
                        )
                    else:
                        _save_mapping(merged, "Auto-sync reference data: category mapping upload")
                        parts = []
                        if added:
                            parts.append("added " + ", ".join(leaf_name(p) for p in added))
                        if updated:
                            parts.append("updated " + ", ".join(leaf_name(p) for p in updated))
                        st.session_state["category_mapping_message"] = f"Category mapping saved: {'; '.join(parts)}."
                        st.rerun()

    for path, template_df in sections:
        section_key = _mapping_section_key(path)
        with st.expander(f"{leaf_name(path)} - {len(template_df)} specs ({display_path(path)})", expanded=False):
            if not editable:
                st.dataframe(template_df, width="stretch", hide_index=True)
                continue
            edited = stable_data_editor(
                template_df,
                num_rows="dynamic",
                width="stretch",
                key=f"category_mapping_section_{section_key}",
                column_config={
                    "Value1 (Category)": st.column_config.TextColumn("Value1 (Category)", width="medium"),
                    "Value3 (Group)": st.column_config.TextColumn("Value3 (Group)", width="medium"),
                    "Value4 (Spec)": st.column_config.TextColumn("Value4 (Spec)", width="large"),
                },
            )
            if not edited.equals(template_df):
                st.session_state["category_mapping_df"] = replace_taxonomy_rows(
                    st.session_state["category_mapping_df"], path, edited
                )
            if st.button(
                "Delete This Category",
                key=f"category_mapping_delete_{section_key}",
                disabled=not push_ack,
            ):
                reset_stable_data_editor(f"category_mapping_section_{section_key}")
                _save_mapping(
                    delete_taxonomy(st.session_state["category_mapping_df"], path),
                    f"Auto-sync reference data: deleted category '{leaf_name(path)}'",
                )
                st.session_state["category_mapping_message"] = f"Deleted category {leaf_name(path)}."
                st.rerun()

    if not editable:
        return

    st.markdown("---")
    st.markdown("#### Add New Category")
    new_path = st.text_input(
        "Taxonomy path (levels separated by > or >>)",
        key="category_mapping_new_path",
        placeholder="e.g. Photography > Cameras > DSLR Cameras",
    )
    new_v1 = st.text_input(
        "Value1 (Category) for its spec rows",
        key="category_mapping_new_v1",
        placeholder="Leave blank to use the last taxonomy level",
    )
    new_rows_text = st.text_area(
        "Spec rows, one per line: Group [TAB] Spec (paste straight from Excel)",
        key="category_mapping_new_rows",
        height=160,
        placeholder="General\tColor\nGeneral\tLoad Capacity\nPhysical Details\tWeight",
    )
    if st.button("Add Category", type="primary", disabled=not push_ack):
        path = new_path.strip()
        template_df = parse_template_lines(new_rows_text)
        if not path:
            st.error("Enter a taxonomy path first.")
        elif template_df.empty:
            st.error("Paste at least one Group/Spec line.")
        elif any(existing == path for existing, _ in sections):
            st.error("That taxonomy already exists below - edit it in its own section instead.")
        else:
            v1 = new_v1.strip() or leaf_name(path)
            template_df["Value1 (Category)"] = template_df["Value1 (Category)"].replace("", v1)
            _save_mapping(
                replace_taxonomy_rows(st.session_state["category_mapping_df"], path, template_df),
                f"Auto-sync reference data: added category '{leaf_name(path)}'",
            )
            st.session_state["category_mapping_message"] = (
                f"Added category {leaf_name(path)} with {len(template_df)} spec row(s)."
            )
            for state_key in ("category_mapping_new_path", "category_mapping_new_v1", "category_mapping_new_rows"):
                st.session_state.pop(state_key, None)
            st.rerun()


def render() -> None:
    page_header("Admin", "Reference Data")
    st.caption("These tables replace the validation/configuration sheets from the legacy workbook.")

    editable, save_requested, push_ack = _render_auth_controls()
    saved_message = st.session_state.pop("reference_data_saved_message", "")
    if saved_message:
        st.success(saved_message)
    if st.button("Reload From Backend", width="stretch"):
        _reload_reference_data()
        st.rerun()

    tab_labels = [label for label, _ in TABLES] + ["HTML Template"]
    tabs = st.tabs(tab_labels)
    for tab, (label, state_key) in zip(tabs, TABLES):
        with tab:
            if state_key == "category_mapping_df":
                _render_category_mapping(editable, push_ack)
            else:
                _render_table(label, state_key, editable, push_ack)

    with tabs[-1]:
        if editable:
            st.session_state["html_template"] = st.text_area(
                "HTML Template",
                value=st.session_state["html_template"],
                height=520,
            )
        else:
            st.code(st.session_state["html_template"], language="html")

    # Save only after every editor above has written its pending edits into
    # session state — saving earlier would persist the pre-edit tables.
    if save_requested:
        _save_and_push("Auto-sync reference data from live admin edit")
        st.session_state["reference_data_saved_message"] = (
            f"Reference data saved to {REFERENCE_DATA_PATH.name}."
        )
        st.rerun()
