from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from io import BytesIO

import pandas as pd

from sku_manager.config import INPUT_SHEET_COLUMNS, OUTPUT_COLUMNS, QUEUE_COLUMNS
from sku_manager.models import new_item_record


def _row(field: str, item_no: str, value1="", value2="", value3="", value4="", value5="", comments: str = "", source: str = "") -> dict:
    return {
        "": "",
        "Field Name": field,
        "Item Number": item_no,
        "Value1": value1,
        "Value2": value2,
        "Value3": value3,
        "Value4": value4,
        "Value5": value5,
        "Comments": comments,
        "Source": source,
    }


def _line_list(value) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").splitlines()
    return [str(line).strip() for line in raw if str(line).strip()]


def _field_comment(item: dict, field_key: str, fallback: str = "") -> str:
    comments = item.get("comments", {})
    value = comments.get(field_key, "") if isinstance(comments, dict) else ""
    return str(value).strip() or str(fallback or "").strip()


def _common_sources(item: dict) -> list[str]:
    return _line_list(item.get("links", {}).get("general", []))


def _video_links(item: dict) -> list[str]:
    return _line_list(item.get("details", {}).get("video_link", ""))


def _video_link_id(video_link: str) -> str:
    text = str(video_link).strip().rstrip("/")
    if not text:
        return ""
    tail = text.rsplit("/", 1)[-1]
    return tail.split("?", 1)[0].split("#", 1)[0]


def build_item_rows(item: dict) -> list[dict]:
    details = item["details"]
    item_no = details.get("item_no", "")
    rows = [
        _row(
            "Title",
            item_no,
            details.get("title", ""),
            comments=_field_comment(item, "title", details.get("comments", "")),
        ),
        _row("Short Title", item_no, details.get("short_title", "")),
        _row(
            "Description",
            item_no,
            details.get("description", ""),
            comments=_field_comment(item, "description"),
        ),
    ]

    for index, include in enumerate(item.get("includes", []), start=1):
        text = str(include.get("text", "")).strip()
        sku = str(include.get("sku", "")).strip()
        if not text and not sku:
            continue
        rows.append(_row(
            "Includes",
            item_no,
            value1=index * 10,
            value2=text,
            value3=sku,
            comments=_field_comment(item, "includes") if index == 1 else "",
        ))

    battery_info = details.get("battery_info", "")
    no_battery = str(battery_info).strip().lower() == "no battery used"
    battery_material = "" if no_battery else details.get("battery_material", "")
    battery_type = "" if no_battery else details.get("battery_type", "")
    battery_quantity = "" if no_battery else details.get("battery_quantity", "")

    rows.extend([
        _row("Mfg Model", item_no, details.get("mfg_model", "")),
        _row("Battery Info", item_no, battery_info),
        _row("Battery Material", item_no, battery_material),
        _row("Battery Type", item_no, battery_type),
        _row("Battery Quantity", item_no, battery_quantity),
    ])

    for index, feature in enumerate(item.get("features", []), start=1):
        rows.append(_row(
            "Feature",
            item_no,
            index * 10,
            str(feature),
            comments=_field_comment(item, "features") if index == 1 else "",
        ))

    for index, spec in enumerate(item.get("specs", []), start=1):
        rows.append(_row(
            "Specification",
            item_no,
            value1=str(spec.get("category", "") or ""),
            value2=index * 10,
            value3=str(spec.get("group", "") or ""),
            value4=spec.get("Spec", ""),
            value5=spec.get("Value", ""),
            comments=_field_comment(item, "specs") if index == 1 else "",
        ))

    for index, highlight in enumerate(item.get("highlights", []), start=1):
        rows.append(_row(
            "Highlight",
            item_no,
            index * 10,
            str(highlight),
            "PDP",
            comments=_field_comment(item, "highlights") if index == 1 else "",
        ))

    for index, source in enumerate(_common_sources(item)):
        if index < len(rows):
            rows[index]["Source"] = source
        else:
            rows.append(_row("Link", item_no, source=source))

    return rows


