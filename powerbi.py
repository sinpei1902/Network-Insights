import streamlit as st
import requests
import time
import io
import json
import os
import database
from datetime import datetime
import msal
from openai import AzureOpenAI
import zipfile
import pandas as pd

# =====================
# 🔐 CONFIGURATION
# =====================
pbi = st.secrets["powerbi"]
client_id = pbi["client_id"]
client_secret = pbi["client_secret"]
tenant_id = pbi["tenant_id"]
workspace_id = pbi["workspace_id"]
report_id = pbi["report_id"]

AUTHORITY = f"https://login.microsoftonline.com/{tenant_id}"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
POWER_BI_API = "https://api.powerbi.com/v1.0/myorg"

#DASHBOARD
def get_embed_info():
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    # Generate embed token
    token_response = requests.post(
        f"{POWER_BI_API}/groups/{workspace_id}/reports/{report_id}/GenerateToken",
        headers=headers,
        json={"accessLevel": "View", "allowSaveAs": "false"}
    )
    if token_response.status_code != 200:
        st.error(f"Error generating embed token: {token_response.text}")
        return None

    token = token_response.json()["token"]

    # Get report info (embedUrl)
    report_info = requests.get(
        f"{POWER_BI_API}/groups/{workspace_id}/reports/{report_id}",
        headers=headers
    ).json()

    embed_url = report_info["embedUrl"]
    return token, embed_url

def dashboard():
    st.title("📊 Power BI Embedded Dashboard")

    with st.spinner("🔄 Connecting to Power BI..."):
        embed_info = get_embed_info()

    if embed_info:
        token, embed_url = embed_info
        st.success("✅ Connected to Power BI!")

        html_code = f"""
        <!DOCTYPE html>
        <html>
          <head>
            <script src="https://cdn.jsdelivr.net/npm/powerbi-client@latest/dist/powerbi.min.js"></script>
          </head>
          <body>
            <div id="reportContainer" style="height:400px;width:100%;"></div>
            <script>
              document.addEventListener("DOMContentLoaded", function() {{
                var models = window['powerbi-client'].models;
                var embedConfig = {{
                    type: 'report',
                    id: '{report_id}',
                    embedUrl: '{embed_url}',
                    accessToken: '{token}',
                    tokenType: models.TokenType.Embed,
                    settings: {{
                        panes: {{
                            filters: {{ visible: false }},
                            pageNavigation: {{ visible: true }}
                        }}
                    }}
                }};
                var reportContainer = document.getElementById('reportContainer');
                powerbi.embed(reportContainer, embedConfig);
              }});
            </script>
          </body>
        </html>
        """

        st.components.v1.html(html_code, height=800, scrolling=True)
    else:
        st.error("⚠️ Could not load Power BI report.")



#EXPORT

# Optional: provide a Power BI filter dynamically
# Example: only export data for vessels in "Singapore"
DYNAMIC_FILTERS = [
    {
        "filter": {
            "table": "Vessel",
            "column": "Region",
            "operator": "In",
            "values": ["Singapore"]
        }
    }
]


def get_access_token():
    """Authenticate with Azure AD and get an access token for Power BI REST API."""
    print("🔑 Authenticating with Azure AD...")
    token_resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default"
        }
    )

    if token_resp.status_code != 200:
        raise SystemExit(f"❌ Authentication failed: {token_resp.text}")

    access_token = token_resp.json().get("access_token")
    print("✅ Authenticated successfully!\n")
    return access_token


def start_export_job(headers, filters=None):
    """Start Power BI report export job (PDF) with optional filters."""
    export_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/ExportTo"
    payload = {"format": "PDF"}

    if filters:
        payload["powerBIReportConfiguration"] = {"filters": filters}

    print("🚀 Starting export job...")
    job_resp = requests.post(export_url, headers={**headers, "Content-Type": "application/json"}, json=payload)

    print("Export start:", job_resp.status_code)
    print(job_resp.text)

    if job_resp.status_code != 202:
        raise SystemExit("❌ Export job could not be started. Check permissions or format support.")

    job_id = job_resp.json()["id"]
    print(f"📄 Export Job ID: {job_id}\n")
    return job_id


