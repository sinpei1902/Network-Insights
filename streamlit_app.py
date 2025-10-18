import streamlit as st
import chat, news, dashboard

st.set_page_config(layout="wide")

dashboard.app()
with st.container(border=True):
    news.app()
with st.container(border=True):
    chat.bot()

