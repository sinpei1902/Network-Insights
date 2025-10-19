# chat_server.py
import socketio
from aiohttp import web

# Create Async Socket.IO server
sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

@sio.event
async def connect(sid, environ):
    print(f"🟢 {sid} connected")

@sio.event
async def join_room(sid, data):
    username = data["username"]
    room = data["room"]
    await sio.save_session(sid, {"username": username, "room": room})
    await sio.enter_room(sid, room)  # ✅ must await this
    print(f"✅ {username} joined {room}")
    await sio.emit("user_joined", {"username": username}, room=room)

@sio.event
async def send_message(sid, data):
    session = await sio.get_session(sid)
    room = session["room"]
    sender = session["username"]
    message = data["message"]
    print(f"[{room}] {sender}: {message}")
    # ✅ Broadcast to everyone in the same room
    await sio.emit("new_message", {"room": room, "sender": sender, "message": message}, room=room)

@sio.event
async def disconnect(sid):
    print(f"🔴 {sid} disconnected")

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=3001)

