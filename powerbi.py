'''import streamlit as st
import json
import requests
import database
import exportdata
from exportdata import export_filtered_data
import os
from supabase import create_client

# ============================================================
# 🔑 POWER BI AUTH / EMBED
# ============================================================
def get_embed_info(client_id, client_secret, tenant_id, workspace_id, report_id):
    """Authenticate and return Power BI embed token + URL."""
    access_token = exportdata.get_access_token(client_id, client_secret, tenant_id)
    headers = {"Authorization": f"Bearer {access_token}"}

    # Get embed URL
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
    return embed_token, embed_url


# ============================================================
# 🎛️ STREAMLIT DASHBOARD
# ============================================================
def app():
    st.title("📊 Power BI Dashboard — Filter + Export Automation")

    pbi = st.secrets["powerbi"]
    client_id = pbi["client_id"]
    client_secret = pbi["client_secret"]
    tenant_id = pbi["tenant_id"]
    workspace_id = pbi["workspace_id"]
    report_id = pbi["report_id"]

    username = st.session_state.get("username", "demo_user")
    jobs = database.get_user_jobs(username)

    if not jobs:
        st.warning("No saved filters found. Please create one first.")
        return

    job_names = [job["job_name"] for job in jobs]
    selected_job = st.selectbox("Select a filter set:", job_names)
    job = next(j for j in jobs if j["job_name"] == selected_job)
    filters = job["filters"]

    embed_token, embed_url = get_embed_info(client_id, client_secret, tenant_id, workspace_id, report_id)
    

    # ============================================================
    # 💡 FRONTEND EMBED + EXPORT HANDLER
    # ============================================================
    html_code = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <script src="https://cdn.jsdelivr.net/npm/powerbi-client@latest/dist/powerbi.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/file-saver@2.0.5/dist/FileSaver.min.js"></script>
      </head>
      <body style="font-family:sans-serif">
        <div style="display:flex;gap:10px;margin-bottom:8px;">
          <button id="btnFilter" style="padding:6px 12px;">⚙️ Apply Auto Filters</button>
          <button id="btnExport" style="padding:6px 12px;">📤 Export All Visuals + PDF</button>
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
          const container = document.getElementById('reportContainer');
          const report = powerbi.embed(container, embedConfig);

          const autoFilters = {json.dumps(filters)};

          // --- Auto-apply filters when loaded ---
          report.on('loaded', async () => {{
            try {{
              await report.setFilters(autoFilters);
              console.log('✅ Auto filters applied');
            }} catch (err) {{
              console.error('❌ Filter error:', err);
            }}
          }});

          // --- Reapply manually ---
          document.getElementById("btnFilter").onclick = async () => {{
            try {{
              await report.setFilters(autoFilters);
              alert("✅ Filters reapplied successfully!");
            }} catch (err) {{
              alert("⚠️ Filter apply failed. Check console.");
              console.error(err);
            }}
          }};

          // --- Export all visuals + send to backend ---
          document.getElementById("btnExport").onclick = async () => {{
            try {{
              const pages = await report.getPages();
              const exportData = {{}};

              for (const page of pages) {{
                const visuals = await page.getVisuals();
                for (const v of visuals) {{
                  try {{
                    const data = await v.exportData(models.ExportDataType.Summarized);
                    exportData[v.title || v.name] = data.data;
                  }} catch (e) {{
                    console.warn("Skipped non-exportable visual:", v.title);
                  }}
                }}
              }}

              // send exported CSVs to backend
              window.parent.postMessage({{
                type: "streamlit:setComponentValue",
                value: JSON.stringify(exportData)
              }}, "*");

              alert("📦 Export complete! Backend will generate ZIP and PDF.");
            }} catch (err) {{
              alert("⚠️ Export failed. Check console.");
              console.error(err);
            }}
          }};
        }});
        </script>
      </body>
    </html>
    """
    
    exported_data = st.components.v1.html(html_code, height=870, scrolling=True)

    # ============================================================
    # 🧩 BACKEND: SAVE CSVs + GENERATE PDF + ZIP
    # ============================================================
    if isinstance(exported_data, str) and exported_data.strip():
        try:
            export_dict = json.loads(exported_data)
            export_filtered_data(
                client_id, client_secret, tenant_id,
                workspace_id, report_id,
                username, selected_job, filters, export_dict
            )
        except Exception as e:
            st.error(f"⚠️ Export failed: {e}")


if __name__ == "__main__":
    app()
'''

'''import streamlit as st
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

# ======================================================
# 🚀 RUN STANDALONE
# ======================================================
if __name__ == "__main__":
    app()
'''
import streamlit as st
import requests
import json
import os
import time
from datetime import datetime
from supabase import create_client

EXPORTS_DIR = "exports"
os.makedirs(EXPORTS_DIR, exist_ok=True)


# ======================================================
# 🔑 Power BI Auth (Service Principal)
# ======================================================
def get_access_token(client_id, client_secret, tenant_id):
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