def build_video_links_df(queue_df: pd.DataFrame, items: dict) -> pd.DataFrame:
    columns = ["Item Number", "Links", "Source", "Video Links"]
    rows = []
    for _, queue_row in queue_df.iterrows():
        item_no = str(queue_row["Item No"])
        item = items.get(item_no)
        if not item:
            continue
        for video_link in _video_links(item):
            rows.append({
                "Item Number": item_no,
                "Links": _video_link_id(video_link),
                "Source": "YouTube",
                "Video Links": video_link,
            })
    return pd.DataFrame(rows, columns=columns)

def first_link(item: dict, group: str) -> str:
    links = item.get("links", {}).get(group, [])
    return next((link for link in links if str(link).strip()), "")


def build_output_df(queue_df: pd.DataFrame, items: dict) -> pd.DataFrame:
    rows = []
    for _, queue_row in queue_df.iterrows():
        item_no = str(queue_row["Item No"])
        item = items.get(item_no)
        if item:
            rows.extend(build_item_rows(item))
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)



def _input_atr_value(value: str) -> str:
    text = str(value or "").strip()
    return "" if text.lower().startswith("child of ") else text

def build_input_sheet_df(queue_df: pd.DataFrame, items: dict | None = None) -> pd.DataFrame:
    """Frozen snapshot of the original input/workspace sheet.

    ATR and JIRA are queue metadata. Title and Mfg Item remain the original
    uploaded values even if the editable SKU title is changed later.
    """
    rows = []
    for _, queue_row in queue_df.iterrows():
        item_no = str(queue_row["Item No"])
        item_details = items.get(item_no, {}).get("details", {}) if items else {}
        has_atr_column = "ATR Type" in queue_df.columns
        atr_type = _input_atr_value(queue_row.get("ATR Type", "")) if has_atr_column else ""
        if not atr_type and item_details:
            atr_type = _input_atr_value(item_details.get("atr_type", ""))
        rows.append({
            "ATR Type": atr_type if has_atr_column else (atr_type or "Standalone"),
            "JIRA": str(queue_row.get("JIRA", "") or item_details.get("jira", "")),
            "Item No": item_no,
            "Title": str(queue_row.get("Title", "") or item_details.get("input_title", "") or item_details.get("title", "")),
            "Mfg Item": str(queue_row.get("Mfg Item", "") or item_details.get("input_mfg_item", "") or item_details.get("mfg_item", "")),
        })
    return pd.DataFrame(rows, columns=INPUT_SHEET_COLUMNS)
