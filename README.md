# VirtualOps SKU Manager

A modular Streamlit replacement for the legacy Excel/VBA SKU processing workbook.

## Run Locally

```powershell
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Current Workflow

1. Upload an Excel queue with `Item No`, `Title`, and `Mfg Item`.
2. Process each SKU through focused pages:
   - Queue
   - General
   - Description
   - Features
   - Specs
   - Highlights
   - Preview & Export
   - Reference Data
3. Export the processed details in the VBA-style row format.

## Notes

This first version stores app data in Streamlit session state. For deployment with multiple users, replace the session store with a persistent backend such as Supabase, Google Sheets, Airtable, or a database.
