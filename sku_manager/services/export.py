from __future__ import annotations

from io import BytesIO

import pandas as pd

from sku_manager.config import OUTPUT_COLUMNS, QUEUE_COLUMNS
from sku_manager.models import new_item_record


def _row(field: str, item_no: str, value1: str = "", value2: str = "", value3: str = "", value4: str = "", value5: str = "", comments: str = "", source: str = "", video: str = "") -> dict:
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
        "Video Link": video,
    }


def build_item_rows(item: dict) -> list[dict]:
    details = item["details"]
    item_no = details.get("item_no", "")
    comments = details.get("comments", "")
    rows = [
        _row("Title", item_no, details.get("title", ""), comments=comments),
        _row("Short Title", item_no, details.get("short_title", "")),
        _row("Description", item_no, details.get("description", "")),
        _row("Mfg Model", item_no, details.get("mfg_model", "")),
        _row("Battery Info", item_no, details.get("battery_info", "")),
        _row("Battery Material", item_no, details.get("battery_material", "")),
        _row("Battery Type", item_no, details.get("battery_type", "")),
        _row("Battery Quantity", item_no, details.get("battery_quantity", "")),
    ]

    for index, include in enumerate(item.get("includes", []), start=1):
        text = str(include.get("text", "")).strip()
        sku = str(include.get("sku", "")).strip()
        if not text and not sku:
            continue
        rows.append(_row(
            "Includes",
            item_no,
            value1=str(index * 10),
            value2=text,
            value3=sku,
        ))

    for index, feature in enumerate(item.get("features", []), start=1):
        rows.append(_row("Feature", item_no, str(index * 10), str(feature)))

    for index, spec in enumerate(item.get("specs", []), start=1):
        rows.append(_row(
            "Specification",
            item_no,
            value1=str(spec.get("category", "") or ""),
            value2=str(index * 10),
            value3=str(spec.get("group", "") or ""),
            value4=spec.get("Spec", ""),
            value5=spec.get("Value", ""),
        ))

    for index, highlight in enumerate(item.get("highlights", []), start=1):
        rows.append(_row("Highlight", item_no, str(index * 10), str(highlight), "PDP"))

    shared_links = [
        str(link).strip()
        for link in item.get("links", {}).get("general", [])
        if str(link).strip()
    ]
    for i, link in enumerate(shared_links):
        if i < len(rows):
            rows[i]["Source"] = link
        else:
            rows.append(_row("Link", item_no, source=link))

    return rows


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


def excel_bytes(output_df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        output_df.to_excel(writer, index=False, sheet_name="-Item Processed Details-")
        workbook = writer.book
        worksheet = writer.sheets["-Item Processed Details-"]
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#56667f", "font_color": "#FFFFFF", "border": 1})
        for col_num, column in enumerate(output_df.columns):
            worksheet.write(0, col_num, column, header_fmt)
            width = min(max(12, int(output_df[column].astype(str).str.len().max() if not output_df.empty else 12) + 2), 55)
            worksheet.set_column(col_num, col_num, width)
    return buffer.getvalue()


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
    try:
        df = pd.read_excel(file, sheet_name=0, dtype=str).fillna("")
    except Exception as exc:
        raise ValueError(f"Could not read file: {exc}") from exc

    required = {"Field Name", "Item Number"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"Missing columns: {required - set(df.columns)}")

    # Collect ordered item numbers preserving first-seen order
    item_nos = list(dict.fromkeys(
        str(r).strip() for r in df["Item Number"] if str(r).strip()
    ))
    if not item_nos:
        raise ValueError("No item numbers found in the file.")

    items: dict = {ino: new_item_record(item_no=ino) for ino in item_nos}

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

    for _, row in df.iterrows():
        ino   = v(row, "Item Number")
        field = v(row, "Field Name")
        if not ino or ino not in items:
            continue
        item = items[ino]
        det  = item["details"]

        if field in _SIMPLE:
            det[_SIMPLE[field]] = v(row, "Value1")
            if field == "Title":
                det["comments"] = v(row, "Comments")
            source = v(row, "Source")
            if source:
                item.setdefault("links", {}).setdefault("general", [])
                if source not in item["links"]["general"]:
                    item["links"]["general"].append(source)

        elif field == "Link":
            source = v(row, "Source")
            if source:
                item.setdefault("links", {}).setdefault("general", [])
                if source not in item["links"]["general"]:
                    item["links"]["general"].append(source)

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

        elif field == "Feature":
            text = v(row, "Value2")
            if text:
                item["features"].append(text)

        elif field == "Specification":
            category = v(row, "Value1")
            group    = v(row, "Value3")
            key      = v(row, "Value4")
            val      = v(row, "Value5")
            if key or val or category or group:
                item["specs"].append({
                    "category": category,
                    "group":    group,
                    "Spec":     key,
                    "Value":    val,
                })

        elif field == "Highlight":
            text = v(row, "Value2")
            if text:
                item["highlights"].append(text)

        source = v(row, "Source")
        if source and field in ("Feature", "Specification", "Highlight", "Includes"):
            item.setdefault("links", {}).setdefault("general", [])
            if source not in item["links"]["general"]:
                item["links"]["general"].append(source)

    # Build a minimal queue_df from the parsed items
    queue_rows = [
        {
            "Item No":  ino,
            "Title":    items[ino]["details"].get("title", ""),
            "Mfg Item": items[ino]["details"].get("mfg_item", ""),
            "Status":   "",
            "Done By":  "",
        }
        for ino in item_nos
    ]
    queue_df = pd.DataFrame(queue_rows, columns=QUEUE_COLUMNS)
    return queue_df, items


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
        include_rows.append(f"<tr><td>{order}</td><td>{value}</td></tr>")
    includes = "".join(include_rows)
    features = "".join(f"<tr><td>{idx * 10}</td><td>{feature}</td></tr>" for idx, feature in enumerate(item.get("features", []), start=1))
    specs = "".join(
        f"<tr><td>{idx * 10}</td><td></td><td></td><td>{spec.get('Spec', '')}</td><td>{spec.get('Value', '')}</td></tr>"
        for idx, spec in enumerate(item.get("specs", []), start=1)
    )
    highlights = "".join(f"<li>{highlight}</li>" for highlight in item.get("highlights", []))
    battery = "".join(
        [
            f"<tr><td>Battery Info</td><td>{details.get('battery_info', '')}</td></tr>",
            f"<tr><td>Battery Material</td><td>{details.get('battery_material', '')}</td></tr>",
            f"<tr><td>Battery Type</td><td>{details.get('battery_type', '')}</td></tr>",
            f"<tr><td>Battery Quantity</td><td>{details.get('battery_quantity', '')}</td></tr>",
        ]
    )
    replacements = {
        "--Title--": details.get("title", ""),
        "--ShortTitle--": details.get("short_title", ""),
        "--ItemNo--": details.get("item_no", ""),
        "--MfgItem--": details.get("mfg_item", ""),
        "--MfgModel--": details.get("mfg_model", ""),
        "--Description--": details.get("description", ""),
        "--Includes--": includes,
        "--Features--": features,
        "--Specifications--": specs,
        "--Highlights--": highlights,
        "--Warranty Months--": details.get("warranty_months", ""),
        "--Battery Info--": battery,
    }
    html = template
    for old, new in replacements.items():
        html = html.replace(old, str(new))
    return html
