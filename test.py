import streamlit as st
import requests
import time
import io
import json
import os
import database

# =====================
# 🔐 CONFIGURATION
# =====================
pbi = st.secrets["powerbi"]
client_id = pbi["client_id"]
client_secret = pbi["client_secret"]
tenant_id = pbi["tenant_id"]
workspace_id = pbi["workspace_id"]
report_id = pbi["report_id"]

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


def download_exported_pdf(headers, download_url, output_path="dashboard_export.pdf"):
    """Download the exported Power BI report PDF."""
    print(f"⬇️ Downloading PDF from {download_url} ...")
    pdf_data = requests.get(download_url, headers=headers)

    if pdf_data.status_code != 200:
        raise SystemExit(f"❌ Failed to download PDF: {pdf_data.status_code} {pdf_data.text}")

    with open(output_path, "wb") as f:
        f.write(pdf_data.content)

    database.add_file_to_db(st.session_state["username"],output_path)

    print(f"🎉 Report successfully saved as {output_path}")
    


def app(filters=None):
    """Main app logic for exporting Power BI report."""
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    job_id = start_export_job(headers, filters)
    download_url = poll_export_status(headers, job_id)
    download_exported_pdf(headers, download_url)


if __name__ == "__main__": # only runs when called directly
    # Run export with or without filters
    use_filters = True  # change to False if you want full report export
    app(filters=DYNAMIC_FILTERS if use_filters else None)
