from __future__ import annotations

import pandas as pd
import streamlit as st


def default_battery_materials() -> pd.DataFrame:
    # "-" stays first: it is the selectbox placeholder for "no material chosen".
    return pd.DataFrame(
        {
            "Battery Material": [
                "-",
                "alkaline",
                "lead acid",
                "lithium",
                "lithium ion",
                "magnesium",
                "mercury",
                "nickel cadmium",
                "nickel metal hydride",
                "silver oxide",
                "zinc air",
                "zinc carbon",
                "zinc chloride",
            ]
        }
    )


def default_battery_types() -> pd.DataFrame:
    # "-" stays first: it is the selectbox placeholder for "no type chosen".
    return pd.DataFrame(
        {
            "Battery Type": [
                "-",
                "1/3 N",
                "18350",
                "18650",
                "9-volt",
                "A",
                "A10",
                "A13",
                "A23",
                "A312",
                "A675",
                "AA",
                "AAA",
                "AAAA",
                "AG3",
                "AG3/LR41",
                "AG5",
                "C",
                "CR1216",
                "CR1220",
                "CR123",
                "CR123A",
                "CR1616",
                "CR1620",
                "CR1623",
                "CR1632",
                "CR2",
                "CR2016",
                "CR2023",
                "CR2025",
                "CR2026",
                "CR2032",
                "CR2412",
                "CR2430",
                "CR2450",
                "CR927",
                "D",
                "DD",
                "LR1130",
                "LR41",
                "LR43",
                "LR44",
                "LR45",
                "LR48",
                "LR54",
                "LR60",
                "LR63",
                "LR66",
                "N",
                "non-universal",
                "SR44W",
                "SR521SW",
                "SR616SW",
                "SR621SW",
                "SR626SW",
                "SR721SW",
                "SR916SW",
                "SR920SW",
                "SR927SW",
            ]
        }
    )


def default_special_character_rules() -> pd.DataFrame:
    rows = [
        ("\u00a9", "Delete", "", "Copyright symbol"),
        ("\u00ae", "Delete", "", "Registered trademark"),
        ("\u2122", "Delete", "", "Trademark"),
        ("\u00b0", "Replace", " Degree ", "Degree symbol"),
        ("\u00ba", "Replace", " Degree ", "Degree symbol"),
        ("\u00b1", "Replace", " +/-", "Plus-or-minus sign"),
        ("\u00b6", "Delete", "", "Paragraph mark"),
        ("\u00bc", "Replace", " 1/4", "Fraction, one-fourth"),
        ("\u00bd", "Replace", " 1/2", "Fraction, one-half"),
        ("\u00be", "Replace", " 3/4", "Fraction, three-fourths"),
        ("\u00d7", "Replace", " x", "Multiplication sign"),
        ("\u03a9", "Replace", " Ohm", "Ohm"),
        ("\u00b2", "Replace", " 2", "Superscript 2"),
        ("\u00b5", "Replace", "micro", "Mu or Micro"),
        ("\u03bcA", "Replace", "micro A", ""),
        ("\u03bcV", "Replace", "micro V", ""),
        ("\u2013", "Replace", "-", "-"),
        ("\u2014", "Replace", "-", "-"),
        ("~", "Replace", "-", "Tilde to -"),
        ("\u2019", "Replace", "'", "Single invert"),
        ("\u201c", "Replace", "\"", "Invert. Open"),
        ("\u201d", "Replace", "\"", "Invert. Close"),
        ("\u03b1", "Replace", "a", "Alpha"),
        ("\u2018", "Replace", "'", ""),
        ("\u00d8", "Delete", "", ""),
        ("\u00c2", "Replace", "A", ""),
        ("\u03a6", "Delete", "", "Phi"),
        ("\u02da", "Replace", " Degree ", "Degree symbol"),
        ("\u2264", "Replace", "<=", "Less than or equals to"),
        ("\uff5e", "Replace", "-", "Tilde to -"),
        ("\u2103", "Replace", " Degree C", "Degree symbol"),
        ("\u2265", "Replace", ">=", "Greater than or equals to"),
        ("\u221e", "Replace", "Infinite", ""),
        ("\u2033", "Replace", "\"", ""),
        ("\u2126", "Replace", "Ohm", "Ohm"),
        ("\u03bc", "Replace", "micro", ""),
        ("\u2011", "Replace", "-", ""),
        ("\u2032", "Replace", "'", ""),
        ("\u201e", "Replace", "\"", ""),
        ("\u00f8", "Delete", "", ""),
        ("\u01ab", "Delete", "", ""),
        ("\u01a9", "Delete", "", ""),
        ("\u2212", "Replace", "-", "-"),
        ("\ufb01", "Replace", "fi", ""),
        ("\uff1a", "Replace", ":", "colon"),
        ("\u00e9", "Replace", "e", ""),
        ("Grey", "Replace", "Gray", ""),
        ("grey", "Replace", "gray", ""),
        ("Colour", "Replace", "Color", ""),
        ("colour", "Replace", "color", ""),
        ("Adaptor", "Replace", "Adapter", ""),
        ("adaptor", "Replace", "adapter", ""),
        ("Velcro", "Replace", "Self-Securing Closure", ""),
        ("velcro", "Replace", "self-securing closure", ""),
        ("\u2026", "Replace", "...", ""),
        ("Aluminium", "Replace", "Aluminum", ""),
        ("\u215c", "Replace", "3/8", ""),
        ("\u00dc", "Replace", "U", ""),
        ("\u25b3", "Replace", "Delta ", "Delta"),
        ("\u2266", "Replace", "<=", ""),
        ("\u2267", "Replace", ">=", ""),
        ("\u2020", "Delete", "", ""),
        ("\u2248", "Replace", "=", ""),
        ("\u2393", "Replace", "=", ""),
        ("\u00e5", "Replace", "Angstrom", ""),
        ("\ufb02", "Replace", "fl", ""),
        ("\u3010", "Replace", "(", ""),
        ("\u3011", "Replace", ")", ""),
        ("aluminium", "Replace", "aluminum", ""),
        ("T\u00dcV", "Replace", "TUV", ""),
        ("X\u1d49", "Replace", "Xe", ""),
        ("\u00b7", "Replace", ".", ""),
        ("\u014d", "Replace", "o", ""),
        ("\uff08", "Replace", "(", ""),
        ("\uff09", "Replace", ")", ""),
        ("\u2161", "Replace", "II", ""),
        ("\u2160", "Replace", "I", ""),
        ("\uff0c", "Replace", ", ", ""),
        ("\u03c6", "Delete", "", "Phi"),
        ("\uff1c", "Replace", "<", "Less than"),
    ]
    return pd.DataFrame(rows, columns=["Symbol", "Action required", "Replace Value", "Symbol Meaning"])

