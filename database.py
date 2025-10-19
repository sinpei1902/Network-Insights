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
    supabase.table("user_details").update({"role": new_role}).eq("username", username).execute()

def modify_dept(username,new_dept):
    supabase.table("user_details").update({"department": new_dept}).eq("username", username).execute()

def modify_job(username,new_job):
    supabase.table("user_details").update({"job_title": new_job}).eq("username", username).execute()

# File management




def get_files(username):
    result = supabase.table("user_files").select("*").eq("username", username).execute()
    return result.data

def save_file_to_local(filename, output_path="dashboard_export.pdf"):
    file = supabase.table("user_files").select("*").eq("username", st.session_state["username"]).eq("file_name",filename).execute().data[0]
    file_path = file["file_path"]
    st.write(file_path)
    response = supabase.storage.from_("pdfs").download(file_path)

    # Save locally
    with open(output_path, "wb") as f:
        f.write(response)
    print(f"✅ File saved locally as {output_path}")
    return output_path

def add_file_to_db(username, output_path, filename):
    """Upload any file (PDF, CSV, ZIP) to Supabase storage and record in DB."""
    storage_path = f"{username}/{os.path.basename(filename)}"
    bucket = "pdfs"  # or rename to "exports" if you prefer separating file types

    try:
        with open(output_path, "rb") as f:
            res = supabase.storage.from_(bucket).upload(storage_path, f, {"upsert": True})

        # Log upload response
        if hasattr(res, "status_code") and res.status_code >= 400:
            print(f"❌ Upload failed for {filename}: {res}")
            st.error(f"Upload failed: {res}")
            return False

        print(f"✅ Uploaded {filename} to Supabase storage at {storage_path}")

        # Record metadata in SQL table
        insert_result = supabase.table("user_files").insert({
            "username": username,
            "file_name": filename,
            "file_path": storage_path
        }).execute()

        print(f"✅ DB record created for {filename}: {insert_result}")
        return True

    except Exception as e:
        print(f"❌ Error uploading {filename}: {e}")
        st.error(f"Error uploading {filename}: {e}")
        return False




#filters per user 
def add_job_filter(username, job_name, filters):
    supabase.table("user_jobs").insert({
        "username": username,
        "job_name": job_name,
        "filters": filters
    }).execute()

def get_user_jobs(username):
    res = supabase.table("user_jobs").select("*").eq("username", username).execute()
    if res.data:
        return res.data
    return []

#chat management
def create_room(room_name, is_group=False):
    result = supabase.table("rooms").insert({"name": room_name, "is_group": is_group}).execute()
    if not result.data:
        return None
    return result.data[0]["id"]

def add_user_to_room(room_id, username):
    supabase.table("room_members").insert({"room_id": room_id, "username": username}).execute()

import httpx, time
from supabase import create_client

def get_user_rooms(username):
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    supabase = create_client(url, key)

    try:
        result = supabase.table("room_members").select("room_id").eq("username", username).execute()
        if not result.data:
            return []
        room_ids = [r["room_id"] for r in result.data]
        if not room_ids:
            return []
        for _ in range(3):
            try:
                rooms = supabase.table("rooms").select("*").in_("id", room_ids).execute()
                return rooms.data
            except httpx.RemoteProtocolError:
                print("⚠️ Supabase disconnected — retrying...")
                time.sleep(1)
        st.error("❌ Could not retrieve rooms. Supabase connection unstable.")
        return []
    except Exception as e:
        print(f"❌ Error fetching rooms: {e}")
        return []

def add_message(room_id, sender, content):
    supabase.table("messages").insert({
        "room_id": room_id,
        "sender": sender,
        "content": content
    }).execute()


def get_messages(room_id, limit=50):
    result = supabase.table("messages").select("*").eq("room_id", room_id).order("timestamp", desc=True).limit(limit).execute()
    return list(reversed(result.data)) if result.data else []

def get_room_by_name(room_name):
    """Find room by its name"""
    result = supabase.table("rooms").select("*").eq("name", room_name).execute()
    return result.data[0] if result.data else None

def get_room_by_id(room_id):
    """Find room by its id"""
    result = supabase.table("rooms").select("*").eq("id", room_id).execute()
    return result.data[0] if result.data else None

def is_user_in_room(username, room_id):
    """Check if user already in the room"""
    result = supabase.table("room_members").select("*").eq("username", username).eq("room_id", room_id).execute()
    return len(result.data) > 0



