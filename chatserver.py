'''from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room
import database

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ======================================================
# EVENTS
# ======================================================

@socketio.on("connect")
def handle_connect():
    print(f"✅ Client connected: {request.sid}")

@socketio.on("disconnect")
def handle_disconnect():
    print(f"❌ Client disconnected: {request.sid}")

#@socketio.on("join_room")
#def handle_join_room(data):
#    room_id = data["room_id"]
#    username = data["username"]

#    print(f"👤 {username} joined room {room_id}")
#    join_room(room_id)

#    # Fetch history and send it to the user only
#    messages = database.get_messages(room_id)
#    emit("chat_history", messages, room=request.sid)
#
#    # Notify others (optional)
#    emit("system_message", {"content": f"{username} joined the room."}, room=room_id, include_self=False)

import time


@socketio.on("join_room")
def handle_join_room(data):
    room_id = data["room_id"]
    username = data["username"]

    print(f"👤 {username} joined room {room_id}")
    join_room(room_id)  # ✅ critical line — adds user to that Socket.IO room

    # Fetch chat history and send to the user who joined
    messages = database.get_messages(room_id)
    emit("chat_history", messages, room=request.sid)

    # Notify others in the room
    emit("system_message", {"content": f"{username} joined the chat."}, room=room_id, include_self=False)


#@socketio.on("send_message")
#def handle_send_message(data):
#    room_id = data["room_id"]
#    sender = data["sender"]
#    content = data["content"]
#
#    print(f"💬 {sender} in {room_id}: {content}")
#
#    # Save to DB
#    database.add_message(room_id, sender, content)
#
#    # Broadcast to everyone in the room
#    emit("new_message", {"sender": sender, "content": content}, room=room_id)

def handle_send_message(data):
    room_id = data["room_id"]
    sender = data["sender"]
    content = data["content"]

    print(f"💬 {sender} in {room_id}: {content}")

    # Save message to database
    database.add_message(room_id, sender, content)

    # ✅ Broadcast to everyone in the same room
    emit(
        "new_message",
        {"sender": sender, "content": content, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
        room=room_id,        # important: this sends to all in room
        include_self=False   # optional: exclude sender if you want
    )
# ======================================================
# RUN SERVER
# ======================================================
if __name__ == "__main__":
    print("🚀 Chat server running on http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050)
'''
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room
import database
import time

from openai import AzureOpenAI
import json, os

# --- Azure OpenAI setup ---
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or "your_default_endpoint"
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY") or "your_default_key"
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") or "your_deployment_name"

client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version = "2024-05-01-preview"
)


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Track connected users per room
active_users = {}  # room_id -> set of usernames
user_rooms = {}    # sid -> room_id



def summarize_chat(room_id):
    """Summarize chat with topic, solutions, and next steps."""
    try:
        messages = database.get_messages(room_id)
        if not messages:
            return "No messages to summarize."

        chat_text = "\n".join([f"{m['sender']}: {m['content']}" for m in messages])

        prompt = f"""
        Summarize this chat clearly.
        Include:
        1. **Main topic of discussion**
        2. **Possible solutions or ideas discussed**
        3. **Next steps or potential future implementations**

        Chat transcript:
        {chat_text}
        """

        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = response.choices[0].message.content.strip()
        database.save_chat_summary(room_id, summary)
        print(f"🧾 Summary saved for room {room_id}")
        return summary
    except Exception as e:
        print(f"❌ Failed to summarize chat: {e}")
        return None


@socketio.on("connect")
def handle_connect():
    print(f"✅ Client connected: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    print(f"❌ Client disconnected: {request.sid}")

    # 🔍 If you store user-room mapping in user_rooms, retrieve room_id
    room_id = user_rooms.get(request.sid) if 'user_rooms' in globals() else None

    # If you want to summarize for all disconnections (even without mapping)
    if not room_id:
        # Optionally: summarize all rooms or skip if you can’t find room
        print("⚠️ No room mapping found, skipping summary trigger.")
        return

    print(f"🕒 User disconnected from {room_id}, generating summary...")
    summary = summarize_chat(room_id)
    if summary:
        emit(
            "system_message",
            {"content": "🧾 Chat summary has been saved."},
            room=room_id
        )



@socketio.on("join_room")
def handle_join_room(data):
    room_id = data["room_id"]
    username = data["username"]

    print(f"👤 {username} joined room {room_id}")
    join_room(room_id)

    # Track user-room mapping
    active_users.setdefault(room_id, set()).add(username)
    user_rooms[request.sid] = room_id

    # Send chat history to the new user
    messages = database.get_messages(room_id)
    emit("chat_history", messages, room=request.sid)

    # Notify others
    emit("system_message",
         {"content": f"{username} joined the room."},
         room=room_id, include_self=False)

    
@socketio.on("send_message")
def handle_send_message(data):
    room_id = data["room_id"]
    sender = data["sender"]
    content = data["content"]

    print(f"💬 {sender} in {room_id}: {content}")
    database.add_message(room_id, sender, content)

    # Broadcast the new message
    emit(
        "new_message",
        {
            "sender": sender,
            "content": content,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        room=room_id,
        include_self=True,
    )

    # 🔔 Broadcast a REFRESH signal to all clients in that room
    emit("refresh_required", {"room_id": room_id}, room=room_id)


'''@socketio.on("send_message")
def handle_send_message(data):
    room_id = data.get("room_id")
    sender = data.get("sender")
    content = data.get("content")

    print(f"💬 {sender} in {room_id}: {content}")

    try:
        # ✅ Save to Supabase via your helper
        database.add_message(room_id, sender, content)
    except Exception as e:
        print(f"❌ Failed to save message: {e}")

    # Broadcast to everyone in the room
    emit(
        "new_message",
        {"sender": sender, "content": content,
         "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
        room=room_id,
        include_self=False,
    )'''


if __name__ == "__main__":
    print("🚀 Chat server running on http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, use_reloader=False)
