from __future__ import annotations

from io import BytesIO

import pandas as pd


VARIANT_COLUMNS = ["PSKU", "CSEQ", "CSKU", "ASEQ", "ATTRIBUTE", "VALUE", "DISCONT"]


def _clean(value) -> str:
    return str(value or "").strip()


def parent_child_groups(queue_df: pd.DataFrame | None) -> list[dict]:
    """Reconstruct each parent SKU and its ordered child SKUs from the queue.

    In the work queue the ATR Type column is relabeled to 'Parent (N)' for a
    parent, '' for its children (which are ordered immediately after the parent),
    and 'Standalone' for everything else. Walk the rows in order, attaching each
    blank-ATR child to the most recent parent.

    Returns an ordered list of
        {"parent_sku", "parent_title", "children": [{"sku", "title"}, ...]}
    keeping only parents that actually have at least one child.
    """
    groups: list[dict] = []
    current: dict | None = None
    if queue_df is None or getattr(queue_df, "empty", True):
        return groups

    for _, row in queue_df.iterrows():
        atr = _clean(row.get("ATR Type", ""))
        sku = _clean(row.get("Item No", ""))
        title = _clean(row.get("Title", ""))
        if not sku:
            continue
        if atr.lower().startswith("parent"):
            current = {"parent_sku": sku, "parent_title": title, "children": []}
            groups.append(current)
        elif atr == "":
            if current is not None:
                current["children"].append({"sku": sku, "title": title})
        else:
            # 'Standalone' (or any other label) closes the current parent group.
            current = None

    return [group for group in groups if group["children"]]


def variant_completeness(queue_df: pd.DataFrame | None, variants: dict) -> tuple[bool, list[str]]:
    """Return (all_complete, problems) across every parent/child in the batch.

    A batch is complete when every parent has at least one attribute and every
    child has a non-empty value for each of the parent's attributes.
    """
    problems: list[str] = []
    groups = parent_child_groups(queue_df)
    if not groups:
        return False, ["No parent SKUs with child variants in this batch."]

    for group in groups:
        psku = group["parent_sku"]
        entry = variants.get(psku, {})
        attributes = [a for a in entry.get("attributes", []) if _clean(a)]
        values = entry.get("values", {})
        if not attributes:
            problems.append(f"{psku}: no attributes defined yet.")
            continue
        for child in group["children"]:
            csku = child["sku"]
            child_values = values.get(csku, {})
            for attr in attributes:
                if not _clean(child_values.get(attr, "")):
                    problems.append(f"{psku} / {csku}: '{attr}' is empty.")

    return (len(problems) == 0), problems


def build_variant_df(queue_df: pd.DataFrame | None, variants: dict) -> pd.DataFrame:
    """Flatten variant options into the PSKU/CSEQ/CSKU/ASEQ/ATTRIBUTE/VALUE rows."""
    rows: list[dict] = []
    for group in parent_child_groups(queue_df):
        psku = group["parent_sku"]
        entry = variants.get(psku, {})
        attributes = [a for a in entry.get("attributes", []) if _clean(a)]
        values = entry.get("values", {})
        cseq = 0
        for child in group["children"]:
            cseq += 10
            csku = child["sku"]
            child_values = values.get(csku, {})
            aseq = 0
            for attr in attributes:
                aseq += 10
                rows.append({
                    "PSKU": psku,
                    "CSEQ": cseq,
                    "CSKU": csku,
                    "ASEQ": aseq,
                    "ATTRIBUTE": attr,
                    "VALUE": _clean(child_values.get(attr, "")),
                    "DISCONT": "",
                })
    return pd.DataFrame(rows, columns=VARIANT_COLUMNS)


def variant_excel_bytes(variant_df: pd.DataFrame) -> bytes:
    """Write the variant rows to a single-sheet Excel workbook."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        sheet_name = "Data"
        variant_df.to_excel(writer, index=False, sheet_name=sheet_name)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        header_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#56667f", "font_color": "#FFFFFF", "border": 1}
        )
        for col_num, column in enumerate(variant_df.columns):
            worksheet.write(0, col_num, column, header_fmt)
            worksheet.set_column(col_num, col_num, 18)
    return buffer.getvalue()