# ======================================================
# 📄 Power BI Export Job
# ======================================================
def start_export_job(headers, workspace_id, report_id, filters=None):
    """Start Power BI export job (PDF) with optional filters."""
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/ExportTo"
    payload = {"format": "PDF"}

    # Include filters if provided
    if filters:
        payload["powerBIReportConfiguration"] = {"filters": filters}

    # 🩹 Always ensure we have a proper 'Bearer <token>' string
    token = headers.get("Authorization", "")
    if isinstance(token, bool) or not isinstance(token, str):
        # Try to rebuild token if malformed
        token = f"Bearer {headers.get('access_token', '')}" if "access_token" in headers else ""
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"

    # 🩹 Now rebuild headers cleanly with correct types
    safe_headers = {
        "Authorization": str(token),
        "Content-Type": "application/json"
    }

    print("🚀 Starting export job to Power BI...")
    print("Payload:", json.dumps(payload, indent=2))

    resp = requests.post(url, headers=safe_headers, json=payload)

    if resp.status_code != 202:
        raise RuntimeError(f"❌ Export failed ({resp.status_code}): {resp.text}")

    job_id = resp.json()["id"]
    print(f"✅ Export job started (ID: {job_id})")
    return job_id



def poll_export_status(headers, workspace_id, report_id, job_id):
    while True:
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/exports/{job_id}"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "Succeeded":
            return data["resourceLocation"]
        elif data["status"] == "Failed":
            raise RuntimeError("❌ Export job failed.")
        time.sleep(5)


def download_pdf(headers, download_url, filename):
    resp = requests.get(download_url, headers=headers)
    resp.raise_for_status()
    output_path = os.path.join(EXPORTS_DIR, filename)
    with open(output_path, "wb") as f:
        f.write(resp.content)
    return output_path


# ======================================================
# ☁️ Upload to Supabase
# ======================================================
def upload_to_supabase(local_path, filename):
    sb = st.secrets["supabase"]
    supabase = create_client(sb["url"], sb["anon_key"])
    with open(local_path, "rb") as f:
        supabase.storage.from_("exports").upload(filename, f, {"upsert": True})
    return True


# ======================================================
# 🎛️ Streamlit App
# ======================================================
def app():
    st.title("📊 Power BI Dashboard — Filter-Aware PDF Export")

    pbi = st.secrets["powerbi"]
    client_id = pbi["client_id"]
    client_secret = pbi["client_secret"]
    tenant_id = pbi["tenant_id"]
    workspace_id = pbi["workspace_id"]
    report_id = pbi["report_id"]

    access_token = get_access_token(client_id, client_secret, tenant_id)
    headers = {"Authorization": f"Bearer {access_token}"}


    # Get embed info
    report_info = requests.get(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}",
        headers=headers
    ).json()
    embed_url = report_info["embedUrl"]
    embed_token = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/GenerateToken",
        headers={**headers, "Content-Type": "application/json"},
        json={"accessLevel": "View"}
    ).json()["token"]

    st.markdown("### 📈 Embedded Power BI Dashboard")

    # ============================================
    # HTML + JS: Send filters via postMessage
    # ============================================
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/powerbi-client@latest/dist/powerbi.min.js"></script>
    </head>
    <body style="font-family:sans-serif">
        <button id="btnSendFilters" style="padding:6px 12px;margin-bottom:8px;">📤 Send Filters to Streamlit</button>
        <div id="reportContainer" style="height:800px;width:100%;border:1px solid #ccc;"></div>

        <script>
          const models = window['powerbi-client'].models;
          const report = powerbi.embed(document.getElementById('reportContainer'), {{
            type: 'report',
            id: '{report_id}',
            embedUrl: '{embed_url}',
            accessToken: '{embed_token}',
            tokenType: models.TokenType.Embed,
            settings: {{
              panes: {{ filters: {{ visible: true }}, pageNavigation: {{ visible: true }} }}
            }}
          }});

          document.getElementById("btnSendFilters").onclick = async () => {{
            try {{
              const filters = await report.getFilters();
              window.parent.postMessage({{ type: "FROM_PBI_FILTERS", value: filters }}, "*");
              alert("✅ Filters sent to Streamlit!");
            }} catch (err) {{
              alert("❌ Failed to fetch filters: " + err);
            }}
          }};
        </script>
    </body>
    </html>
    """

    # Container
    st.components.v1.html(html_code, height=900, scrolling=True)

    # ============================================
    # JS listener inside Streamlit (via st.markdown)
    # ============================================
    st.markdown(
        """
        <script>
        window.addEventListener("message", (event) => {
            if (event.data && event.data.type === "FROM_PBI_FILTERS") {
                const filters = JSON.stringify(event.data.value);
                window.parent.postMessage({type: "SET_STREAMLIT_FILTERS", value: filters}, "*");
            }
        });
        </script>
        """,
        unsafe_allow_html=True,
    )

    # Simulate a bridge (we can use query params or session state)
    filters_raw = st.text_area("📦 Paste Filters JSON (auto-filled soon):", value=st.session_state.get("filters_raw", ""), height=150)

    if filters_raw:
        try:
            parsed_filters = json.loads(filters_raw)
            st.success("✅ Parsed filters detected!")
        except Exception as e:
            st.warning(f"⚠️ Could not parse filters: {e}")
            parsed_filters = None
    else:
        parsed_filters = None

    if st.button("📄 Export PDF Snapshot"):
        try:
            st.write("DEBUG headers:", headers)
            job_id = start_export_job(headers, workspace_id, report_id, filters=parsed_filters)
            st.write("⏳ Waiting for Power BI export to complete...")
            download_url = poll_export_status(headers, workspace_id, report_id, job_id)
            filename = f"PowerBI_Filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            path = download_pdf(headers, download_url, filename)
            upload_to_supabase(path, filename)
            st.success(f"✅ Exported and uploaded to Supabase: {filename}")
            with open(path, "rb") as f:
                st.download_button("⬇️ Download PDF", f, file_name=filename)
        except Exception as e:
            st.error(f"❌ Export failed: {e}")


# ======================================================
if __name__ == "__main__":
    app()

