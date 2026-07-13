APP_TITLE = "VirtualOps SKU Manager"

# Names shown in the sidebar "User" picker; each name keys a private autosave
# file under sku_manager/data/saves/. Can be overridden without a code change
# by adding `save_users = ["Name 1", "Name 2", ...]` to Streamlit secrets.
SAVE_USERS = [
    "Aniruddha",
    "Digpal",
    "Divya",
    "Harsh",
    "Hetvi",
    "Hitesh",
    "Kunjan",
    "Mittal",
    "Nazmeen",
    "Neeraj",
    "Sagar",
    "Shraddha",
    "Vidhi",
    "Trainee",
]

QUEUE_COLUMNS = ["ATR Type", "JIRA", "Item No", "Title", "Mfg Item", "Status"]

INPUT_SHEET_COLUMNS = ["ATR Type", "JIRA", "Item No", "Title", "Mfg Item"]

OUTPUT_COLUMNS = [
    "",
    "Field Name",
    "Item Number",
    "Value1",
    "Value2",
    "Value3",
    "Value4",
    "Value5",
    "Comments",
    "Source",
]

STATUS_OPTIONS = ["", "In Progress", "Completed", "Needs Review"]

BATTERY_INFO_OPTIONS = [
    "no battery used",
    "optional, included",
    "optional, not included",
    "required, included",
    "required, not included",
]
