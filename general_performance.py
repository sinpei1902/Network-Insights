import streamlit as st
import database
import io
from powerbi import analyse_zip_with_ai_info

def app():
    #output_path = database.get_main_file()
    #graphs.generate(output_path)
    with st.spinner("🔽 Downloading ZIP from Supabase..."):
        # Download file as bytes
        zip_bytes = database.get_main_zip("main_file.zip")

    if isinstance(zip_bytes, bytes):
        zip_data = io.BytesIO(zip_bytes)
    else:
        zip_data = io.BytesIO(zip_bytes.read())

    # 6️⃣ Pass ZIP to your AI analysis function
    with st.spinner("🤖 Analysing data using Azure OpenAI..."):
        report = analyse_zip_with_ai_info(zip_data)
