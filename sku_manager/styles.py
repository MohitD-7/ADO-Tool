from __future__ import annotations

import streamlit as st


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --vo-orange: #f28c00;
          --vo-brown: #8a4d00;
          --vo-border: #dfc8b3;
          --vo-muted: #6f6258;
          --vo-bg: #eef0f2;
          --vo-input-bg: #ffffff;
          --vo-input-border: #8fa3b8;
          --vo-input-focus: #2f6f73;
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
          padding-top: 0.5rem !important;
        }
        /* Tighten the gap between every block element */
        div[data-testid="stVerticalBlock"] > div {
          gap: 0.35rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
          padding: 0 !important;
        }
        /* Column gaps */
        div[data-testid="stHorizontalBlock"] {
          gap: 0.5rem !important;
        }
        /* Expander padding */
        div[data-testid="stExpander"] details summary {
          padding: 0.35rem 0.6rem !important;
        }
        div[data-testid="stExpander"] details div[data-testid="stVerticalBlock"] {
          padding: 0.4rem 0.6rem !important;
        }
        /* Caption / small text vertical margin */
        div[data-testid="stCaptionContainer"] {
          margin-bottom: 0 !important;
          margin-top: 0 !important;
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
        section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {
          display: none !important;
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
          color: #2f6f73 !important;
          font-weight: 800 !important;
        }
        section[data-testid="stSidebar"] .stRadio label:has(input:checked) {
          background: #e8f4f4 !important;
          color: #2f6f73 !important;
          border-left: 3px solid #2f6f73 !important;
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

        /* â”€â”€ Section headings â”€â”€ */
        h3, .stSubheader {
          color: #1a2330 !important;
          font-weight: 700 !important;
          font-size: 0.95rem !important;
          padding-bottom: 0.2rem;
          border-bottom: 2px solid #dde3ea;
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
          box-shadow: 0 0 0 3px rgba(47,111,115,0.18) !important;
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
          box-shadow: 0 0 0 3px rgba(47,111,115,0.18) !important;
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
          box-shadow: 0 0 0 3px rgba(47,111,115,0.18) !important;
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

        /* â”€â”€ Generic card â”€â”€ */
        .vo-card {
          background: #fff;
          border: 1px solid var(--vo-border);
          border-radius: 8px;
          padding: 0.6rem 1rem;
          margin: 0.25rem 0 0.5rem 0;
        }

        /* â”€â”€ Divider â”€â”€ */
        .vo-divider {
          border: none;
          border-top: 1px solid #dde3ea;
          margin: 0.5rem 0;
        }

        /* â”€â”€ Buttons â”€â”€ */
        .stButton button {
          border-radius: 6px;
          border: 1.5px solid #8fa3b8;
          font-weight: 700;
          font-size: 0.82rem;
          padding: 0.25rem 0.7rem;
          transition: background 0.12s, border-color 0.12s;
        }
        .stButton button:hover {
          border-color: var(--vo-input-focus);
          background: #f0f7f7;
        }
        .stButton button:focus {
          outline: none !important;
          box-shadow: none !important;
        }
        .stButton button[kind="primary"] {
          background: #2f6f73 !important;
          border-color: #2f6f73 !important;
          color: #fff !important;
        }
        .stButton button[kind="primary"]:hover {
          background: #245558 !important;
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
          background: #f0f7f7 !important;
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
          color: #8fa3b8;
          white-space: nowrap;
        }
        .vo-topbar-ino {
          font-size: .85rem;
          font-weight: 800;
          color: #e8f4f4;
          white-space: nowrap;
          flex-shrink: 0;
        }
        .vo-topbar-title {
          font-size: .8rem;
          color: #8fa3b8;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .vo-workspace-content-gap {
          height: 0.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
