import streamlit as st
import chat, news, businessreport

with st.container(border=True):
    news.app()
with st.container(border=True):
    chat.bot()
with st.container(border=True):
    businessreport.app()
