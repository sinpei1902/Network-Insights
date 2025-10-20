import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from openai import AzureOpenAI
from businessreport import extract_kpi_from_pdf


# ======================
# 🔐 AZURE CONFIG
# ======================
def load_azure_client():
    azure = st.secrets
    client = AzureOpenAI(
        azure_endpoint=azure["AZURE_OPENAI_ENDPOINT"],
        api_key=azure["AZURE_OPENAI_KEY"],
        api_version="2024-02-15-preview",
    )
    deployment = azure["AZURE_OPENAI_DEPLOYMENT"]
    return client, deployment


# ======================
# 🧠 AI ANALYSIS
# ======================
def analyze_kpis_with_ai(df: pd.DataFrame, client, deployment: str):
    """Ask Azure OpenAI to classify and rank KPIs for visual priority and color coding."""
    prompt = f"""
You are a dashboard designer.
Here is KPI data from Power BI:

{df.to_markdown(index=False)}

For each KPI column (excluding 'Month'), return a JSON array with:
[
  {{
    "KPI": "Port Time Savings (%)",
    "Importance": 5,
    "Urgency": "High",
    "Color": "red",
    "ChartType": "line",
    "Summary": "Port time efficiency has dropped sharply since April."
  }},
  ...
]
Color rules:
- Red → urgent problem
- Orange → moderate risk
- Green → improving trend
- Blue → neutral or stable
"""

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are an expert business data analyst and visualization designer."},
            {"role": "user", "content": prompt},
        ],
        temperature=1,
    )

    text = response.choices[0].message.content.strip()
    try:
        return pd.read_json(text)
    except Exception:
        st.warning("⚠️ AI output parsing failed. Displaying raw response.")
        st.text(text)
        return None


# ======================
# 🎨 CHART GENERATION
# ======================
def plot_line_chart(df, kpi, color):
    """Line chart for KPI trends."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Month"], y=df[kpi],
        mode="lines+markers",
        line=dict(color=color, width=3),
        marker=dict(size=8),
        name=kpi
    ))
    fig.update_layout(
        title=kpi,
        title_font=dict(size=16, color=color),
        margin=dict(l=30, r=30, t=60, b=30),
        height=300,
        template="plotly_white"
    )
    return fig


def plot_donut_chart(value, label, color):
    """Donut chart for KPI percentage breakdown."""
    fig = go.Figure(data=[
        go.Pie(
            values=[value, 100 - value],
            labels=[label, ""],
            hole=0.6,
            marker_colors=[color, "#EAEAEA"],
            textinfo="none"
        )
    ])
    fig.update_layout(showlegend=False, height=200, margin=dict(l=0, r=0, t=20, b=0))
    return fig


# ======================
# 🚀 STREAMLIT APP
# ======================
def app():
    #st.set_page_config(page_title="AI KPI Dashboard", layout="wide")
    st.title("📊 AI-Generated KPI Dashboard")
    st.caption("Styled report automatically generated from Power BI data via Azure OpenAI.")
    generate()

def generate(pdf_path= "dashboard_export.pdf"):
    st.info(f"Using data from `{pdf_path}`")

    # Extract KPI Data
    try:
        df = extract_kpi_from_pdf(pdf_path)
        st.success("✅ KPI data extracted successfully.")
    except Exception as e:
        st.error(f"❌ Failed to read PDF: {e}")
        return

    st.dataframe(df)

    # AI Analysis
    st.subheader("🧠 Analyzing KPI Importance & Urgency...")
    client, deployment = load_azure_client()
    ai_result = analyze_kpis_with_ai(df, client, deployment)

    if ai_result is None or ai_result.empty:
        st.error("AI analysis failed.")
        return

    ai_result = ai_result.sort_values("Importance", ascending=False).reset_index(drop=True)
    st.subheader("🏅 KPI Priorities")
    st.dataframe(ai_result)

    # ====== LAYOUT ======
    st.markdown("## 📈 Performance Overview")
    top_kpis = ai_result.head(4)  # Top 4 KPIs

    cols = st.columns(2)
    for i, (_, row) in enumerate(top_kpis.iterrows()):
        kpi = row["KPI"]
        color = row["Color"]
        urgency = row["Urgency"]
        summary = row["Summary"]

        with cols[i % 2]:
            st.markdown(f"### {kpi}  —  <span style='color:{color};font-weight:bold'>{urgency}</span>", unsafe_allow_html=True)
            st.plotly_chart(plot_line_chart(df, kpi, color), use_container_width=True)
            st.caption(f"🧾 {summary}")
            st.markdown("---")

    # ====== Donut Overview Section ======
    st.markdown("## 📊 KPI Snapshot")
    donut_cols = st.columns(len(top_kpis))
    for i, (_, row) in enumerate(top_kpis.iterrows()):
        kpi = row["KPI"]
        color = row["Color"]
        avg_value = round(df[kpi].mean(), 1)
        with donut_cols[i]:
            st.plotly_chart(plot_donut_chart(min(avg_value, 100), kpi, color), use_container_width=True)
            st.markdown(f"**{avg_value}%**<br><span style='color:{color}'>{row['Urgency']}</span>", unsafe_allow_html=True)


if __name__ == "__main__":
    app()
