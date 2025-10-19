import streamlit as st
import json
import requests
import database
import exportdata
from exportdata import export_filtered_data

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


