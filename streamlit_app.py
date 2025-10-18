import streamlit as st
import chat, news

with st.container(border=True):
    news.app()
with st.container(border=True):
    chat.bot()
