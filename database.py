import streamlit as st
from supabase import create_client

url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["anon_key"]
supabase = create_client(url, key)

# User management
def check_username_exists(username):
    result = supabase.table("users").select("id").eq("username", username).execute()
    return len(result.data) > 0

def create_user(username, password):
    result = supabase.table("users").insert({"username": username, "password_hash": password}).execute()
    return len(result.data) > 0

def validate_user(username, entered_password):
    result = supabase.table("users").select("*").eq("username", username).eq("password_hash", entered_password).execute()
    return len(result.data) > 0

