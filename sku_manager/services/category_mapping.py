from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st


TAXONOMY_SEPARATOR = ">>"

_COL_PATH = "Taxonomy Path"
_COL_V1 = "Value1 (Category)"
_COL_V3 = "Value3 (Group)"
_COL_V4 = "Value4 (Spec)"

MAPPING_COLUMNS = [_COL_PATH, _COL_V1, _COL_V3, _COL_V4]
TEMPLATE_COLUMNS = [_COL_V1, _COL_V3, _COL_V4]

# Header aliases accepted from uploaded sheets (matched case-insensitively).
_MAPPING_HEADER_ALIASES = {
    "taxo": _COL_PATH,
    "taxonomy": _COL_PATH,
    "taxonomy path": _COL_PATH,
    "path": _COL_PATH,
    "v1": _COL_V1,
    "value1": _COL_V1,
    "value1 (category)": _COL_V1,
    "category": _COL_V1,
    "v3": _COL_V3,
    "value3": _COL_V3,
    "value3 (group)": _COL_V3,
    "group": _COL_V3,
    "v4": _COL_V4,
    "value4": _COL_V4,
    "value4 (spec)": _COL_V4,
    "spec": _COL_V4,
}


def _mapping_df() -> pd.DataFrame:
    df = st.session_state.get("category_mapping_df")
    if df is None or _COL_PATH not in getattr(df, "columns", []):
        return pd.DataFrame(columns=[_COL_PATH, _COL_V1, _COL_V3, _COL_V4])
    return df


def taxonomy_parts(path: str) -> list[str]:
    return [part.strip() for part in str(path or "").split(TAXONOMY_SEPARATOR) if part.strip()]


def leaf_name(path: str) -> str:
    parts = taxonomy_parts(path)
    return parts[-1] if parts else ""


def display_path(path: str) -> str:
    return " > ".join(taxonomy_parts(path))


def category_paths() -> list[str]:
    """Unique taxonomy paths from the mapping table, sorted by leaf name."""
    ordered: list[str] = []
    seen: set[str] = set()
    for value in _mapping_df()[_COL_PATH].tolist():
        path = str(value or "").strip()
        if path and path not in seen:
            ordered.append(path)
            seen.add(path)
    return sorted(ordered, key=lambda path: leaf_name(path).lower())


def category_labels(paths: list[str]) -> dict[str, str]:
    """Dropdown labels: the taxonomy leaf, plus the parent when two leaves collide."""
    leaf_counts = Counter(leaf_name(path).lower() for path in paths)
    labels: dict[str, str] = {}
    for path in paths:
        parts = taxonomy_parts(path)
        leaf = parts[-1] if parts else ""
        if leaf_counts[leaf.lower()] > 1 and len(parts) > 1:
            labels[path] = f"{leaf} ({parts[-2]})"
        else:
            labels[path] = leaf
    return labels


def template_rows(path: str) -> list[dict]:
    """Predefined spec rows for a category, in mapping-table order, with Value5 empty."""
    target = str(path or "").strip()
    if not target:
        return []
    rows: list[dict] = []
    for _, row in _mapping_df().iterrows():
        if str(row.get(_COL_PATH, "") or "").strip() != target:
            continue
        group = str(row.get(_COL_V3, "") or "").strip()
        spec = str(row.get(_COL_V4, "") or "").strip()
        if not group and not spec:
            continue
        rows.append(
            {
                "category": str(row.get(_COL_V1, "") or "").strip(),
                "group": group,
                "Spec": spec,
                "Value": "",
            }
        )
    return rows


def merge_template_into_specs(specs: list[dict], path: str) -> int:
    """Append the category's template rows that are not already in the specs list.

    Existing rows (and their values) are never touched; returns how many rows were added.
    """
    added = 0
    for template in template_rows(path):
        if _template_row_present(specs, template):
            continue
        specs.append(dict(template))
        added += 1
    return added


