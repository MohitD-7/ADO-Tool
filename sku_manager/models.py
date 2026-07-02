from __future__ import annotations

from copy import deepcopy
from typing import Any


DETAIL_DEFAULTS: dict[str, Any] = {
    "item_no": "",
    "title": "",
    "short_title": "",
    "description": "",
    "mfg_item": "",
    "mfg_model": "",
    "manufacturer": "",
    "warranty_months": "",
    "battery_info": "no battery used",
    "battery_material": "",
    "battery_type": "",
    "battery_quantity": "",
    "title_source": "",
    "short_title_source": "",
    "description_source": "",
    "includes_source": "",
    "comments": "",
    "video_link": "",
}


def new_item_record(item_no: str = "", title: str = "", mfg_item: str = "") -> dict[str, Any]:
    details = deepcopy(DETAIL_DEFAULTS)
    details["item_no"] = item_no
    details["title"] = title
    details["mfg_item"] = mfg_item
    return {
        "details": details,
        "features": [],
        "specs": [],
        "highlights": [],
        "includes": [],
        "comments": {},
        "links": {
            "general": ["", "", "", ""],
            "features": [""],
            "specs": [""],
            "highlights": [""],
            "includes": [""],
        },
    }
