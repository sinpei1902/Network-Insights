import streamlit as st
from supabase import create_client, Client
import bcrypt
import os

url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["anon_key"]
supabase = create_client(url, key)

# User management
def check_username_exists(username):
    result = supabase.table("users").select("id").eq("username", username).execute()
    return len(result.data) > 0

def create_user(username, password):
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    result = supabase.table("users").insert({"username": username, "password_hash": hashed_pw}).execute()
    supabase.table("user_details").insert({"username":username}).execute()
    return len(result.data) > 0

def validate_user(username, entered_password):
    # Get the stored password hash for the username
    result = supabase.table("users").select("password_hash").eq("username", username).execute()
    if not result.data:
        return False  # user not found
    stored_hash = result.data[0]["password_hash"]
    return bcrypt.checkpw(entered_password.encode("utf-8"), stored_hash.encode("utf-8"))

def get_info(username):
    result = supabase.table("user_details").select("*").eq("username", username).execute()
    return result.data[0]

def modify_role(username,new_role):
    supabase.table("user_detailes").update({"role": new_role}).eq("username", username).execute()

def modify_dept(username,new_dept):
    supabase.table("user_detailes").update({"department": new_dept}).eq("username", username).execute()

def modify_job(username,new_job):
    supabase.table("user_detailes").update({"job_title": new_job}).eq("username", username).execute()

# File management

def add_file_to_db(username, output_path, filename):
    #1. upload to supabase storage
    storage_path = f"{username}/{os.path.basename(filename)}"
    with open(output_path, "rb") as f:
        supabase.storage.from_("pdfs").upload(storage_path, f)

    #2. save file path in database
    supabase.table("user_files").insert({
        "username": username,
        "file_name": filename,
        "file_path": storage_path
    }).execute()