def poll_export_status(headers, job_id):
    """Poll export job status until it succeeds or fails."""
    base = "https://wabi-south-east-asia-d-primary-redirect.analysis.windows.net"
    status_url = f"{base}/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/exports/{job_id}"

    print("⏳ Checking export status... (polling every 5 seconds)")
    while True:
        resp = requests.get(status_url, headers=headers)

        if resp.status_code != 200:
            print(f"⚠️ Unexpected response ({resp.status_code}): {resp.text}")
            time.sleep(5)
            continue

        try:
            status_json = resp.json()
            status = status_json.get("status")
        except Exception:
            print("⚠️ Could not parse response JSON, retrying...")
            time.sleep(5)
            continue

        print(f"📊 Export Status: {status}")

        if status == "Succeeded":
            print("✅ Export succeeded!")
            return status_json["resourceLocation"]
        elif status == "Failed":
            raise SystemExit("❌ Export failed.")
        else:
            time.sleep(5)


def download_exported_pdf(headers, download_url, filename=None, output_path="dashboard_export.pdf"):
    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"report_{timestamp}.pdf"
    """Download the exported Power BI report PDF."""
    print(f"⬇️ Downloading PDF from {download_url} ...")
    pdf_data = requests.get(download_url, headers=headers)

    if pdf_data.status_code != 200:
        raise SystemExit(f"❌ Failed to download PDF: {pdf_data.status_code} {pdf_data.text}")

    with open(output_path, "wb") as f:
        f.write(pdf_data.content)

    database.add_file_to_db(st.session_state["username"],output_path,filename)

    st.write(f"🎉 Report successfully saved as {filename}")
    
def export(filters=None):
    """Main app logic for exporting Power BI report."""
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    job_id = start_export_job(headers, filters)
    download_url = poll_export_status(headers, job_id)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"report_{timestamp}.pdf"
    download_exported_pdf(headers, download_url,filename)

import streamlit as st
import requests
import os
from supabase import create_client

# ======================================================
# 🔑 POWER BI AUTHENTICATION (Service Principal)
# ======================================================
def get_access_token(client_id, client_secret, tenant_id):
    """Get Azure AD token for Power BI REST API."""
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://analysis.windows.net/powerbi/api/.default"
    }
    resp = requests.post(token_url, data=payload)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_embed_info(client_id, client_secret, tenant_id, workspace_id, report_id):
    """Fetch Power BI embed URL + token."""
    access_token = get_access_token(client_id, client_secret, tenant_id)
    headers = {"Authorization": f"Bearer {access_token}"}

    # Get Embed URL
    report_resp = requests.get(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}",
        headers=headers
    )
    report_resp.raise_for_status()
    embed_url = report_resp.json()["embedUrl"]

    # Generate Embed Token
    token_resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/GenerateToken",
        headers={**headers, "Content-Type": "application/json"},
        json={"accessLevel": "View"}
    )
    token_resp.raise_for_status()
    embed_token = token_resp.json()["token"]
    return embed_url, embed_token


