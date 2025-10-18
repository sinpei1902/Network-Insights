import streamlit as st
import pandas as pd
import pdfplumber
import re
from openai import AzureOpenAI

def extract_kpi_from_pdf(pdf_path: str):
    """Safely extract KPI data from Power BI export PDF."""
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
        try:
            part = text.split(section)[1]
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


def app():
    st.title("📊 Power BI → AI Business Report")
    st.caption("Reads KPI data from the exported Power BI PDF and generates insights using Azure OpenAI.")

    pdf_path = "dashboard_export.pdf"
    st.info(f"Using Power BI export file: {pdf_path}")

    try:
        df = extract_kpi_from_pdf(pdf_path)
        st.success("✅ Extracted KPI data:")
        st.dataframe(df)
    except Exception as e:
        st.error(f"❌ Failed to read PDF: {e}")
        return

    # Azure setup
    azure = st.secrets 
    client = AzureOpenAI(
        azure_endpoint=azure["AZURE_OPENAI_ENDPOINT"],
        api_key=azure["AZURE_OPENAI_KEY"],
        api_version="2024-02-15-preview"
    )

    # AI prompt
    prompt = f"""
    You are a senior operations analyst. Using the following KPI data extracted from a Power BI report,
    write a clear, actionable performance summary with insights and recommendations.

    Data:
    {df.to_markdown(index=False)}
    """

    st.subheader("🧠 Generating AI Report...")
    response = client.chat.completions.create(
        model=azure["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {"role": "system", "content": "You are an expert operations analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=1,
    )
    report = response.choices[0].message.content

    st.subheader("📄 AI-Generated Business Summary")
    st.write(report)

    with open("business_summary.txt", "w", encoding="utf-8") as f:
        f.write(report)
    st.success("💾 Report saved to business_summary.txt")
