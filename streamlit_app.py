import streamlit as st
import importlib

PAGES = {
    "1️⃣ Export Power BI Dashboard": "test",
    "2️⃣ Generate Business Report": "businessreport",
}

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", list(PAGES.keys()))

module_name = PAGES[page]
module = importlib.import_module(module_name)

if hasattr(module, "app"):
    module.app()
else:
    st.error(f"The module `{module_name}` has no `app()` function.")
