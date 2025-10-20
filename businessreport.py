import streamlit as st
import pandas as pd
import pdfplumber
import re
from openai import AzureOpenAI
import os
import database

# ==========================
# 📄 1️⃣ Extract KPIs from Power BI PDF
# ==========================
def extract_kpi_from_pdf(pdf_path: str):
    """Safely extract KPI data from Power BI export PDF."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    data = {
        "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
        "Port Time Savings (%)": [],
        "Arrival Accuracy (%)": [],
        "Bunker Savings (USD M)": [],
        "Carbon Abatement (K tonnes)": [],
    }

    with pdfplumber.open(pdf_path) as pdf:
        text = "".join(page.extract_text() or "" for page in pdf.pages)

    def safe_extract(pattern, section):
        """Extract using regex only after the section header appears."""
        try:
            part = text.split(section, 1)[1]
            return re.findall(pattern, part)
        except Exception:
            return []

    port = [int(x) for x in safe_extract(r"(\d{1,2})%", "Port Time Savings")]
    acc = [int(x) for x in safe_extract(r"(\d{1,3})%", "Arrival Accuracy")]
    bunk = [float(x) for x in safe_extract(r"(\d+\.\d+)M", "Bunker Savings")]
    carb = [float(x) for x in safe_extract(r"(\d+\.\d+)", "Carbon Abatement")]

    max_len = len(data["Month"])
    for key, arr in {
        "Port Time Savings (%)": port,
        "Arrival Accuracy (%)": acc,
        "Bunker Savings (USD M)": bunk,
        "Carbon Abatement (K tonnes)": carb,
    }.items():
        data[key] = arr[:max_len] + [None] * (max_len - len(arr))

    return pd.DataFrame(data)


# ==========================
# 🤖 2️⃣ Generate AI Business Report
# ==========================
from openai import AzureOpenAI
import pandas as pd
import database  # assuming you already have this file in your project

def generate_ai_report(df, azure, username):
    """Generate a personalized AI-driven report using Azure OpenAI and user details."""

    # 1️⃣ Fetch user details from database
    user_info = database.get_info(username)
    
    role = user_info.get("role", "staff").title()
    dept = user_info.get("department", "General")
    job = user_info.get("job_title", "Employee")

    # 2️⃣ Build dynamic context
    user_context = f"""
    User Profile:
    - Name: {username}
    - Role: {role}
    - Department: {dept}
    - Job Title: {job}

    You should adapt your analysis tone and focus based on the user's background.
    For example:
    - If they are an executive or manager, focus on strategic summaries and decisions.
    - If they are an analyst, focus on data trends and root cause analysis.
    - If they are from operations, highlight process efficiency and risks.
    - If they are from sales, focus on growth, customers, and targets.
    """

    # 3️⃣ Construct the main prompt
    prompt = f"""
    You are a senior operations analyst.
    You are writing this report for: {role} in {dept}.
    Use their professional background to tailor the level of detail and emphasis.

    KPI Data (from Power BI report):
    {df.to_markdown(index=False)}

    {user_context}

    Write a concise, actionable performance summary that:
    - Identifies key trends (positive or negative)
    - Explains potential causes or correlations
    - Recommends 2–3 clear actions aligned with their department
    - Uses professional tone and structured formatting
    """

    # 4️⃣ Call Azure OpenAI
    client = AzureOpenAI(
        azure_endpoint=azure["AZURE_OPENAI_ENDPOINT"],
        api_key=azure["AZURE_OPENAI_KEY"],
        api_version="2024-02-15-preview",
    )

    response = client.chat.completions.create(
        model=azure["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {"role": "system", "content": "You are an expert business intelligence and operations analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=1,
    )

    return response.choices[0].message.content.strip()

# ==========================
# 🚀 3️⃣ Streamlit App Logic
# ==========================
def app():
    st.title("📊 Power BI → AI Business Report")
    st.caption("Reads KPI data from a Power BI PDF export and generates insights using Azure OpenAI.")

    select_file()

def select_file():
    files = database.get_files(st.session_state["username"])
    print(files)
    filenames=[]
    if files:
        for file in files:
            filenames.append(file["file_name"])
        # Extract filenames for display
        #filenames = [file["file_name"] for file in files]

        # Let user pick one file
        filename = st.radio(
            "Select file to generate report:",
            filenames,
            index=0  # optional: pre-select first item
        )
        st.success(f"Selected file: {filename}")

    else:
        st.warning("No files found for your account.")
        filename = None

    if st.button("Generate"):
        output_path = database.save_file_to_local(filename)
        st.info(f"Using exported Power BI report: `{filename}`")
        run(output_path)

def run(pdf_path):
    # Step 1: Extract KPIs
    try:
        df = extract_kpi_from_pdf(pdf_path)
        st.success("✅ Extracted KPI Data")
        st.dataframe(df)
    except Exception as e:
        st.error(f"❌ Failed to extract data from PDF: {e}")
        return

    # Step 2: Generate AI Analysis
    try:
        azure = st.secrets

        # ✅ Get username from Streamlit session
        username = st.session_state.get("username", "guest")

        st.subheader("🧠 Generating AI Business Summary...")
        report = generate_ai_report(df, azure, username)
        st.subheader("📄 AI-Generated Insights")
        st.write(report)

        # Save results locally
        with open("business_summary.txt", "w", encoding="utf-8") as f:
            f.write(report)
        st.success("💾 Report saved as business_summary.txt")
        
        database.save_ai_report(username, "business_summary.txt", report)
        st.success("📤 Report uploaded to Supabase.")


    except Exception as e:
        st.error(f"❌ Failed to generate AI report: {e}")



if __name__ == "__main__":
    app()