def normalize_mapping_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Rename aliased headers, keep the four mapping columns, strip cell whitespace."""
    rename_map = {}
    for column in df.columns:
        alias = _MAPPING_HEADER_ALIASES.get(str(column).strip().lower())
        if alias and alias not in rename_map.values():
            rename_map[column] = alias
    out = df.rename(columns=rename_map)
    out = out.loc[:, ~out.columns.duplicated()]
    for column in MAPPING_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out = out[MAPPING_COLUMNS].fillna("").astype(str)
    for column in MAPPING_COLUMNS:
        out[column] = out[column].str.strip()
    # A row is meaningful only with a taxonomy and at least a group or spec.
    keep = (out[_COL_PATH] != "") & ((out[_COL_V3] != "") | (out[_COL_V4] != ""))
    return out[keep].reset_index(drop=True)


def split_by_taxonomy(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """(path, template-rows) pairs in first-appearance order; path column dropped."""
    sections: list[tuple[str, pd.DataFrame]] = []
    if df is None or df.empty or _COL_PATH not in df.columns:
        return sections
    for path in df[_COL_PATH].astype(str).str.strip():
        if path and all(path != existing for existing, _ in sections):
            sections.append((path, pd.DataFrame()))
    resolved = []
    for path, _ in sections:
        mask = df[_COL_PATH].astype(str).str.strip() == path
        resolved.append((path, df.loc[mask, TEMPLATE_COLUMNS].reset_index(drop=True)))
    return resolved


def replace_taxonomy_rows(df: pd.DataFrame, path: str, template_df: pd.DataFrame) -> pd.DataFrame:
    """Replace one taxonomy's rows in the flat mapping table, keeping section order.

    An unknown path is appended as a new section; an empty template removes the section.
    """
    path = str(path or "").strip()
    pieces: list[pd.DataFrame] = []
    replaced = False
    for existing_path, existing_rows in split_by_taxonomy(df):
        source = template_df if existing_path == path else existing_rows
        if existing_path == path:
            replaced = True
        pieces.append(_attach_path(existing_path, source))
    if not replaced:
        pieces.append(_attach_path(path, template_df))
    combined = pd.concat([p for p in pieces if not p.empty], ignore_index=True) if pieces else pd.DataFrame()
    return normalize_mapping_frame(combined if not combined.empty else pd.DataFrame(columns=MAPPING_COLUMNS))


def delete_taxonomy(df: pd.DataFrame, path: str) -> pd.DataFrame:
    return replace_taxonomy_rows(df, path, pd.DataFrame(columns=TEMPLATE_COLUMNS))


def _attach_path(path: str, template_df: pd.DataFrame) -> pd.DataFrame:
    if template_df is None or template_df.empty:
        return pd.DataFrame(columns=MAPPING_COLUMNS)
    out = template_df.copy()
    out[_COL_PATH] = path
    for column in MAPPING_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    return out[MAPPING_COLUMNS]


def merge_mapping_upload(existing: pd.DataFrame, uploaded_frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Merge uploaded sheet frames into the mapping: replace taxonomies present in the
    upload, keep all others. Returns (new_df, added_paths, updated_paths)."""
    normalized_frames = [normalize_mapping_frame(frame) for frame in uploaded_frames]
    incoming = (
        pd.concat(normalized_frames, ignore_index=True)
        if normalized_frames
        else pd.DataFrame(columns=MAPPING_COLUMNS)
    )
    existing_paths = {path for path, _ in split_by_taxonomy(existing)}
    added: list[str] = []
    updated: list[str] = []
    result = existing if existing is not None else pd.DataFrame(columns=MAPPING_COLUMNS)
    for path, template_df in split_by_taxonomy(incoming):
        result = replace_taxonomy_rows(result, path, template_df)
        (updated if path in existing_paths else added).append(path)
    return result, added, updated


def parse_template_lines(text: str) -> pd.DataFrame:
    """Parse pasted 'Group<TAB>Spec' (or 'V1<TAB>Group<TAB>Spec') lines into template rows."""
    rows: list[dict] = []
    for raw in str(text or "").replace("\r", "\n").split("\n"):
        if not raw.strip():
            continue
        cells = [cell.strip() for cell in raw.split("\t")]
        if len(cells) >= 3:
            v1, group, spec = cells[0], cells[1], cells[2]
        elif len(cells) == 2:
            v1, group, spec = "", cells[0], cells[1]
        else:
            v1, group, spec = "", "", cells[0]
        if group or spec:
            rows.append({_COL_V1: v1, _COL_V3: group, _COL_V4: spec})
    return pd.DataFrame(rows, columns=TEMPLATE_COLUMNS)


def _template_row_present(specs: list[dict], template: dict) -> bool:
    t_spec = template["Spec"].lower()
    t_group = template["group"].lower()
    for entry in specs:
        spec = str(entry.get("Spec", "") or "").strip().lower()
        group = str(entry.get("group", "") or "").strip().lower()
        if spec == t_spec and (group == t_group or not group):
            return True
    return False
