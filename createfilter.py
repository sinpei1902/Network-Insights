# createfilter.py
import streamlit as st
import database

# =========================
# 🧠 USER FILTER MANAGEMENT
# =========================
def create_job_filter(username, job_name, operator_values, service_values, bu_values):
    """Save new job-specific filters into Supabase."""
    filters = [
        {
            "$schema": "http://powerbi.com/product/schema#basic",
            "target": {"table": "data", "column": "Operator"},
            "operator": "In",
            "values": operator_values,
        },
        {
            "$schema": "http://powerbi.com/product/schema#basic",
            "target": {"table": "data", "column": "Service"},
            "operator": "In",
            "values": service_values,
        },
        {
            "$schema": "http://powerbi.com/product/schema#basic",
            "target": {"table": "data", "column": "BU"},
            "operator": "In",
            "values": bu_values,
        },
    ]
    database.add_job_filter(username, job_name, filters)
    st.success(f"✅ Saved filter set for '{job_name}'")

def load_job_filters(username):
    """Fetch all saved filters for a user."""
    return database.get_user_jobs(username)

# =========================
# 🚀 STREAMLIT UI
# =========================
def app():
    st.title("⚙️ Create & Manage Auto Filters")

    username = st.session_state.get("username", "demo_user")
    st.info(f"👤 Logged in as: {username}")

    # ---------- Create new filter ----------
    st.subheader("➕ Create New Auto Filter")
    with st.form("create_job_form"):
        job_name = st.text_input("Job Name")
        operator_values = st.text_input("Operators (comma-separated)").split(",")
        service_values = st.text_input("Services (comma-separated)").split(",")
        bu_values = st.text_input("Business Units (comma-separated)").split(",")

        submitted = st.form_submit_button("💾 Save Auto Filter")
        if submitted:
            if job_name.strip():
                create_job_filter(username, job_name, operator_values, service_values, bu_values)
            else:
                st.error("Please enter a job name before saving.")

    # ---------- View existing filters ----------
    st.subheader("📂 Your Saved Auto Filters")
    jobs = load_job_filters(username)
    if not jobs:
        st.info("No filters saved yet.")
    else:
        for job in jobs:
            st.markdown(f"**🧩 {job['job_name']}**")
            st.json(job["filters"])
