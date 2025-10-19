# autofilter.py
import streamlit as st
import json

def apply_auto_filters(report_id, embed_url, embed_token, filters):
    """Embed Power BI and apply filters automatically on load."""
    html_code = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <script src="https://cdn.jsdelivr.net/npm/powerbi-client@latest/dist/powerbi.min.js"></script>
      </head>
      <body>
        <div style="margin-bottom:10px;">
          <button id="btnApply" style="padding:6px 12px;">⚙️ Apply Auto Filters</button>
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

          // Auto-apply filters on load
          report.on('loaded', async () => {{
            try {{
              await report.setFilters(autoFilters);
              console.log('✅ Auto filters applied on load');
            }} catch (err) {{
              console.error('Filter apply error:', err);
            }}
          }});

          // Manual apply
          document.getElementById("btnApply").onclick = async () => {{
            try {{
              await report.setFilters(autoFilters);
              alert("✅ Filters applied successfully!");
            }} catch (err) {{
              alert("⚠️ Failed to apply filters — check console.");
              console.error(err);
            }}
          }};
        }});
        </script>
      </body>
    </html>
    """
    st.components.v1.html(html_code, height=870, scrolling=True)