def default_html_template() -> str:
    return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Product Sample Page</title>
  <style>
    body { font-family: Calibri, Arial, sans-serif; font-size: 15px; color: #222; }
    h1 { color: #8a4d00; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    td, th { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
    .muted { color: #666; }
  </style>
</head>
<body>
  <h1>--Title--</h1>
  <p class="muted"><strong>SKU:</strong> --ItemNo-- | <strong>Mfg Item:</strong> --MfgItem-- | <strong>Mfg Model:</strong> --MfgModel--</p>
  <h2>Short Title</h2>
  <p>--ShortTitle--</p>
  <h2>Description</h2>
  <p>--Description--</p>
  <h2>Includes</h2>
  <table><tbody>--Includes--</tbody></table>
  <h2>Features</h2>
  <table><tbody>--Features--</tbody></table>
  <h2>Specifications</h2>
  <table><tbody>--Specifications--</tbody></table>
  <h2>Highlights</h2>
  <ul>--Highlights--</ul>
  <h2>Battery Info</h2>
  <table><tbody>--Battery Info--</tbody></table>
  <p><strong>Warranty Months:</strong> --Warranty Months--</p>
</body>
</html>"""


@st.cache_data(show_spinner=False)
def _read_warranty_tsv(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str)
    # Convert warranty months to numeric
    numeric_cols = ["Warranty Months", "Months for Parts"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.fillna("")


def default_warranty() -> pd.DataFrame:
    from pathlib import Path
    warranty_file = Path(__file__).parent / "warranty_master.tsv"
    if warranty_file.exists():
        try:
            return _read_warranty_tsv(str(warranty_file), warranty_file.stat().st_mtime)
        except Exception:
            pass
    return pd.DataFrame(columns=[
        "Brand Name", "Mfg Code", "Warranty Description", "Warranty URL",
        "Warranty Tel#", "Warranty Months", "Months for Parts", "Comments"
    ])
