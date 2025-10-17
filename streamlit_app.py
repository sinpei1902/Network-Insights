import streamlit as st
from openai import AzureOpenAI

st.title("💬 Network Insights Chatbot")

# Load credentials
endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
api_key = st.secrets["AZURE_OPENAI_KEY"]
deployment = st.secrets["AZURE_OPENAI_DEPLOYMENT"]

# This API version comes directly from your documentation
api_version = "2025-01-01-preview"

# Initialise the AzureOpenAI client with your API Management gateway
client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version=api_version
)

# Maintain chat state
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask GPT-5-Mini anything!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Send to the deployed Azure model through API Management
    stream = client.chat.completions.create(
        model=deployment,          # ← "gpt-5-mini"
        messages=st.session_state.messages,
        stream=True,
    )

    with st.chat_message("assistant"):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})
