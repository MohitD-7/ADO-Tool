from __future__ import annotations

from pathlib import Path

import streamlit as st


@st.cache_data(show_spinner=False)
def _read_overrides_css(path: str, mtime: float) -> str:
    return Path(path).read_text(encoding="utf-8")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --vo-orange: #ef8e0d;
          --vo-brown: #8b5000;
          --vo-border: #dfc8b3;
          --vo-muted: #6f6258;
          --vo-bg: #eef0f2;
          --vo-input-bg: #ffffff;
          --vo-input-border: #cbd5e1;
          --vo-input-focus: #ef8e0d;
          --vo-label: #1a2330;
          --vo-disabled-bg: #f0f0f0;
          --vo-disabled-text: #999;
        }

        /* â”€â”€ Global compactness â”€â”€ */
        /* Streamlit's default block gap is enormous â€” cut it down */
        .stApp {
          background: var(--vo-bg);
        }
        /* Remove the huge top padding Streamlit puts above the main content */
        .stApp > div > div > div > div {
          padding-top: 0 !important;
        }
        /* Newer Streamlit builds use these testids for the main container padding */
        div[data-testid="stMainBlockContainer"],
        section[data-testid="stMain"] > div,
        div[data-testid="stAppViewContainer"] > section > div,
        div[data-testid="stAppViewBlockContainer"] {
          padding-top: 0.25rem !important;
          padding-bottom: 0 !important;
        }
        /* Kill the invisible header spacer that used to sit under the top bar */
        div[data-testid="stHeader"] { height: 0 !important; }
        /* Tighten the gap between every block element */
        div[data-testid="stVerticalBlock"] > div {
          gap: 0.2rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
          padding: 0 !important;
        }
        /* Column gaps */
        div[data-testid="stHorizontalBlock"] {
          gap: 0.4rem !important;
        }
        /* Expander padding */
        div[data-testid="stExpander"] details summary {
          padding: 0.3rem 0.6rem !important;
        }
        div[data-testid="stExpander"] details div[data-testid="stVerticalBlock"] {
          padding: 0.35rem 0.6rem !important;
        }
        /* Caption / small text vertical margin */
        div[data-testid="stCaptionContainer"] {
          margin-bottom: 0 !important;
          margin-top: 0 !important;
        }
        div[data-testid="stMarkdownContainer"] p {
          margin-bottom: 0.2rem !important;
        }

        /* â”€â”€ Unify button heights and align with inputs â”€â”€ */
        /* Streamlit inputs render as label + input; labels sit ~24px tall
           (0.8rem font, line-height 1.5, plus 2px bottom margin).
           A button next to an input has no label so it starts 24px higher.
           .vo-spacer-btn fills that gap so button + input share a baseline. */
        .vo-spacer-btn {
          height: 24px !important;
          display: block !important;
          margin: 0 !important;
        }
        /* Make sure the injected spacer div doesn't get collapsed by
           stVerticalBlock's gap rule */
        div[data-testid="stVerticalBlock"] > div:has(> .vo-spacer-btn) {
          margin-bottom: 0 !important;
        }
        /* All buttons: fixed height matches input height so rows line up. */
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
          height: 34px !important;
          min-height: 34px !important;
          padding: 0 0.75rem !important;
          font-size: 0.85rem !important;
          line-height: 1 !important;
        }
        /* Match input height too so alignment is exact */
        .stTextInput input, .stNumberInput input, .stSelectbox > div > div,
        .stDateInput input {
          min-height: 34px !important;
        }

        /* â”€â”€ Hide Streamlit top toolbar (Share, star, edit, GitHub, menu) â”€â”€ */
        header[data-testid="stHeader"] { display: none !important; }
        div[data-testid="stToolbar"]  { display: none !important; }
        div[data-testid="stDecoration"] { display: none !important; }
        div[data-testid="stStatusWidget"] { display: none !important; }
        #MainMenu, footer { display: none !important; }

        /* â”€â”€ Sidebar â”€â”€ */
        section[data-testid="stSidebar"] {
          background: #ffffff;
          border-right: 2px solid var(--vo-border);
          width: 200px !important;
          min-width: 200px !important;
          max-width: 200px !important;
          transform: none !important;
          visibility: visible !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
          width: 200px !important;
        }
        /* Hide collapse arrow so the sidebar can't be closed */
        button[data-testid="stSidebarCollapseButton"],
        button[data-testid="stSidebarCollapsedControl"],
        button[data-testid="collapsedControl"],
        div[data-testid="stSidebarCollapseButton"],
        div[data-testid="stSidebarCollapsedControl"] {
          display: none !important;
        }
        /* Neutralise the collapsed state if it ever gets applied */
        section[data-testid="stSidebar"][aria-expanded="false"] {
          margin-left: 0 !important;
          transform: none !important;
        }
        /* Hide the "nav" / radio group label above the sidebar nav */
        section[data-testid="stSidebar"] .stRadio > label,
        section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"],
        section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"],
        section[data-testid="stSidebar"] .stRadio div[data-baseweb="form-control-label"] {
          display: none !important;
          visibility: hidden !important;
          height: 0 !important;
        }
        /* Nav radio items: clean, no bullets */
        section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
          gap: 2px !important;
          display: flex !important;
          flex-direction: column !important;
        }
        section[data-testid="stSidebar"] .stRadio label {
          display: flex !important;
          align-items: center !important;
          padding: 0.55rem 0.8rem !important;
          border-radius: 6px !important;
          font-size: 0.92rem !important;
          font-weight: 600 !important;
          color: #3a4550 !important;
          cursor: pointer !important;
          transition: background 0.1s !important;
          margin: 0 !important;
        }
        section[data-testid="stSidebar"] .stRadio label:hover {
          background: #f0f4f8 !important;
        }
        /* Hide the actual radio circle dot */
        section[data-testid="stSidebar"] .stRadio input[type="radio"] {
          display: none !important;
        }
        /* Active nav item */
        section[data-testid="stSidebar"] .stRadio input[type="radio"]:checked + div p {
          color: #ef8e0d !important;
          font-weight: 800 !important;
        }
        section[data-testid="stSidebar"] .stRadio label:has(input:checked) {
          background: #fff7ed !important;
          color: #ef8e0d !important;
          border-left: 3px solid #ef8e0d !important;
        }

        /* â”€â”€ Brand â”€â”€ */
        .vo-brand {
          font-size: 1.9rem;
          font-weight: 800;
          color: var(--vo-brown);
          margin-bottom: 0.1rem;
        }
        .vo-subtle {
          color: var(--vo-muted);
          font-size: 0.9rem;
        }

        /* â”€â”€ Page header card â”€â”€ */
        .vo-header {
          background: #ffffff;
          border: 1px solid var(--vo-border);
          border-left: 5px solid var(--vo-orange);
          border-radius: 8px;
          padding: 0.55rem 1rem;
          margin-bottom: 0.6rem;
        }
        .vo-title {
          font-size: 1.25rem;
          line-height: 1.2;
          font-weight: 800;
          color: #202428;
        }
        .vo-kicker {
          color: var(--vo-muted);
          font-weight: 700;
          letter-spacing: .03em;
          text-transform: uppercase;
          font-size: .72rem;
        }
        .vo-badge {
          display: inline-block;
          padding: .15rem .45rem;
          border-radius: 999px;
          background: #ffe2bd;
          color: var(--vo-brown);
          font-weight: 700;
          font-size: .72rem;
          margin-left: .3rem;
        }

        /* Kill orphan card-wrapper divs: st.markdown('<div style="...">')
           calls emit an unterminated <div>. The browser auto-closes it,
           leaving an empty coloured strip. Match any div (anywhere in
           the tree) whose inline style declares a 4px left border. */
        div[style*="border-left:4px"],
        div[style*="border-left: 4px"] {
          border: none !important;
          padding: 0 !important;
          margin: 0 !important;
          background: transparent !important;
          min-height: 0 !important;
          height: 0 !important;
          overflow: hidden !important;
          display: none !important;
        }

        /* â”€â”€ Section headings â”€â”€ */
        h3, .stSubheader {
          color: #1a2330 !important;
          font-weight: 700 !important;
          font-size: 0.95rem !important;
          padding-bottom: 0.2rem;
          border-bottom: 2px solid #e2e8f0;
          margin-top: 0 !important;
          margin-bottom: 0.4rem !important;
        }

        /* â”€â”€ Field labels â”€â”€ */
        .stTextInput label,
        .stTextArea label,
        .stSelectbox label,
        .stNumberInput label,
        .stFileUploader label,
        div[data-testid="stForm"] label {
          font-weight: 700 !important;
          font-size: 0.8rem !important;
          color: var(--vo-label) !important;
          letter-spacing: 0.01em;
          margin-bottom: 2px !important;
          padding-bottom: 0 !important;
        }

        /* â”€â”€ Text inputs â”€â”€ */
        .stTextInput input,
        .stNumberInput input {
          background-color: var(--vo-input-bg) !important;
          border: 2px solid var(--vo-input-border) !important;
          border-radius: 6px !important;
          color: #1a2330 !important;
          font-size: 0.88rem !important;
          padding: 0.28rem 0.55rem !important;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .stTextInput input:focus,
        .stNumberInput input:focus {
          border-color: var(--vo-input-focus) !important;
          box-shadow: 0 0 0 3px rgba(239,142,13,0.24) !important;
          outline: none !important;
        }
        .stTextInput input:hover:not(:focus):not(:disabled),
        .stNumberInput input:hover:not(:focus):not(:disabled) {
          border-color: #5a8090 !important;
        }

        /* â”€â”€ Disabled inputs â€” clearly non-editable â”€â”€ */
        .stTextInput input:disabled,
        .stNumberInput input:disabled {
          background-color: var(--vo-disabled-bg) !important;
          border-color: #ccc !important;
          color: var(--vo-disabled-text) !important;
          cursor: not-allowed !important;
          font-style: italic;
        }

        /* â”€â”€ Text areas â”€â”€ */
        .stTextArea textarea {
          background-color: var(--vo-input-bg) !important;
          border: 2px solid var(--vo-input-border) !important;
          border-radius: 6px !important;
          color: #1a2330 !important;
          font-size: 0.88rem !important;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .stTextArea textarea:focus {
          border-color: var(--vo-input-focus) !important;
          box-shadow: 0 0 0 3px rgba(239,142,13,0.24) !important;
          outline: none !important;
        }
        .stTextArea textarea:hover:not(:focus) {
          border-color: #5a8090 !important;
        }

        /* â”€â”€ Selectboxes â”€â”€ */
        .stSelectbox > div > div {
          background-color: var(--vo-input-bg) !important;
          border: 2px solid var(--vo-input-border) !important;
          border-radius: 6px !important;
        }
        .stSelectbox > div > div:focus-within {
          border-color: var(--vo-input-focus) !important;
          box-shadow: 0 0 0 3px rgba(239,142,13,0.24) !important;
        }
        /* Disabled selectboxes â€” match disabled text inputs */
        .stSelectbox div[data-baseweb="select"][aria-disabled="true"],
        .stSelectbox:has([aria-disabled="true"]) > div > div,
        .stSelectbox:has(> div[disabled]) > div > div {
          background-color: var(--vo-disabled-bg) !important;
          border-color: #ccc !important;
          color: var(--vo-disabled-text) !important;
          cursor: not-allowed !important;
        }
        .stSelectbox:has([aria-disabled="true"]) svg {
          opacity: 0.4 !important;
        }

        /* â”€â”€ Character counter â”€â”€ */
        .vo-count-ok  { color: #2a7a3a; font-size: .75rem; font-weight: 700; text-align: right; margin-top: -2px; margin-bottom: 2px; }
        .vo-count-bad { color: #c62828; font-size: .75rem; font-weight: 800; text-align: right; margin-top: -2px; margin-bottom: 2px; }

        /* â”€â”€ Warning box â”€â”€ */
        .vo-warning {
          background: #fff8ee;
          border: 1px solid #f3c37f;
          border-left: 4px solid var(--vo-orange);
          color: #5c3900;
          border-radius: 6px;
          padding: .4rem .7rem;
          margin: .25rem 0;
          font-size: 0.82rem;
        }

        /* ── Generic card ── */
        .vo-card {
          background: #fff;
          border: 1px solid var(--vo-border);
          border-radius: 8px;
          padding: 0.6rem 1rem;
          margin: 0.25rem 0 0.5rem 0;
        }

        /* ── Divider ── */
        .vo-divider {
          border: none;
          border-top: 1px solid #e2e8f0;
          margin: 0.5rem 0;
        }

        /* ── Buttons ── */
        .stButton button,
        .stFormSubmitButton button {
          border-radius: 6px;
          border: 1.5px solid #cbd5e1;
          font-weight: 700;
          font-size: 0.82rem;
          padding: 0.25rem 0.7rem;
          transition: background 0.12s, border-color 0.12s;
        }
        .stButton button:hover,
        .stFormSubmitButton button:hover {
          border-color: var(--vo-input-focus);
          background: #f8fafc;
        }
        .stButton button:focus,
        .stFormSubmitButton button:focus {
          outline: none !important;
          box-shadow: none !important;
        }
        .stButton button[kind="primary"],
        .stFormSubmitButton button[kind="primary"] {
          background: #ef8e0d !important;
          border-color: #ef8e0d !important;
          color: #fff !important;
        }
        .stButton button[kind="primary"]:hover {
          background: #d97f06 !important;
        }

        /* â”€â”€ Metric cards â”€â”€ */
        div[data-testid="stMetric"] {
          background: #fff;
          border: 1px solid var(--vo-border);
          border-radius: 8px;
          padding: .45rem .7rem;
        }
        div[data-testid="stMetric"] label {
          font-size: .75rem !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
          font-size: 1.3rem !important;
        }

        /* â”€â”€ Data editor â”€â”€ */
        div[data-testid="stDataEditor"] {
          border: 2px solid var(--vo-input-border) !important;
          border-radius: 8px !important;
          overflow: hidden;
        }

        /* â”€â”€ File uploader â”€â”€ */
        div[data-testid="stFileUploader"] > div {
          border: 2px dashed var(--vo-input-border) !important;
          border-radius: 8px !important;
          background: #f8fafc !important;
        }
        div[data-testid="stFileUploader"] > div:hover {
          border-color: var(--vo-input-focus) !important;
          background: #f8fafc !important;
        }

        /* â”€â”€ Sticky workspace / review topbar â”€â”€ */
        .vo-topbar {
          position: sticky;
          top: 0;
          z-index: 100;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          background: #1a2330;
          border-radius: 8px;
          padding: .42rem .85rem;
          margin-bottom: .35rem;
          box-shadow: 0 2px 8px rgba(0,0,0,.18);
        }
        .vo-topbar-sku {
          display: flex;
          align-items: baseline;
          gap: .5rem;
          min-width: 0;
          flex-shrink: 1;
          overflow: hidden;
        }
        .vo-topbar-label {
          font-size: .65rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .07em;
          color: #cbd5e1;
          white-space: nowrap;
        }
        .vo-topbar-ino {
          font-size: .85rem;
          font-weight: 800;
          color: #fff7ed;
          white-space: nowrap;
          flex-shrink: 0;
        }
        .vo-topbar-title {
          font-size: .8rem;
          color: #cbd5e1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .vo-workspace-content-gap {
          height: 0.1rem;
        }

        /* ═══════════════════════════════════════════════════════════════
           DESIGNv2 — VirtualOps SKU Manager (per DESIGN.md prose)
           Cool-gray neutral stack, orange primary, high density.
           Scoped under `.dv2` so it doesn't leak onto legacy pages.
           ═══════════════════════════════════════════════════════════════ */
        .dv2 {
          /* Brand */
          --dv2-primary:        #EF8E0D;   /* buttons, active tabs, focus */
          --dv2-primary-hover:  #D97F06;
          --dv2-on-primary:     #FFFFFF;
          --dv2-secondary:      #1A1A1B;   /* high-contrast text, nav bg */

          /* Cool-gray neutral stack (DESIGN.md > Colors) */
          --dv2-neutral-50:  #F8FAFC;   /* Surface 0 — app canvas, table headers */
          --dv2-neutral-100: #F1F5F9;   /* zebra stripe */
          --dv2-neutral-200: #E2E8F0;   /* card border */
          --dv2-neutral-300: #CBD5E1;   /* secondary button border, input border */
          --dv2-neutral-400: #94A3B8;
          --dv2-neutral-500: #64748B;   /* muted text */
          --dv2-neutral-700: #334155;
          --dv2-neutral-900: #0F172A;   /* body text */

          /* Status */
          --dv2-success: #22C55E;
          --dv2-danger:  #EF4444;
          --dv2-info:    #3B82F6;

          font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          color: var(--dv2-neutral-900);
        }

        /* ── Header card ─────────────────────────────────────────────── */
        .dv2 .dv2-header {
          background: #FFFFFF;
          border: 1px solid var(--dv2-neutral-200);
          border-radius: 4px;                 /* Shapes: 0.25rem */
          padding: 8px 16px;                  /* Density: high, 4px base */
          margin-bottom: 8px;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
        }
        .dv2 .dv2-header-left { min-width: 0; flex: 1; overflow: hidden; }
        .dv2 .dv2-chip-row {
          display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
          margin-bottom: 3px;
        }
        .dv2 .dv2-id-chip {
          background: var(--dv2-neutral-100);
          color: var(--dv2-neutral-900);
          border: 1px solid var(--dv2-neutral-200);
          border-radius: 10px;                /* Shapes: chips are pill 12px */
          padding: 1px 8px;
          font-family: 'JetBrains Mono', ui-monospace, monospace;
          font-size: 11px; line-height: 15px; font-weight: 400;
        }
        .dv2 .dv2-status-chip {
          border-radius: 10px;                /* pill */
          padding: 1px 8px;
          font-size: 10px; line-height: 15px; font-weight: 700;
          letter-spacing: .06em; text-transform: uppercase;
        }
        .dv2 .dv2-status-draft {
          background: rgba(239,142,13,.14);   /* Active tint */
          color: #8b5000;
        }
        .dv2 .dv2-status-alert {
          background: var(--dv2-danger);      /* Alerts: high-contrast + dark text */
          color: #FFFFFF;
        }
        .dv2 .dv2-status-neutral {
          background: var(--dv2-neutral-100);
          color: var(--dv2-neutral-700);
        }
        .dv2 .dv2-header-title {
          font-family: 'Inter', sans-serif;
          font-size: 16px; line-height: 20px; font-weight: 700;
          letter-spacing: -.01em;
          color: var(--dv2-neutral-900);
          margin: 0 0 2px 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
        }
        .dv2 .dv2-header-meta {
          font-size: 11px; line-height: 14px;
          color: var(--dv2-neutral-500);
          display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
          margin: 0;
        }
        .dv2 .dv2-header-meta .dv2-sep { color: var(--dv2-neutral-300); }
        .dv2 .dv2-header-meta .dv2-lbl { font-weight: 600; color: var(--dv2-neutral-700); }
        .dv2 .dv2-header-meta .dv2-mono {
          font-family: 'JetBrains Mono', ui-monospace, monospace;
          color: var(--dv2-neutral-900);
        }

        /* ── Form card (Surface 1: white + 1px border, NO shadow) ────── */
        .dv2 .dv2-card {
          background: #FFFFFF;
          border: 1px solid var(--dv2-neutral-200);
          border-radius: 4px;
          padding: 16px 20px;
          margin-bottom: 12px;
        }
        .dv2 .dv2-section + .dv2-section { margin-top: 20px; }
        .dv2 .dv2-section-title {
          font-family: 'Inter', sans-serif;
          font-size: 13px; line-height: 18px; font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .06em;
          color: var(--dv2-neutral-700);
          border-bottom: 1px solid var(--dv2-neutral-200);
          padding: 16px 0 6px;
          margin: 0 0 12px 0 !important;
          border-top: none !important;
        }

        /* ── Label row (LABEL … 47/150) ─────────────────────────────── */
        .dv2 .dv2-label-row {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          font-family: 'Inter', sans-serif;
          font-size: 11px; line-height: 16px;
          letter-spacing: .06em;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--dv2-neutral-500);
          margin-bottom: 4px;
        }
        .dv2 .dv2-label-row .dv2-count {
          font-size: 10px; font-weight: 500;
          color: var(--dv2-neutral-400);
          letter-spacing: 0;
          text-transform: none;
          font-family: 'JetBrains Mono', ui-monospace, monospace;
        }
        .dv2 .dv2-label-row .dv2-count.bad { color: var(--dv2-danger); font-weight: 700; }

        /* ── Inputs (flat white, 1px border, orange glow on focus) ──── */
        .dv2 .stTextInput input,
        .dv2 .stNumberInput input,
        .dv2 .stTextArea textarea,
        .dv2 .stSelectbox > div > div {
          background-color: #FFFFFF !important;
          border: 1px solid var(--dv2-neutral-300) !important;
          border-radius: 4px !important;
          color: var(--dv2-neutral-900) !important;
          font-family: 'Inter', sans-serif !important;
          font-size: 13px !important;
          line-height: 18px !important;
          padding: 6px 10px !important;
          box-shadow: none !important;
          transition: border-color .12s, box-shadow .12s;
        }
        /* Mono for numeric fields — DESIGN.md: "SKU numbers, quantities, UPC codes" */
        .dv2 .stNumberInput input,
        .dv2 .dv2-mono-input .stTextInput input {
          font-family: 'JetBrains Mono', ui-monospace, monospace !important;
          font-size: 13px !important;
        }
        .dv2 .stTextInput input:focus,
        .dv2 .stNumberInput input:focus,
        .dv2 .stTextArea textarea:focus {
          border-color: var(--dv2-primary) !important;
          box-shadow: 0 0 0 2px rgba(239,142,13,.28) !important;   /* orange glow, 2px offset */
          outline: none !important;
        }
        .dv2 .stSelectbox > div > div:focus-within {
          border-color: var(--dv2-primary) !important;
          box-shadow: 0 0 0 2px rgba(239,142,13,.28) !important;
        }
        .dv2 .stTextInput input::placeholder,
        .dv2 .stTextArea textarea::placeholder {
          color: var(--dv2-neutral-400) !important;
        }

        /* Hide Streamlit's built-in label — we render our own dv2-label-row */
        .dv2 .dv2-field .stTextInput label,
        .dv2 .dv2-field .stNumberInput label,
        .dv2 .dv2-field .stSelectbox label,
        .dv2 .dv2-field .stTextArea label {
          display: none !important;
        }

        /* ── Buttons ─────────────────────────────────────────────────── */
        .dv2 .stButton button {
          border-radius: 4px !important;
          font-family: 'Inter', sans-serif !important;
          font-size: 13px !important;
          line-height: 18px !important;
          font-weight: 600 !important;
          letter-spacing: 0 !important;
          padding: 6px 12px !important;
          height: auto !important;
          min-height: 32px !important;
          box-shadow: none !important;
          transition: background .12s, opacity .12s, border-color .12s !important;
        }
        /* Secondary: white bg + 1px gray border + BLACK text */
        .dv2 .stButton button[kind="secondary"],
        .dv2 .stButton button:not([kind="primary"]) {
          background: #FFFFFF !important;
          border: 1px solid var(--dv2-neutral-300) !important;
          color: var(--dv2-neutral-900) !important;
        }
        .dv2 .stButton button[kind="secondary"]:hover,
        .dv2 .stButton button:not([kind="primary"]):hover {
          background: var(--dv2-neutral-50) !important;
          border-color: var(--dv2-neutral-400) !important;
        }
        /* Primary: solid orange with WHITE text */
        .dv2 .stButton button[kind="primary"],
        .dv2 .stFormSubmitButton button[kind="primary"] {
          background: var(--dv2-primary) !important;
          border: 1px solid var(--dv2-primary) !important;
          color: var(--dv2-on-primary) !important;
        }
        .dv2 .stButton button[kind="primary"]:hover,
        .dv2 .stFormSubmitButton button[kind="primary"]:hover {
          background: var(--dv2-primary-hover) !important;
          border-color: var(--dv2-primary-hover) !important;
        }
        /* Focus: 2px solid orange with 2px offset (accessible) */
        .dv2 .stButton button:focus-visible {
          outline: 2px solid var(--dv2-primary) !important;
          outline-offset: 2px !important;
        }

        /* ── Sub-tab strip (General / Description / …) ─────────────── */
        /* Streamlit renders each tab as its own st.button. We paint them
           as flat underlined tabs and mark the active one with orange. */
        .dv2-tabs { margin-bottom: 12px; }
        .dv2-tabs div[data-testid="stHorizontalBlock"] {
          gap: 4px !important;
          border-bottom: 1px solid var(--dv2-neutral-200);
          padding: 0 4px;
        }
        .dv2-tabs .stButton button {
          background: transparent !important;
          border: none !important;
          border-bottom: 2px solid transparent !important;
          border-radius: 0 !important;
          color: var(--dv2-neutral-500) !important;
          font-weight: 600 !important;
          font-size: 13px !important;
          padding: 10px 4px !important;
          min-height: 0 !important;
          margin-bottom: -1px !important;   /* overlap the strip's border */
          text-transform: none !important;
          letter-spacing: 0 !important;
        }
        .dv2-tabs .stButton button:hover {
          color: var(--dv2-neutral-900) !important;
          background: transparent !important;
          border-bottom-color: var(--dv2-neutral-300) !important;
        }
        /* Active tab: primary-kind button carries the orange underline */
        .dv2-tabs .stButton button[kind="primary"] {
          background: transparent !important;
          color: var(--dv2-primary) !important;
          border: none !important;
          border-bottom: 2px solid var(--dv2-primary) !important;
          border-radius: 0 !important;
          font-weight: 700 !important;
        }
        .dv2-tabs .stButton button[kind="primary"]:hover {
          background: transparent !important;
          color: var(--dv2-primary-hover) !important;
          border-bottom-color: var(--dv2-primary-hover) !important;
        }
        .dv2-tabs .stButton button:focus-visible {
          outline: none !important;
          border-bottom-color: var(--dv2-primary) !important;
        }
        /* Hide "Press Enter to apply" hints — values also commit on click-away */
        [data-testid="InputInstructions"] { display: none !important; }
        /* Hide the chain-link anchor icon next to headings */
        [data-testid="stHeaderActionElements"] { display: none !important; }
        h1 > a, h2 > a, h3 > a, h4 > a, h5 > a, h6 > a { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    overrides_path = Path(__file__).with_name("design_overrides.css")
    if overrides_path.exists():
        overrides_css = _read_overrides_css(str(overrides_path), overrides_path.stat().st_mtime)
        st.markdown(f"<style>{overrides_css}</style>", unsafe_allow_html=True)
