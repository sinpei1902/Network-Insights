import streamlit as st
import requests
import msal

# ===== Power BI Setup =====
pbi = st.secrets["powerbi"]
CLIENT_ID = pbi["client_id"]
CLIENT_SECRET = pbi["client_secret"]
TENANT_ID = pbi["tenant_id"]
WORKSPACE_ID = pbi["workspace_id"]
REPORT_ID = pbi["report_id"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
POWER_BI_API = "https://api.powerbi.com/v1.0/myorg"

@st.cache_data(ttl=3000)
def get_access_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_silent(SCOPE, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=SCOPE)
    return result["access_token"]

def get_embed_info():
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    # Generate embed token
    token_response = requests.post(
        f"{POWER_BI_API}/groups/{WORKSPACE_ID}/reports/{REPORT_ID}/GenerateToken",
        headers=headers,
        json={"accessLevel": "View", "allowSaveAs": "false"}
    )
    if token_response.status_code != 200:
        st.error(f"Error generating embed token: {token_response.text}")
        return None

    token = token_response.json()["token"]

    # Get report info (embedUrl)
    report_info = requests.get(
        f"{POWER_BI_API}/groups/{WORKSPACE_ID}/reports/{REPORT_ID}",
        headers=headers
    ).json()

    embed_url = report_info["embedUrl"]
    return token, embed_url

# ===== Streamlit Page =====
def app():
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
            <div id="reportContainer" style="height:800px;width:100%;"></div>
            <script>
              document.addEventListener("DOMContentLoaded", function() {{
                var models = window['powerbi-client'].models;
                var embedConfig = {{
                    type: 'report',
                    id: '{REPORT_ID}',
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

