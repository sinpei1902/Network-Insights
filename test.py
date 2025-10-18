import requests, time, io

# =====================
# 🔐 CONFIG
# =====================
tenant_id = "27fa816c-95b5-4431-90d9-4d0ac1986f71"
client_id = "d4513e50-29a7-4f57-a41f-68fae5006b67"
client_secret = "uF08Q~1sS-bSDi4bZe8JuOyPrIZglZ4zRqgKLbMp"
workspace_id = "41675240-7b6e-4163-a0ed-52b5c3b13e01"
report_id = "06bdda3d-459c-4632-8784-d43e6b208aab"

# =====================
# 1️⃣ AUTHENTICATE
# =====================

def app(): 
    print("🔑 Authenticating with Azure AD...")
    token = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default"
        }
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Authenticated!\n")

    # =====================
    # 2️⃣ START EXPORT JOB (PDF)
    # =====================
    export_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/ExportTo"
    payload = {"format": "PDF"}
    print("🚀 Starting export job...")
    job_resp = requests.post(export_url, headers={**headers, "Content-Type": "application/json"}, json=payload)

    print("Export start:", job_resp.status_code)
    print(job_resp.text)

    if job_resp.status_code != 202:
        raise SystemExit("❌ Export job could not be started. Check permissions or format support.")

    job_id = job_resp.json()["id"]
    print("📄 Job ID:", job_id)

    # =====================
    # 3️⃣ POLL JOB STATUS
    # =====================
    # 3️⃣ POLL JOB STATUS (REGIONAL ENDPOINT)
    base = "https://wabi-south-east-asia-d-primary-redirect.analysis.windows.net"
    status_url = f"{base}/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/exports/{job_id}"

    while True:
        resp = requests.get(status_url, headers=headers)
        print("Raw status response:", resp.status_code, resp.text[:200])
        
        if resp.status_code == 200 and resp.text.strip():
            try:
                status_json = resp.json()
                status = status_json.get("status")
                print("📊 Status:", status)
                if status == "Succeeded":
                    download_url = status_json["resourceLocation"]
                    print("✅ Export succeeded! Downloading file...")
                    break
                elif status == "Failed":
                    raise SystemExit("❌ Export failed.")
            except Exception as e:
                print("⚠️ Could not parse JSON:", e)
        else:
            print("⏳ Export not ready, waiting...")

        time.sleep(5)


    # =====================
    # 4️⃣ DOWNLOAD PDF
    # =====================
    pdf_data = requests.get(download_url, headers=headers)
    with open("dashboard_export.pdf", "wb") as f:
        f.write(pdf_data.content)
    print("🎉 Report saved as dashboard_export.pdf")
