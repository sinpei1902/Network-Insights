import streamlit as st
import importlib


PAGES = {
    "Account": "account",
    "MAIN DASHBOARD": "main_dashboard.consoldashboard",
    "1️⃣ Export Power BI Dashboard": "powerbi",
    "2️⃣ Generate Business Report": "businessreport",
    "3. News updates": "news",
    "4. Graphs": "graphs",
    "5. Chat": "chattest",
}


st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", list(PAGES.keys()))


module_name = PAGES[page]
module = importlib.import_module(module_name)


if hasattr(module, "app"):
    if module == importlib.import_module("account"):
        module.app()
    elif "username" in st.session_state and st.session_state["username"]:
        module.app()
    else:
        st.write("Please login first.")
else:
    st.error(f"The module `{module_name}` has no `app()` function.")