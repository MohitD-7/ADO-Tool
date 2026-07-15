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

## AI Spec Autofill

The Specs tab can use OpenAI to fill blank V5 values from pasted product/spec source text.

Configure the API key outside the codebase:

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_MODEL="o3"
streamlit run streamlit_app.py
```

You can also set `openai_api_key` in Streamlit secrets. `OPENAI_MODEL` is optional and defaults to `o3`.

## Notes

This first version stores app data in Streamlit session state. For deployment with multiple users, replace the session store with a persistent backend such as Supabase, Google Sheets, Airtable, or a database.
