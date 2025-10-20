import streamlit as st
from openai import AzureOpenAI

def bot():
    st.title("🌊 PSA Chatbot")
    st.caption("Your AI assistant for maritime insights, port operations, and global logistics strategy.")

    # Azure OpenAI setup
    endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
    api_key = st.secrets["AZURE_OPENAI_KEY"]
    deployment = st.secrets["AZURE_OPENAI_DEPLOYMENT"]
    api_version = "2025-01-01-preview"

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version
    )

    # Chat state
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert assistant for PSA International’s Global Strategy Division. "
                    "You specialize in maritime logistics, port management, shipping economics, "
                    "and digital transformation. Provide concise, analytical, and globally informed insights. "
                    "Explain in business terms for executive-level planning."
                )
            }
        ]

    # Display past chat safely
    for m in st.session_state.messages:
        # Ensure m is a dict with expected structure
        if not isinstance(m, dict) or "role" not in m or "content" not in m:
            continue  # skip invalid items

        if m["role"] not in ["user", "assistant"]:
            continue  # skip system messages

        with st.chat_message(m["role"]):
            st.markdown(m["content"])


    # Chat input
    if prompt := st.chat_input("Ask about port strategy, digitalisation, or logistics insights..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # --- Validate and rebuild messages before sending to API ---
        valid_messages = []
        for m in st.session_state.messages:
            if isinstance(m, dict) and "role" in m and "content" in m:
                valid_messages.append(m)

        # Always ensure there's at least one system message
        if not valid_messages or valid_messages[0]["role"] != "system":
            valid_messages.insert(0, {
                "role": "system",
                "content": (
                    "You are an expert assistant for PSA International’s Global Strategy Division. "
                    "You specialize in maritime logistics, port management, shipping economics, "
                    "and digital transformation. Provide concise, analytical, and globally informed insights."
                )
            })

        # --- Call the model safely ---
        stream = client.chat.completions.create(
            model=deployment,
            messages=valid_messages,
            stream=True,
            max_completion_tokens=1000
        )

        response = st.write_stream(stream)

        st.session_state.messages.append({"role": "assistant", "content": response})

    st.markdown("---")
    if st.button("🧹 Clear Chat"):
        st.session_state.messages = st.session_state.messages[:1]  # keep system
        st.rerun()
