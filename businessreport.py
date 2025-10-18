import streamlit as st
import pandas as pd
import pdfplumber
import re
from openai import AzureOpenAI
import os

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
def generate_ai_report(df, azure):
    """Generate AI-driven summary using Azure OpenAI."""
    client = AzureOpenAI(
        azure_endpoint=azure["AZURE_OPENAI_ENDPOINT"],
        api_key=azure["AZURE_OPENAI_KEY"],
        api_version="2024-02-15-preview",
    )

    prompt = f"""
    You are a senior operations analyst. 
    Using the following KPI data extracted from a Power BI report,
    write a concise but actionable performance summary with insights and recommendations.

    Data:
    {df.to_markdown(index=False)}
    """

    response = client.chat.completions.create(
        model=azure["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {"role": "system", "content": "You are an expert in operations analytics and reporting."},
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

    pdf_path = "dashboard_export.pdf"
    st.info(f"Using exported Power BI report: `{pdf_path}`")

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
        st.subheader("🧠 Generating AI Business Summary...")
        report = generate_ai_report(df, azure)
        st.subheader("📄 AI-Generated Insights")
        st.write(report)

        # Save results locally
        with open("business_summary.txt", "w", encoding="utf-8") as f:
            f.write(report)
        st.success("💾 Report saved as business_summary.txt")

    except Exception as e:
        st.error(f"❌ Failed to generate AI report: {e}")


if __name__ == "__main__":
    app()
