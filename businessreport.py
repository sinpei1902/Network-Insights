"""
Power BI REST API + OpenAI Integration
--------------------------------------
This script connects to a Power BI Embedded workspace using
Service Principal authentication, fetches live data, and generates
a professional business report with GPT.
"""

import requests
import pandas as pd
import json
import os
from openai import OpenAI

def app():
    # -------------------------------------------------
    # 1️⃣ CONFIGURATION — ENTER YOUR CREDENTIALS HERE
    # -------------------------------------------------
    TENANT_ID = "27fa816c-95b5-4431-90d9-4d0ac1986f71"
    CLIENT_ID = "d4513e50-29a7-4f57-a41f-68fae5006b67"
    CLIENT_SECRET = "uF08Q~1sS-bSDi4bZe8JuOyPrIZglZ4zRqgKLbMp"

    WORKSPACE_ID = "41675240-7b6e-4163-a0ed-52b5c3b13e01"
    REPORT_ID = "06bdda3d-459c-4632-8784-d43e6b208aab"

    OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    client = OpenAI()

    # -------------------------------------------------
    # 2️⃣ AUTHENTICATE TO MICROSOFT (Get Access Token)
    # -------------------------------------------------
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://analysis.windows.net/powerbi/api/.default"
    }

    token_response = requests.post(token_url, data=token_data)
    access_token = token_response.json().get("access_token")

    if not access_token:
        raise Exception("Failed to authenticate with Azure AD. Check credentials.")

    headers = {"Authorization": f"Bearer {access_token}"}

    print("✅ Successfully authenticated with Power BI Service")

    # -------------------------------------------------
    # 3️⃣ FETCH DATASETS AND TABLES
    # -------------------------------------------------
    datasets_url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets"
    datasets_resp = requests.get(datasets_url, headers=headers).json()

    print("\n📊 Available Datasets:")
    print(json.dumps(datasets_resp, indent=2))

    # Extract one dataset ID (for demonstration)
    dataset_id = datasets_resp["value"][0]["id"]

    # -------------------------------------------------
    # 4️⃣ QUERY A TABLE OR METRICS (using DAX query)
    # -------------------------------------------------
    query_url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{dataset_id}/executeQueries"

    # Example DAX query (replace with your actual table or measure names)
    query_body = {
        "queries": [
            {
                "query": """
                EVALUATE
                SUMMARIZECOLUMNS(
                    'Network'[Month],
                    "PortTimeSavings", AVERAGE('Network'[PortTimeSavings]),
                    "ArrivalAccuracy", AVERAGE('Network'[ArrivalAccuracy]),
                    "BunkerSavingsUSD", SUM('Network'[BunkerSavingsUSD]),
                    "CarbonAbatement", SUM('Network'[CarbonAbatement])
                )
                """
            }
        ]
    }

    data_resp = requests.post(query_url, headers=headers, json=query_body)
    data_json = data_resp.json()

    # Convert to DataFrame if successful
    if "results" in data_json:
        table = data_json["results"][0]["tables"][0]
        df = pd.DataFrame(table["rows"])
    else:
        print("⚠️ Could not query dataset, showing structure:")
        print(json.dumps(data_json, indent=2))
        df = pd.DataFrame()

    print("\n✅ Data retrieved from Power BI:")
    print(df.head())

    # -------------------------------------------------
    # 5️⃣ GENERATE BUSINESS REPORT USING OPENAI
    # -------------------------------------------------
    prompt = f"""
    You are a business analyst reviewing network performance data
    fetched from Power BI. Generate a clear and actionable report.

    DATA SAMPLE:
    {df.to_markdown(index=False)}

    TASK:
    1. Summarize key performance insights.
    2. Identify trends and problem areas.
    3. Recommend strategies or operational improvements.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert operations and data analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    report = response.choices[0].message.content

    print("\n📄 AI-GENERATED REPORT\n")
    print(report)

    with open("powerbi_auto_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    print("\nReport saved to powerbi_auto_report.txt ✅")
