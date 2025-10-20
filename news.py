'''import streamlit as st
import requests
import time
import feedparser
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta
from openai import AzureOpenAI
from businessreport import extract_kpi_from_pdf
from powerbi import get_access_token, start_export_job, poll_export_status, download_exported_pdf


# ======================
# 🔐 CONFIG
# ======================
pbi = st.secrets["powerbi"]
client_id = pbi["client_id"]
client_secret = pbi["client_secret"]
tenant_id = pbi["tenant_id"]
workspace_id = pbi["workspace_id"]
report_id = pbi["report_id"]

azure = st.secrets
AZURE_OPENAI_ENDPOINT = azure["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_KEY = azure["AZURE_OPENAI_KEY"]
AZURE_OPENAI_DEPLOYMENT = azure["AZURE_OPENAI_DEPLOYMENT"]

client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-15-preview"
)


# ======================
# 📰 1️⃣ FETCH LATEST NEWS
# ======================
def fetch_news(keywords, days=1, max_results=10):
    """Scrape global news headlines using Google News RSS (no API key needed)."""
    query = "+".join(keywords)
    query_encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={query_encoded}&hl=en-SG&gl=SG&ceid=SG:en"
    feed = feedparser.parse(url)

    articles = []
    for entry in feed.entries[:max_results]:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.get("published", ""),
            "summary": entry.get("summary", "")
        })
    return articles


# ======================
# 📊 2️⃣ EXPORT USER-SPECIFIC POWER BI REPORT
# ======================
def export_user_report(region):
    """Filter Power BI by user region and export to PDF."""
    filters = [{
        "filter": {
            "table": "Vessel",
            "column": "Region",
            "operator": "In",
            "values": [region]
        }
    }]
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    job_id = start_export_job(headers, filters)
    download_url = poll_export_status(headers, job_id)
    download_exported_pdf(headers, download_url, output_path="user_dashboard.pdf")
    return "user_dashboard.pdf"


# ======================
# 🧠 3️⃣ ASSESS RISK BASED ON KPI + NEWS
# ======================
def assess_risk_from_news(news_items, kpi_df, region):
    """Heuristically determine overall risk based on KPIs and news relevance."""
    relevant_news = []
    risk_level = "Low"

    for item in news_items:
        title = item["title"].lower()
        summary = item["summary"].lower()

        # Check if region is mentioned
        if region.lower() in title or region.lower() in summary:
            relevant_news.append(item)

    if not relevant_news:
        return {"risk": "Low", "news": [], "reason": "No relevant news found."}

    # Heuristic: If KPI is weak and relevant news exists → higher risk
    port_savings = kpi_df["Port Time Savings (%)"].iloc[-1]
    if port_savings < 10:
        risk_level = "High"
    elif port_savings < 20:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "risk": risk_level,
        "news": relevant_news,
        "reason": f"Found {len(relevant_news)} relevant news items mentioning {region}. KPI port time savings = {port_savings}%."
    }


# ======================
# 🧾 4️⃣ GENERATE AI SUMMARY
# ======================
def generate_summary(risk_report, region):
    """Use Azure OpenAI to generate an actionable risk summary."""
    news_snippets = "\n".join(
        [f"- {n['title']} ({n['link']})" for n in risk_report["news"]]
    )

    prompt = f"""
You are a maritime logistics risk analyst.

Region: {region}
Overall Risk Level: {risk_report['risk']}
Reason: {risk_report['reason']}

Relevant News:
{news_snippets}

Generate a summary for the user.

If risk is HIGH — immediately propose at least 3 alternate shipping routes and justify each.
If risk is MEDIUM — suggest possible alternate routes and additional mitigation measures.
If risk is LOW — inform the user but no alternate routes are needed.
"""

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are a global logistics and risk analysis expert."},
            {"role": "user", "content": prompt},
        ],
        temperature=1,
    )
    return response.choices[0].message.content


# ======================
# 🚀 5️⃣ STREAMLIT APP
# ======================
def app():
    st.title("📰 Global News Risk Monitor")
    st.caption("Scrapes recent news + Power BI data to assess operational risk and suggest actions.")

    region = st.text_input("Enter your region of responsibility (e.g., East Asia, Europe):", "East Asia")
    keywords = st.text_input("Enter keywords for monitoring:", "port congestion, vessel delays, strike, logistics")

    if st.button("Run News Risk Analysis"):
        st.info("🔎 Fetching latest news...")
        news_items = fetch_news(keywords.split(","))

        st.success(f"✅ Retrieved {len(news_items)} news articles.")
        st.dataframe(pd.DataFrame(news_items)[["title", "published", "link"]])

        st.info("📊 Exporting Power BI report...")
        pdf_path = export_user_report(region)
        kpi_df = extract_kpi_from_pdf(pdf_path)
        st.success("✅ Power BI data extracted.")
        st.dataframe(kpi_df)

        st.info("🧠 Assessing risk...")
        risk_report = assess_risk_from_news(news_items, kpi_df, region)
        st.write(risk_report)

        st.info("✍️ Generating AI summary...")
        summary = generate_summary(risk_report, region)
        st.subheader("📄 AI Risk Summary")
        st.write(summary)

        with open("news_risk_summary.txt", "w", encoding="utf-8") as f:
            f.write(summary)
        st.success("💾 Summary saved to news_risk_summary.txt")


if __name__ == "__main__":
    app()'''
    
    



