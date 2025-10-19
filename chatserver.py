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

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


@socketio.on("connect")
def handle_connect():
    print(f"✅ Client connected: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    print(f"❌ Client disconnected: {request.sid}")


@socketio.on("join_room")
def handle_join_room(data):
    room_id = data["room_id"]
    username = data["username"]
    print(f"👤 {username} joined room {room_id}")
    join_room(room_id)

    # Send history only to this user
    messages = database.get_messages(room_id)
    emit("chat_history", messages, room=request.sid)

    # Notify others
    emit("system_message",
         {"content": f"{username} joined the room."},
         room=room_id, include_self=False)


@socketio.on("send_message")
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
    )


if __name__ == "__main__":
    print("🚀 Chat server running on http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, use_reloader=False)