def _coerce_order_values(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    if sheet_name != "-Item Processed Details-" or df.empty or "Field Name" not in df.columns:
        return df
    out = df.copy()

    def order_number(value):
        text = str(value).strip()
        return int(text) if text.isdigit() else value

    if "Value1" in out.columns:
        mask = out["Field Name"].isin(["Includes", "Feature", "Highlight"])
        out.loc[mask, "Value1"] = out.loc[mask, "Value1"].map(order_number)
    if "Value2" in out.columns:
        mask = out["Field Name"].eq("Specification")
        out.loc[mask, "Value2"] = out.loc[mask, "Value2"].map(order_number)
    return out


def _write_sheet(writer, df: pd.DataFrame, sheet_name: str) -> None:
    df_to_write = _coerce_order_values(df, sheet_name)
    df_to_write.to_excel(writer, index=False, sheet_name=sheet_name)
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#56667f", "font_color": "#FFFFFF", "border": 1})
    for col_num, column in enumerate(df_to_write.columns):
        worksheet.write(0, col_num, column, header_fmt)
        worksheet.set_column(col_num, col_num, 20)


def excel_bytes(
    output_df: pd.DataFrame,
    input_df: pd.DataFrame | None = None,
    video_links_df: pd.DataFrame | None = None,
    warranty_df: pd.DataFrame | None = None,
) -> bytes:
    buffer = BytesIO()
    if video_links_df is None:
        video_links_df = pd.DataFrame(columns=["Item Number", "Links", "Source", "Video Links"])
    if warranty_df is None:
        warranty_df = pd.DataFrame(columns=[
            "SKU", "SKIP_Y_N", "MFG_CODE", "DESCR", "MO_PARTS", "MO_LABOR",
            "URL", "INT_PREFIX", "PHONE#", "EXTENSION", "DISCONT"
        ])
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        if input_df is not None:
            _write_sheet(writer, input_df, "Input")
        _write_sheet(writer, output_df, "-Item Processed Details-")
        _write_sheet(writer, video_links_df, "Video Links")
        _write_sheet(writer, warranty_df, "Warranty")
    return buffer.getvalue()


# Text export keeps only the field/value columns (through Value5); the trailing
# Comments and Source columns are dropped.
TEXT_COLUMNS = ["", "Field Name", "Item Number", "Value1", "Value2", "Value3", "Value4", "Value5"]


def text_bytes(output_df: pd.DataFrame) -> bytes:
    """Tab-separated Notepad-friendly export of the filled output sheet.

    Includes the empty leading column but stops at Value5 — Comments, Source,
    and Source are omitted.
    """
    columns = [col for col in TEXT_COLUMNS if col in output_df.columns]
    return output_df[columns].to_csv(index=False, sep="\t").encode("utf-8-sig")


def parse_output_excel(file) -> tuple[pd.DataFrame, dict]:
    """
    Reverse-parse an output Excel (produced by export_excel) back into
    a (queue_df, items) pair that the workspace can load directly.

    Field Name mapping:
      Title, Short Title, Includes, Description,
      Manufacturer (AD Filters), Warranty Months, Mfg Model,
      Battery Info, Battery Material, Battery Type, Battery Quantity,
      Feature (Value1=order, Value2=text),
      Specification (Value2=order, Value4=key, Value5=value),
      Highlight (Value1=order, Value2=text)
    """
    required = {"Field Name", "Item Number"}
    try:
        sheets = pd.read_excel(file, sheet_name=None, dtype=str)
    except Exception as exc:
        raise ValueError(f"Could not read file: {exc}") from exc

    # Prefer the named field/output sheet; fall back to the first sheet that
    # carries the required columns (Input sheet is now first in the workbook).
    df = sheets.get("-Item Processed Details-")
    if df is None or not required.issubset(set(df.columns)):
        df = next(
            (s for s in sheets.values() if required.issubset(set(s.columns))),
            None,
        )
    if df is None:
        df = next(iter(sheets.values()), pd.DataFrame())
    df = df.fillna("")

    if not required.issubset(set(df.columns)):
        raise ValueError(f"Missing columns: {required - set(df.columns)}")

    def input_queue_snapshot() -> tuple[list[str], dict[str, dict[str, str]]]:
        input_sheet = sheets.get("Input")
        if input_sheet is None or input_sheet.empty:
            return [], {}
        input_sheet = input_sheet.fillna("")
        columns_by_key = {str(col).strip().lower(): col for col in input_sheet.columns}

        def col(*names: str):
            for name in names:
                found = columns_by_key.get(name)
                if found is not None:
                    return found
            return None

        item_col = col("item no", "item number", "item#", "item #", "sku")
        if item_col is None:
            return [], {}
        atr_col = col("atr type", "atr", "relationship")
        jira_col = col("jira", "jira #", "jira#", "jira no", "jira number")
        title_col = col("title", "product title")
        mfg_col = col("mfg item", "mfgitem", "mfgitem#", "mfgitem #", "manufacturer item", "mfr item")
        order: list[str] = []
        snapshot: dict[str, dict[str, str]] = {}
        for _, input_row in input_sheet.iterrows():
            ino = str(input_row.get(item_col, "")).strip()
            if not ino:
                continue
            if ino not in snapshot:
                order.append(ino)
            snapshot[ino] = {
                "ATR Type": _input_atr_value(input_row.get(atr_col, "")) if atr_col is not None else "Standalone",
                "JIRA": str(input_row.get(jira_col, "")).strip() if jira_col is not None else "",
                "Title": str(input_row.get(title_col, "")).strip() if title_col is not None else "",
                "Mfg Item": str(input_row.get(mfg_col, "")).strip() if mfg_col is not None else "",
            }
        return order, snapshot
    input_order, input_snapshot = input_queue_snapshot()

    # Collect ordered item numbers preserving first-seen order from the output
    # sheet, but prefer the Input sheet order when it is present.
    processed_item_nos = list(dict.fromkeys(
        str(r).strip() for r in df["Item Number"] if str(r).strip()
    ))
    if input_order:
        item_nos = [ino for ino in input_order if ino in processed_item_nos]
        item_nos.extend(ino for ino in processed_item_nos if ino not in item_nos)
    else:
        item_nos = processed_item_nos
    if not item_nos:
        raise ValueError("No item numbers found in the file.")

    items: dict = {
        ino: new_item_record(
            item_no=ino,
            title=input_snapshot.get(ino, {}).get("Title", ""),
            mfg_item=input_snapshot.get(ino, {}).get("Mfg Item", ""),
            atr_type=input_snapshot.get(ino, {}).get("ATR Type", "Standalone") if ino in input_snapshot else "Standalone",
            jira=input_snapshot.get(ino, {}).get("JIRA", ""),
        )
        for ino in item_nos
    }

    _SIMPLE = {
        "Title":            "title",
        "Short Title":      "short_title",
        "Description":      "description",
        "Mfg Model":        "mfg_model",
        "Battery Info":     "battery_info",
        "Battery Material": "battery_material",
        "Battery Type":     "battery_type",
        "Battery Quantity": "battery_quantity",
    }

    def v(row, col):
        return str(row.get(col, "")).strip()

    def append_unique(values: list[str], new_values: list[str]) -> list[str]:
        for value in new_values:
            if value and value not in values:
                values.append(value)
        return values

    def save_common_media(item: dict, row) -> None:
        source = v(row, "Source")
        if source:
            links = item.setdefault("links", {}).setdefault("general", [])
            item["links"]["general"] = append_unique(links, _line_list(source))
        video = v(row, "Video Link")
        if video:
            existing = _line_list(item.setdefault("details", {}).get("video_link", ""))
            item["details"]["video_link"] = "\n".join(append_unique(existing, _line_list(video)))

    def save_field_note(item: dict, row, field_key: str) -> None:
        comment = v(row, "Comments")
        if comment:
            comments = item.setdefault("comments", {})
            if not str(comments.get(field_key, "")).strip():
                comments[field_key] = comment

    for _, row in df.iterrows():
        ino = v(row, "Item Number")
        field = v(row, "Field Name")
        if not ino or ino not in items:
            continue
        item = items[ino]
        det = item["details"]
        save_common_media(item, row)

        if field in _SIMPLE:
            field_key = _SIMPLE[field]
            det[field_key] = v(row, "Value1")
            if field == "Title":
                det["comments"] = v(row, "Comments")
            save_field_note(item, row, field_key)

        elif field == "Link":
            source = v(row, "Source")
            if source:
                links = item.setdefault("links", {}).setdefault("general", [])
                item["links"]["general"] = append_unique(links, _line_list(source))

        elif field == "Includes":
            text = v(row, "Value2")
            sku = v(row, "Value3")
            legacy = v(row, "Value1")
            if text or sku:
                if text and sku:
                    sku = ""
                item["includes"].append({"text": text, "sku": sku})
            elif legacy:
                for part in [p.strip() for p in legacy.split(" - ") if p.strip()]:
                    item["includes"].append({"text": part, "sku": ""})
            save_field_note(item, row, "includes")

        elif field == "Feature":
            text = v(row, "Value2")
            if text:
                item["features"].append(text)
            save_field_note(item, row, "features")

        elif field == "Specification":
            category = v(row, "Value1")
            group = v(row, "Value3")
            key = v(row, "Value4")
            val = v(row, "Value5")
            if key or val or category or group:
                item["specs"].append({
                    "category": category,
                    "group": group,
                    "Spec": key,
                    "Value": val,
                })
            save_field_note(item, row, "specs")

        elif field == "Highlight":
            text = v(row, "Value2")
            if text:
                item["highlights"].append(text)
            save_field_note(item, row, "highlights")

    video_df = sheets.get("Video Links")
    if video_df is not None and {"Item Number", "Video Links"}.issubset(set(video_df.columns)):
        video_df = video_df.fillna("")
        for _, row in video_df.iterrows():
            ino = str(row.get("Item Number", "")).strip()
            video = str(row.get("Video Links", "")).strip()
            if ino and video and ino in items:
                existing = _line_list(items[ino]["details"].get("video_link", ""))
                items[ino]["details"]["video_link"] = "\n".join(append_unique(existing, _line_list(video)))

    warranty_df = sheets.get("Warranty")
    if warranty_df is not None and {"SKU", "MFG_CODE"}.issubset(set(warranty_df.columns)):
        warranty_df = warranty_df.fillna("")
        warranty_master = load_warranty_data()
        for _, row in warranty_df.iterrows():
            ino = str(row.get("SKU", "")).strip()
            if ino and ino in items:
                mfg_code = str(row.get("MFG_CODE", "")).strip()
                descr = str(row.get("DESCR", "")).strip()
                months = str(row.get("MO_PARTS", "")).strip()
                
                brand = ""
                if not warranty_master.empty:
                    conditions = []
                    if mfg_code:
                        conditions.append(warranty_master["Mfg Code"].astype(str).str.strip().str.lower() == mfg_code.lower())
                    if descr:
                        conditions.append(warranty_master["Warranty Description"].astype(str).str.strip().str.lower() == descr.lower())
                    
                    matched = pd.DataFrame()
                    if len(conditions) == 2:
                        matched = warranty_master[conditions[0] & conditions[1]]
                    if matched.empty and mfg_code:
                        matched = warranty_master[warranty_master["Mfg Code"].astype(str).str.strip().str.lower() == mfg_code.lower()]
                    if matched.empty and descr:
                        matched = warranty_master[warranty_master["Warranty Description"].astype(str).str.strip().str.lower() == descr.lower()]
                    
                    if not matched.empty:
                        brand = str(matched.iloc[0].get("Brand Name", "")).strip()
                
                items[ino]["details"]["warranty_brand"] = brand
                items[ino]["details"]["warranty_months"] = months
    # Build a minimal queue_df from the parsed items
    queue_rows = [
        {
            "ATR Type": _input_atr_value(items[ino]["details"].get("atr_type", "")),
            "JIRA": items[ino]["details"].get("jira", ""),
            "Item No":  ino,
            "Title":    items[ino]["details"].get("input_title", "") or items[ino]["details"].get("title", ""),
            "Mfg Item": items[ino]["details"].get("input_mfg_item", "") or items[ino]["details"].get("mfg_item", ""),
            "Status":   "",
        }
        for ino in item_nos
    ]
    queue_df = pd.DataFrame(queue_rows, columns=QUEUE_COLUMNS)
    return queue_df, items


def load_warranty_data(warranty_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Load warranty data from session state or provided DataFrame.

    Warranty data is stored in reference_data.json and cached in session state.
    Creates a lowercase brand index for case-insensitive lookups.
    """
    import streamlit as st
    if warranty_df is not None:
        df = warranty_df.copy()
    else:
        try:
            df = st.session_state.get("warranty_df", pd.DataFrame()).copy()
        except Exception:
            df = pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    df = df.fillna("")
    if "Brand Name" in df.columns:
        df["brand_lower"] = df["Brand Name"].str.lower()
    return df


def _numeric_cell(value, *, digits_only: bool = False, blank_as_zero: bool = False):
    text = str(value or "").strip()
    if digits_only:
        text = "".join(ch for ch in text if ch.isdigit())
    if not text:
        return 0 if blank_as_zero else ""
    number = pd.to_numeric(text, errors="coerce")
    if pd.isna(number):
        return 0 if blank_as_zero else ""
    as_float = float(number)
    return int(as_float) if as_float.is_integer() else as_float


def _prepare_warranty_export_df(warranty_df: pd.DataFrame) -> pd.DataFrame:
    out = warranty_df.copy()
    for column in ["PHONE#", "Phone#"]:
        if column in out.columns:
            out[column] = out[column].map(lambda value: _numeric_cell(value, digits_only=True))
    for column in ["MO_PARTS", "Mo_Parts"]:
        if column in out.columns:
            out[column] = out[column].map(_numeric_cell)
    for column in ["MO_LABOR", "MO_LABOUR", "Mo_Labor", "Mo_Labour"]:
        if column in out.columns:
            out[column] = out[column].map(lambda value: _numeric_cell(value, blank_as_zero=True))
    return out


def build_warranty_export_df(queue_df: pd.DataFrame, items: dict, warranty_master: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build a DataFrame representing the Warranty sheet with the same details as the warranty download file."""
    if warranty_master is None:
        warranty_master = load_warranty_data()

    warranty_rows = []
    for _, queue_row in queue_df.iterrows():
        item_no = str(queue_row.get("Item No", "")).strip()
        if not item_no or item_no not in items:
            continue
        item = items[item_no]
        brand = item["details"].get("warranty_brand", "").strip()
        months = item["details"].get("warranty_months", "").strip()
        if brand:
            warranty_rows.append((item_no, brand, months))

    warranty_data = []
    for item_no, brand, months in warranty_rows:
        if warranty_master is not None and not warranty_master.empty:
            brand_lower = brand.lower()
            matched = warranty_master[warranty_master["Brand Name"].str.lower() == brand_lower]
            if not matched.empty:
                match = matched.iloc[0]
                warranty_data.append({
                    "SKU": item_no,
                    "SKIP_Y_N": "N",
                    "MFG_CODE": match.get("Mfg Code", ""),
                    "DESCR": match.get("Warranty Description", ""),
                    "MO_PARTS": months,
                    "MO_LABOR": 0,
                    "URL": match.get("Warranty URL", ""),
                    "INT_PREFIX": "",
                    "PHONE#": match.get("Warranty Tel#", ""),
                    "EXTENSION": "",
                    "DISCONT": "",
                })

    columns = [
        "SKU", "SKIP_Y_N", "MFG_CODE", "DESCR", "MO_PARTS", "MO_LABOR",
        "URL", "INT_PREFIX", "PHONE#", "EXTENSION", "DISCONT"
    ]
    if warranty_data:
        df = pd.DataFrame(warranty_data, columns=columns)
    else:
        df = pd.DataFrame(columns=columns)
    return _prepare_warranty_export_df(df)


def warranty_excel_bytes(warranty_df: pd.DataFrame) -> bytes:
    """Generate Excel bytes for warranty data."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        _write_sheet(writer, _prepare_warranty_export_df(warranty_df), "Data")
    return buffer.getvalue()


BATTERY_COLUMNS = ["SKU", "SEQUENCE", "INFO", "MATERIAL", "QUANTITY", "TYPE", "DISCONT"]


def build_battery_df(queue_df: pd.DataFrame, items: dict) -> pd.DataFrame:
    """One row per SKU that actually carries a battery (Battery Info set and not
    'no battery used'), in queue order. SEQUENCE is 10 and DISCONT stays blank."""
    rows: list[dict] = []
    for _, queue_row in queue_df.iterrows():
        item_no = str(queue_row["Item No"]).strip()
        item = items.get(item_no)
        if not item:
            continue
        details = item["details"]
        info = str(details.get("battery_info", "") or "").strip()
        if not info or info.lower() == "no battery used":
            continue
        rows.append({
            "SKU": item_no,
            "SEQUENCE": 10,
            "INFO": info,
            "MATERIAL": str(details.get("battery_material", "") or "").strip(),
            "QUANTITY": str(details.get("battery_quantity", "") or "").strip(),
            "TYPE": str(details.get("battery_type", "") or "").strip(),
            "DISCONT": "",
        })
    return pd.DataFrame(rows, columns=BATTERY_COLUMNS)


def battery_excel_bytes(battery_df: pd.DataFrame) -> bytes:
    """Generate Excel bytes for battery data (single 'Data' sheet)."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        _write_sheet(writer, battery_df, "Data")
    return buffer.getvalue()


_DESCRIPTION_ALLOWED_TAGS = {
    "b",
    "br",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
_DESCRIPTION_DROP_CONTENT_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "svg",
    "math",
    "meta",
    "link",
}
_VOID_TAGS = {"br"}


class _DescriptionSanitizer(HTMLParser):
    """Allow only simple formatting/table tags and text in product descriptions."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if self._drop_depth:
            if tag in _DESCRIPTION_DROP_CONTENT_TAGS:
                self._drop_depth += 1
            return
        if tag in _DESCRIPTION_DROP_CONTENT_TAGS:
            self._drop_depth = 1
            return
        if tag in _DESCRIPTION_ALLOWED_TAGS:
            self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if self._drop_depth:
            return
        if tag in _DESCRIPTION_ALLOWED_TAGS:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._drop_depth:
            if tag in _DESCRIPTION_DROP_CONTENT_TAGS:
                self._drop_depth -= 1
            return
        if tag in _DESCRIPTION_ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._drop_depth:
            self.parts.append(escape(data, quote=True))

    def handle_entityref(self, name: str) -> None:
        if not self._drop_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._drop_depth:
            self.parts.append(f"&#{name};")


def sanitize_description_html(value) -> str:
    sanitizer = _DescriptionSanitizer()
    sanitizer.feed(str(value or ""))
    sanitizer.close()
    return "".join(sanitizer.parts)


def _safe_text(value) -> str:
    return escape(str(value or ""), quote=True)


def render_html(item: dict, template: str) -> str:
    details = item["details"]
    include_rows = []
    order = 0
    for entry in item.get("includes", []):
        text = str(entry.get("text", "")).strip()
        sku = str(entry.get("sku", "")).strip()
        if not text and not sku:
            continue
        order += 10
        value = text if text else f"SKU {sku}"
        include_rows.append(f"<tr><td>{order}</td><td>{_safe_text(value)}</td></tr>")
    includes = "".join(include_rows)
    features = "".join(
        f"<tr><td>{idx * 10}</td><td>{_safe_text(feature)}</td></tr>"
        for idx, feature in enumerate(item.get("features", []), start=1)
    )
    specs = "".join(
        "<tr>"
        f"<td>{_safe_text(spec.get('category', ''))}</td>"
        f"<td>{idx * 10}</td>"
        f"<td>{_safe_text(spec.get('group', ''))}</td>"
        f"<td>{_safe_text(spec.get('Spec', ''))}</td>"
        f"<td>{_safe_text(spec.get('Value', ''))}</td>"
        "</tr>"
        for idx, spec in enumerate(item.get("specs", []), start=1)
    )
    highlights = "".join(f"<li>{_safe_text(highlight)}</li>" for highlight in item.get("highlights", []))
    battery = "".join(
        [
            f"<tr><td>Battery Info</td><td>{_safe_text(details.get('battery_info', ''))}</td></tr>",
            f"<tr><td>Battery Material</td><td>{_safe_text(details.get('battery_material', ''))}</td></tr>",
            f"<tr><td>Battery Type</td><td>{_safe_text(details.get('battery_type', ''))}</td></tr>",
            f"<tr><td>Battery Quantity</td><td>{_safe_text(details.get('battery_quantity', ''))}</td></tr>",
        ]
    )
    replacements = {
        "--Title--": _safe_text(details.get("title", "")),
        "--ShortTitle--": _safe_text(details.get("short_title", "")),
        "--ItemNo--": _safe_text(details.get("item_no", "")),
        "--MfgItem--": _safe_text(details.get("mfg_item", "")),
        "--MfgModel--": _safe_text(details.get("mfg_model", "")),
        "--Description--": sanitize_description_html(details.get("description", "")),
        "--Includes--": includes,
        "--Features--": features,
        "--Specifications--": specs,
        "--Highlights--": highlights,
        "--Warranty Months--": _safe_text(details.get("warranty_months", "")),
        "--Battery Info--": battery,
    }
    html = template
    for old, new in replacements.items():
        html = html.replace(old, str(new))
    return html