import streamlit as st
import feedparser
import pandas as pd
import urllib.parse
from datetime import datetime
from openai import AzureOpenAI
import database  # new import

# ======================
# 🔐 CONFIG
# ======================
azure = st.secrets
AZURE_OPENAI_ENDPOINT = azure["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_KEY = azure["AZURE_OPENAI_KEY"]
AZURE_OPENAI_DEPLOYMENT = azure["AZURE_OPENAI_DEPLOYMENT"]

client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-15-preview"
)

# ======================
# 📰 1️⃣ FETCH LATEST NEWS
# ======================
def fetch_news(keywords, max_results=10):
    """Scrape global news headlines using Google News RSS (no API key needed)."""
    query = "+".join(keywords)
    query_encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={query_encoded}&hl=en-SG&gl=SG&ceid=SG:en"
    feed = feedparser.parse(url)

    articles = []
    for entry in feed.entries[:max_results]:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.get("published", ""),
            "summary": entry.get("summary", "")
        })
    return articles

# ======================
# 🧠 2️⃣ ASSESS RISK BASED ON NEWS + AI REPORT
# ======================
def assess_risk_from_news(news_items, ai_report_text, region):
    """Heuristically determine risk based on news relevance and report tone."""
    relevant_news = []
    for item in news_items:
        title = item["title"].lower()
        summary = item["summary"].lower()
        if region.lower() in title or region.lower() in summary:
            relevant_news.append(item)

    report_lower = ai_report_text.lower()
    if any(word in report_lower for word in ["delay", "risk", "inefficiency", "shortfall"]):
        base_risk = "Medium"
    elif any(word in report_lower for word in ["improvement", "strong", "increase", "growth"]):
        base_risk = "Low"
    else:
        base_risk = "Low"

    # escalate risk if there’s a lot of relevant news
    if len(relevant_news) > 3:
        base_risk = "High"

    return {
        "risk": base_risk,
        "news": relevant_news,
        "reason": f"Based on {len(relevant_news)} relevant news articles mentioning {region} and the tone of recent business performance report."
    }

# ======================
# 🧾 3️⃣ GENERATE AI SUMMARY
# ======================
def generate_summary(risk_report, region):
    """Use Azure OpenAI to generate an actionable risk summary."""
    news_snippets = "\n".join(
        [f"- {n['title']} ({n['link']})" for n in risk_report["news"]]
    )

    prompt = f"""
You are a maritime logistics risk analyst.

Region: {region}
Overall Risk Level: {risk_report['risk']}
Reason: {risk_report['reason']}

Relevant News:
{news_snippets}

Generate a summary for the user.

If risk is HIGH — immediately propose at least 3 alternate shipping routes and justify each.
If risk is MEDIUM — suggest possible alternate routes and additional mitigation measures.
If risk is LOW — inform the user but no alternate routes are needed.
"""

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are a global logistics and risk analysis expert."},
            {"role": "user", "content": prompt},
        ],
        temperature=1,
    )
    return response.choices[0].message.content.strip()

# ======================
# 🚀 4️⃣ STREAMLIT APP
# ======================
def app():
    st.title("📰 Global News Risk Monitor")
    st.caption("Scrapes recent news + your latest AI business report to assess operational risk and suggest actions.")

    username = st.session_state.get("username", "guest")
    region = st.text_input("Enter your region of responsibility (e.g., East Asia, Europe):", "East Asia")
    keywords = st.text_input("Enter keywords for monitoring:", "port congestion, vessel delays, strike, logistics")

    if st.button("Run News Risk Analysis"):
        # Step 1: Fetch latest AI report
        st.info("📄 Fetching your latest AI business report...")
        latest_report = database.get_latest_ai_report(username)

        if not latest_report:
            st.warning("⚠️ No AI business report found. Please generate one first in the Business Report page.")
            return

        report_text = latest_report["report_text"]
        st.success(f"✅ Found report: {latest_report['file_name']} (created {latest_report['created_at']})")

        # Step 2: Fetch news
        st.info("🔎 Fetching latest news...")
        news_items = fetch_news(keywords.split(","))
        st.success(f"✅ Retrieved {len(news_items)} news articles.")
        st.dataframe(pd.DataFrame(news_items)[["title", "published", "link"]])

        # Step 3: Assess risk
        st.info("🧠 Assessing risk...")
        risk_report = assess_risk_from_news(news_items, report_text, region)
        st.write(risk_report)

        # Step 4: Generate AI risk summary
        st.info("✍️ Generating AI summary...")
        summary = generate_summary(risk_report, region)
        st.subheader("📄 AI Risk Summary")
        st.write(summary)

        # Save results locally
        with open("news_risk_summary.txt", "w", encoding="utf-8") as f:
            f.write(summary)
        st.success("💾 Summary saved to news_risk_summary.txt")

if __name__ == "__main__":
    app()
