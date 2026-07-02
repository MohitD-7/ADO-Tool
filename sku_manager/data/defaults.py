from __future__ import annotations

import pandas as pd


def default_manufacturers() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Manufacturer": [
                "New Brand",
                "ErgoLife",
                "Leica",
                "Sprolink",
                "TAMRON",
                "Sony",
                "Canon",
                "Nikon",
            ]
        }
    )


def default_battery_materials() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Battery Material": [
                "-",
                "alkaline",
                "lead acid",
                "lithium",
                "lithium ion",
                "nickel metal hydride",
                "zinc air",
            ]
        }
    )


def default_battery_types() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Battery Type": [
                "-",
                "A",
                "AA",
                "AAA",
                "9-volt",
                "18650",
                "non-universal",
            ]
        }
    )


def default_special_character_rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Symbol": "(c)", "Action required": "Delete", "Replace Value": "", "Symbol Meaning": "Copyright shorthand"},
            {"Symbol": "(r)", "Action required": "Delete", "Replace Value": "", "Symbol Meaning": "Registered shorthand"},
            {"Symbol": "tm", "Action required": "Delete", "Replace Value": "", "Symbol Meaning": "Trademark shorthand"},
            {"Symbol": "°", "Action required": "Replace", "Replace Value": " Degree ", "Symbol Meaning": "Degree symbol"},
            {"Symbol": "±", "Action required": "Replace", "Replace Value": " +/-", "Symbol Meaning": "Plus/minus"},
            {"Symbol": "×", "Action required": "Replace", "Replace Value": " x", "Symbol Meaning": "Multiplication sign"},
        ]
    )


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


def default_checklist() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Checklist Item": [
                "Brand name is not in title and is present in short title",
                "Character limits are within allowed ranges",
                "Includes uses hyphen separators and no commas",
                "Similar SKUs were checked",
                "SKU item number has no spaces or copy/paste errors",
                "Battery information is added where applicable",
                "Special characters were reviewed",
                "Warranty months match includes/warranty copy",
                "Manufacturer filter is not added incorrectly",
            ],
            "Active": [True] * 9,
        }
    )