# ======================================================
# 🎛️ STREAMLIT APP: Power BI Embed + Export ZIP
# ======================================================
def app():
    st.title("📊 Power BI Dashboard — Export All Visuals as CSV (ZIP)")

    pbi = st.secrets["powerbi"]
    client_id = pbi["client_id"]
    client_secret = pbi["client_secret"]
    tenant_id = pbi["tenant_id"]
    workspace_id = pbi["workspace_id"]
    report_id = pbi["report_id"]

    embed_url, embed_token = get_embed_info(client_id, client_secret, tenant_id, workspace_id, report_id)

    # ======================================================
    # 💡 FRONTEND HTML (with JSZIP for zipping CSVs)
    # ======================================================
    html_code = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <script src="https://cdn.jsdelivr.net/npm/powerbi-client@latest/dist/powerbi.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/file-saver@2.0.5/dist/FileSaver.min.js"></script>
      </head>
      <body style="font-family:sans-serif">
        <div style="display:flex;gap:10px;margin-bottom:10px;">
          <button id="btnExport" style="padding:8px 16px;">📤 Export All Visuals → ZIP</button>
        </div>
        <div id="reportContainer" style="height:800px;width:100%;border:1px solid #ccc;"></div>

        <script>
        document.addEventListener("DOMContentLoaded", async function() {{
          const models = window['powerbi-client'].models;
          const embedConfig = {{
            type: 'report',
            id: '{report_id}',
            embedUrl: '{embed_url}',
            accessToken: '{embed_token}',
            tokenType: models.TokenType.Embed,
            settings: {{
              panes: {{
                filters: {{ visible: true }},
                pageNavigation: {{ visible: true }}
              }}
            }}
          }};

          const report = powerbi.embed(document.getElementById('reportContainer'), embedConfig);

          // 🔽 Export all visuals → ZIP
          document.getElementById("btnExport").onclick = async () => {{
            const zip = new JSZip();
            let exportedCount = 0;

            try {{
              const pages = await report.getPages();
              for (const page of pages) {{
                const visuals = await page.getVisuals();
                for (const v of visuals) {{
                  try {{
                    const data = await v.exportData(models.ExportDataType.Summarized);
                    const fileName = 
                      `${{page.displayName || page.name}}_${{v.title || v.name}}`
                      .replace(/[\\/:*?"<>|]/g, "_") + ".csv";
                    zip.file(fileName, data.data);
                    exportedCount++;
                  }} catch (err) {{
                    console.warn("⚠️ Skipped visual:", v.title);
                  }}
                }}
              }}

              if (exportedCount === 0) {{
                alert("⚠️ No exportable visuals found.");
                return;
              }}

              const blob = await zip.generateAsync({{ type: "blob" }});
              const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
              saveAs(blob, `PowerBI_Export_${{timestamp}}.zip`);
              alert(`✅ Exported ${{exportedCount}} visuals as CSV (zipped).`);
            }} catch (error) {{
              console.error("❌ Export failed:", error);
              alert("❌ Export failed. See console for details.");
            }}
          }};
        }});
        </script>
      </body>
    </html>
    """

    st.components.v1.html(html_code, height=870, scrolling=True)

    st.info("💡 Click the '📤 Export All Visuals → ZIP' button in the embedded report to download all visuals as CSV inside one ZIP file.")
    ai_analysis_ui()

# ======================================================
# 🚀 RUN STANDALONE
# ======================================================



# ======================================================
# 🤖 Azure OpenAI Client Setup
# ======================================================
AZURE_ENDPOINT = st.secrets["AZURE_OPENAI_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_OPENAI_KEY"]
AZURE_DEPLOYMENT = st.secrets["AZURE_OPENAI_DEPLOYMENT"]

client = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_key=AZURE_KEY,
    api_version="2024-05-01-preview"
)

# ======================================================
# 🧠 Function: Analyse ZIP using Azure OpenAI
# ======================================================
def analyse_zip_with_ai(zip_file):
    """Extracts CSVs from ZIP and sends summaries to Azure OpenAI for analysis."""
    with zipfile.ZipFile(zip_file) as z:
        csv_files = [f for f in z.namelist() if f.endswith(".csv")]

        if not csv_files:
            return "⚠️ No CSV files found in the ZIP."

        summaries = []
        for file_name in csv_files:
            with z.open(file_name) as f:
                df = pd.read_csv(f)
                # Limit to preview if large
                preview = df.head(10).to_csv(index=False)
                summaries.append(f"### {file_name}\n{preview}")

        combined_summary = "\n\n".join(summaries)

    prompt = f"""
You are a business intelligence analyst. 
Below are multiple CSV datasets exported from a Power BI dashboard. 
Each CSV corresponds to a visual showing business metrics such as sales, performance, or operations.

Your task:
1. Interpret the data.
2. Identify trends, insights, anomalies, and performance summaries.
3. Provide actionable recommendations and an executive summary.

Use structured sections (Overview, Key Metrics, Insights, Recommendations).

Data Preview:
{combined_summary}
"""

    st.info("🧠 Analysing with Azure OpenAI, please wait...")
    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are an expert business intelligence analyst."},
            {"role": "user", "content": prompt}
        ],
        #temperature=0.4,
        max_completion_tokens=3000
    )

    report_text = response.choices[0].message.content
    return report_text


# ======================================================
# 📦 Streamlit UI for AI Analysis
# ======================================================
def ai_analysis_ui():
    st.header("🤖 AI Business Report Generator")

    uploaded_zip = st.file_uploader("📂 Upload your Power BI Export ZIP (CSV files inside)", type=["zip"])

    if uploaded_zip:
        st.success("✅ ZIP uploaded successfully!")

        if st.button("🧩 Analyse with Azure OpenAI"):
            try:
                report = analyse_zip_with_ai(uploaded_zip)
                st.subheader("📋 AI-Generated Business Report")
                st.markdown(report)

                # Allow download as text
                report_file = io.BytesIO(report.encode("utf-8"))
                st.download_button("⬇️ Download Report", report_file, file_name="business_report.txt")
            except Exception as e:
                st.error(f"❌ Error analysing ZIP: {e}")
    else:
        st.info("Please upload a ZIP file exported from your Power BI dashboard.")


if __name__ == "__main__": # only runs when called directly
    # Run export with or without filters
    use_filters = True  # change to False if you want full report export
    app(filters=DYNAMIC_FILTERS if use_filters else None)


