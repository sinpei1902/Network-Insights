import streamlit as st
import requests
import os
import json
import time
import zipfile
from datetime import datetime
import database

EXPORTS_DIR = "exports"
os.makedirs(EXPORTS_DIR, exist_ok=True)

# ============================================================
# 🔑 AUTHENTICATION
# ============================================================
def get_access_token(client_id, client_secret, tenant_id):
    token_resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default",
        },
    )
    token_resp.raise_for_status()
    return token_resp.json().get("access_token")


# ============================================================
# 📄 POWER BI EXPORT (PDF)
# ============================================================
def start_export_job(headers, workspace_id, report_id, filters=None):
    """Trigger Power BI Export-to-File job."""
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/ExportTo"
    payload = {"format": "PDF"}
    if filters:
        payload["powerBIReportConfiguration"] = {"filters": filters}
    resp = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=payload)
    resp.raise_for_status()
    return resp.json()["id"]


def poll_export_status(headers, workspace_id, report_id, job_id):
    """Poll until Power BI PDF export job finishes."""
    while True:
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/exports/{job_id}"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "Succeeded":
            return data["resourceLocation"]
        elif status == "Failed":
            raise RuntimeError("Power BI PDF export failed.")
        time.sleep(5)


def download_exported_pdf(headers, download_url, output_path):
    """Download the generated PDF."""
    resp = requests.get(download_url, headers=headers)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)
    return output_path


# ============================================================
# 📦 ZIP CREATION
# ============================================================
def create_zip_bundle(username, job_name, files):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{username}_{job_name}_{timestamp}.zip"
    zip_path = os.path.join(EXPORTS_DIR, zip_filename)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for fpath in files:
            zf.write(fpath, os.path.basename(fpath))
    return zip_path


# ============================================================
# 🚀 FULL EXPORT PIPELINE (CSV + PDF)
# ============================================================
def export_filtered_data(client_id, client_secret, tenant_id, workspace_id, report_id,
                         username, job_name, filters, exported_data):
    """Handles both CSV + PDF export, and uploads to DB."""
    local_files = []

    # Save CSV files
    for title, csv_text in exported_data.items():
        safe_name = title.replace(" ", "_").replace("/", "_")
        file_path = os.path.join(EXPORTS_DIR, f"{safe_name}.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(csv_text)
        local_files.append(file_path)

    # Generate filtered PDF
    access_token = get_access_token(client_id, client_secret, tenant_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    job_id = start_export_job(headers, workspace_id, report_id, filters)
    download_url = poll_export_status(headers, workspace_id, report_id, job_id)
    pdf_path = os.path.join(EXPORTS_DIR, f"{job_name}_dashboard.pdf")
    download_exported_pdf(headers, download_url, pdf_path)
    local_files.append(pdf_path)

    # Bundle into ZIP
    zip_path = create_zip_bundle(username, job_name, local_files)

    # Upload ZIP to database
    upload_success = database.add_file_to_db(username, zip_path, os.path.basename(zip_path))
    if upload_success:
        st.success(f"✅ Export complete! Uploaded ZIP: {os.path.basename(zip_path)}")
    else:
        st.warning("⚠️ ZIP saved locally but upload failed.")

    return zip_path
