# chattest.py
import socketio

sio = socketio.Client()

@sio.event
def connect():
    print("✅ Connected to chat server!")

@sio.on("new_message")
def on_message(data):
    print(f"[{data['room']}] {data['sender']}: {data['message']}")

sio.connect("http://localhost:3001")

username = input("Enter username: ")
room = input("Enter room: ")
sio.emit("join_room", {"username": username, "room": room})

print("Type messages below. Press Ctrl+C to exit.")
while True:
    msg = input("> ")
    sio.emit("send_message", {"room": room, "sender": username, "message": msg})
