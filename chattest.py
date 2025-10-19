'''import streamlit as st
import socketio
import time
import queue
import database
import warnings

# ======================================================
# CONFIG
# ======================================================
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
sio = socketio.Client()
INCOMING_QUEUE = queue.Queue()  # global, thread-safe message queue

# ======================================================
# SOCKET HANDLERS (no Streamlit calls here!)
# ======================================================
@sio.event
def connect():
    print("✅ Connected to chat server")

@sio.event
def disconnect():
    print("❌ Disconnected from chat server")

@sio.event
def chat_history(data):
    print("📜 Received chat history:", len(data))
    INCOMING_QUEUE.put({"type": "history", "data": data})

@sio.event
def new_message(data):
    print("💬 New message:", data)
    INCOMING_QUEUE.put({"type": "new", "data": data})

@sio.event
def system_message(data):
    INCOMING_QUEUE.put({"type": "system", "data": data})


# ======================================================
# STREAMLIT APP
# ======================================================
def app():
    st.title("💬 Chat Room")

    # ---- Login Check ----
    if "username" not in st.session_state:
        st.warning("Please log in first on the Account page.")
        return

    username = st.session_state["username"]
    st.subheader(f"Welcome, {username}! 👋")

    # ---- Session State Defaults ----
    if "connected" not in st.session_state:
        st.session_state["connected"] = False
    if "room_id" not in st.session_state:
        st.session_state["room_id"] = None
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()

    # ---- Room Selection ----
    rooms = database.get_user_rooms(username)
    room_names = [f"{r['name']} ({r['id'][:8]})" for r in rooms] if rooms else []

    col1, col2 = st.columns(2)
    with col1:
        selected = st.selectbox("Your Rooms:", [""] + room_names)
        if st.button("Join Room"):
            if selected:
                selected_room = rooms[room_names.index(selected)]
                connect_to_room(selected_room["id"], username)
            else:
                st.warning("Select a room first.")

    with col2:
        new_room_name = st.text_input("Create new room:")
        if st.button("Create"):
            if new_room_name.strip():
                room_id = database.create_room(new_room_name)
                database.add_user_to_room(room_id, username)
                connect_to_room(room_id, username)
            else:
                st.warning("Room name cannot be empty.")

    st.divider()

    join_input = st.text_input("Join by room name or ID:")
    if st.button("Join Existing"):
        room = database.get_room_by_name(join_input) or database.get_room_by_id(join_input)
        if not room:
            st.error("No such room found.")
        else:
            if not database.is_user_in_room(username, room["id"]):
                database.add_user_to_room(room["id"], username)
            connect_to_room(room["id"], username)

    if st.session_state["room_id"]:
        render_chat(username)


# ======================================================
# SOCKET CONNECTION
# ======================================================
def connect_to_room(room_id, username):
    st.session_state["room_id"] = room_id
    if not st.session_state["connected"]:
        try:
            sio.connect("http://localhost:5050", transports=["websocket", "polling"])
            st.session_state["connected"] = True
        except Exception as e:
            st.error(f"⚠️ Could not connect to chat server: {e}")
            return

    sio.emit("join_room", {"room_id": room_id, "username": username})


# ======================================================
# CHAT RENDER
# ======================================================
def render_chat(username):
    room_id = st.session_state["room_id"]
    st.markdown(f"### 💬 Room ID: `{room_id[:8]}`")

    # ---- Process incoming messages from socket thread ----
    while not INCOMING_QUEUE.empty():
        event = INCOMING_QUEUE.get()
        if event["type"] == "history":
            st.session_state["messages"] = event["data"]
        elif event["type"] == "new":
            st.session_state["messages"].append(event["data"])
        elif event["type"] == "system":
            st.session_state["messages"].append(
                {"sender": "System", "content": event["data"]["content"]}
            )

    # ---- Display messages ----
    chat_box = st.container()
    for msg in st.session_state["messages"]:
        sender = msg.get("sender", "")
        content = msg.get("content", "")
        ts = msg.get("timestamp", "")[:19]
        if sender == username:
            chat_box.markdown(
                f"<div style='text-align:right;color:#4CAF50;margin:5px 0;'>"
                f"<b>You:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )
        elif sender == "System":
            chat_box.markdown(
                f"<div style='text-align:center;color:gray;font-style:italic;margin:5px 0;'>"
                f"{content}</div>",
                unsafe_allow_html=True,
            )
        else:
            chat_box.markdown(
                f"<div style='text-align:left;margin:5px 0;'>"
                f"<b>{sender}:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )

    # ---- Send message ----
    msg = st.text_input("Type your message:", key="message_input")
    if st.button("Send Message"):
        if msg.strip():
            sio.emit("send_message", {
                "room_id": room_id,
                "sender": username,
                "content": msg.strip()
            })
            st.session_state["messages"].append(
                {"sender": username, "content": msg.strip(), "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
            )
        else:
            st.warning("Cannot send empty message.")

    # ---- Auto-refresh ----
    if time.time() - st.session_state["last_refresh"] > 2:
        st.session_state["last_refresh"] = time.time()
        st.experimental_rerun() if hasattr(st, "experimental_rerun") else None
    
    # ---- Auto-refresh (universal) ----
    # Detect if a new message arrived during this render
    if 'last_message_count' not in st.session_state:
        st.session_state['last_message_count'] = len(st.session_state['messages'])

    if len(st.session_state['messages']) > st.session_state['last_message_count']:
        # A new message just came in → refresh immediately
        st.session_state['last_message_count'] = len(st.session_state['messages'])
        st.markdown("""
            <script>
            window.scrollTo(0, document.body.scrollHeight);
            setTimeout(function(){ window.location.reload(); }, 300);
            </script>
        """, unsafe_allow_html=True)
    else:
        # No new message → periodic refresh every 2s
        st.markdown("""
            <script>
            setTimeout(function(){ window.location.reload(); }, 2000);
            </script>
        """, unsafe_allow_html=True)



# ======================================================
# ENTRY
# ======================================================
if __name__ == "__main__":
    app()'''

import streamlit as st
import socketio
import time
import queue
import database
import warnings

# ======================================================
# CONFIG & GLOBALS
# ======================================================
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

if "sio" not in st.session_state:
    st.session_state["sio"] = socketio.Client()
sio = st.session_state["sio"]

INCOMING_QUEUE = queue.Queue()  # global thread-safe queue
CHAT_SERVER_URL = "http://localhost:5050"  # match your chatserver.py port


# ======================================================
# SOCKET HANDLERS (background threads)
# ======================================================
@sio.event
def connect():
    print("✅ Connected to chat server")

@sio.event
def disconnect():
    print("❌ Disconnected from chat server")
    st.session_state["connected"] = False

@sio.event
def chat_history(data):
    print("📜 Received chat history:", len(data))
    INCOMING_QUEUE.put({"type": "history", "data": data})

@sio.event
def new_message(data):
    print("💬 New message:", data)
    INCOMING_QUEUE.put({"type": "new", "data": data})

@sio.event
def system_message(data):
    INCOMING_QUEUE.put({"type": "system", "data": data})
    
@sio.event
def refresh_required(data):
    print("♻️ Refresh signal received for room:", data.get("room_id"))
    INCOMING_QUEUE.put({"type": "refresh", "data": data})



# ======================================================
# STREAMLIT APP
# ======================================================
def app():
    st.title("💬 Chat Room")

    if "username" not in st.session_state:
        st.warning("Please log in first on the Account page.")
        return

    username = st.session_state["username"]

    # Initialize once
    st.session_state.setdefault("connected", False)
    st.session_state.setdefault("room_id", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("last_refresh", time.time())
    st.session_state.setdefault("last_message_count", 0)

    # Auto-reconnect socket if lost
    if not sio.connected:
        try:
            sio.connect(CHAT_SERVER_URL, transports=["websocket", "polling"])
            st.session_state["connected"] = True
        except Exception as e:
            st.error(f"⚠️ Could not connect to chat server: {e}")

    # --------------------------------------------
    # ROOM CONTROLS
    # --------------------------------------------
    rooms = database.get_user_rooms(username)
    room_names = [f"{r['name']} ({r['id'][:8]})" for r in rooms] if rooms else []

    col1, col2 = st.columns(2)
    with col1:
        selected = st.selectbox("Your Rooms:", [""] + room_names)
        if st.button("Join Room"):
            if selected:
                selected_room = rooms[room_names.index(selected)]
                connect_to_room(selected_room["id"], username)
            else:
                st.warning("Select a room first.")

    with col2:
        new_room_name = st.text_input("Create new room:")
        if st.button("Create"):
            if new_room_name.strip():
                room_id = database.create_room(new_room_name)
                database.add_user_to_room(room_id, username)
                connect_to_room(room_id, username)
            else:
                st.warning("Room name cannot be empty.")

    st.divider()

    join_input = st.text_input("Join by room name or ID:")
    if st.button("Join Existing"):
        room = database.get_room_by_name(join_input) or database.get_room_by_id(join_input)
        if not room:
            st.error("No such room found.")
        else:
            if not database.is_user_in_room(username, room["id"]):
                database.add_user_to_room(room["id"], username)
            connect_to_room(room["id"], username)

    # --------------------------------------------
    # CHAT INTERFACE
    # --------------------------------------------
    if st.session_state["room_id"]:
        render_chat(username)


# ======================================================
# CONNECT & JOIN ROOM
# ======================================================
def connect_to_room(room_id, username):
    st.session_state["room_id"] = room_id

    if not sio.connected:
        try:
            sio.connect(CHAT_SERVER_URL, transports=["websocket", "polling"])
            st.session_state["connected"] = True
        except Exception as e:
            st.error(f"⚠️ Could not connect to chat server: {e}")
            return

    sio.emit("join_room", {"room_id": room_id, "username": username})
    print(f"👤 {username} joined room {room_id}")


# ======================================================
# CHAT RENDER & SEND
# ======================================================
def render_chat(username):
    room_id = st.session_state["room_id"]
    st.markdown(f"### 💬 Room ID: `{room_id[:8]}`")

    # --- Process incoming events ---
    new_message_received = False
    '''while not INCOMING_QUEUE.empty():
        event = INCOMING_QUEUE.get()
        if event["type"] == "history":
            st.session_state["messages"] = event["data"]
        elif event["type"] == "new":
            st.session_state["messages"].append(event["data"])
            new_message_received = True
        elif event["type"] == "system":
            st.session_state["messages"].append(
                {"sender": "System", "content": event["data"]["content"]}
            )
            new_message_received = True'''
            
    while not INCOMING_QUEUE.empty():
        event = INCOMING_QUEUE.get()
        if event["type"] == "history":
            st.session_state["messages"] = event["data"]
        elif event["type"] == "new":
            st.session_state["messages"].append(event["data"])
        elif event["type"] == "system":
            st.session_state["messages"].append(
                {"sender": "System", "content": event["data"]["content"]}
            )
        elif event["type"] == "refresh":
            st.rerun()  # ✅ Immediately rerun the Streamlit script
            
    # --- Display chat messages ---
    chat_box = st.container()
    for msg in st.session_state["messages"]:
        sender = msg.get("sender", "")
        content = msg.get("content", "")
        ts = msg.get("timestamp", "")[:19]
        if sender == username:
            chat_box.markdown(
                f"<div style='text-align:right;color:#4CAF50;margin:5px 0;'>"
                f"<b>You:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )
        elif sender == "System":
            chat_box.markdown(
                f"<div style='text-align:center;color:gray;font-style:italic;margin:5px 0;'>"
                f"{content}</div>",
                unsafe_allow_html=True,
            )
        else:
            chat_box.markdown(
                f"<div style='text-align:left;margin:5px 0;'>"
                f"<b>{sender}:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )

    # --- Send new message ---
    msg = st.text_input("Type your message:", key="message_input")
    if st.button("Send Message"):
        if msg.strip():
            if sio.connected:
                sio.emit("send_message", {
                    "room_id": room_id,
                    "sender": username,
                    "content": msg.strip()
                })
                st.session_state["messages"].append(
                    {"sender": username, "content": msg.strip(),
                     "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
                )
            else:
                st.warning("⚠️ Chat server not connected. Try rejoining the room.")
        else:
            st.warning("Cannot send empty message.")

    # --- Auto-refresh (universal, no Streamlit API needed) ---
    if 'last_message_count' not in st.session_state:
        st.session_state['last_message_count'] = len(st.session_state['messages'])

    # if a new message has appeared
    if len(st.session_state['messages']) > st.session_state['last_message_count']:
        st.session_state['last_message_count'] = len(st.session_state['messages'])
        # scroll to bottom + quick reload
        st.markdown("""
            <script>
            window.scrollTo(0, document.body.scrollHeight);
            setTimeout(function(){ window.location.reload(); }, 400);
            </script>
        """, unsafe_allow_html=True)
    else:
        # slow periodic refresh (2s) to poll for new messages
        st.markdown("""
            <script>
            setTimeout(function(){ window.location.reload(); }, 2000);
            </script>
        """, unsafe_allow_html=True)
'''import time

def render_chat(username):
    room_id = st.session_state["room_id"]
    st.markdown(f"### 💬 Room ID: `{room_id[:8]}`")

    # ------------------------------------------------------
    # REFRESH CONTROLS
    # ------------------------------------------------------
    refresh_col1, refresh_col2 = st.columns([1, 8])
    with refresh_col1:
        refresh_clicked = st.button("🔄 Refresh Chat")

    # auto-refresh every 3 seconds (safe interval)
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()
    auto_refresh_due = (time.time() - st.session_state["last_refresh"]) > 3

    if refresh_clicked or auto_refresh_due:
        st.session_state["last_refresh"] = time.time()

        # ---- Process queue safely ----
        while not INCOMING_QUEUE.empty():
            event = INCOMING_QUEUE.get()
            if event["type"] == "history":
                st.session_state["messages"] = event["data"]
            elif event["type"] == "new":
                st.session_state["messages"].append(event["data"])
            elif event["type"] == "system":
                st.session_state["messages"].append(
                    {"sender": "System", "content": event["data"]["content"]}
                )

        # Trigger light rerun
        if not refresh_clicked:
            st.rerun() if hasattr(st, "rerun") else None

    # ------------------------------------------------------
    # DISPLAY CHAT MESSAGES
    # ------------------------------------------------------
    chat_box = st.container()
    for msg in st.session_state["messages"]:
        sender = msg.get("sender", "")
        content = msg.get("content", "")
        ts = msg.get("timestamp", "")[:19]
        if sender == username:
            chat_box.markdown(
                f"<div style='text-align:right;color:#4CAF50;margin:5px 0;'>"
                f"<b>You:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )
        elif sender == "System":
            chat_box.markdown(
                f"<div style='text-align:center;color:gray;font-style:italic;margin:5px 0;'>"
                f"{content}</div>",
                unsafe_allow_html=True,
            )
        else:
            chat_box.markdown(
                f"<div style='text-align:left;margin:5px 0;'>"
                f"<b>{sender}:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------
    # SEND MESSAGE (using Streamlit form to avoid blank bug)
    # ------------------------------------------------------
    with st.form("send_message_form", clear_on_submit=True):
        msg = st.text_input("Type your message:", key="chat_input")
        submitted = st.form_submit_button("Send Message")

        if submitted:
            if msg.strip():
                if sio.connected:
                    sio.emit("send_message", {
                        "room_id": room_id,
                        "sender": username,
                        "content": msg.strip()
                    })
                    st.session_state["messages"].append(
                        {"sender": username, "content": msg.strip(),
                         "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
                    )
                else:
                    st.warning("⚠️ Chat server not connected.")
            else:
                st.warning("Message cannot be empty.")'''

'''

import time

def render_chat(username):
    room_id = st.session_state["room_id"]
    st.markdown(f"### 💬 Room ID: `{room_id[:8]}`")

    chat_area = st.empty()           # placeholder for messages
    input_area = st.empty()          # placeholder for input box

    while True:
        # ---- Process queue safely ----
        while not INCOMING_QUEUE.empty():
            event = INCOMING_QUEUE.get()
            if event["type"] == "history":
                st.session_state["messages"] = event["data"]
            elif event["type"] == "new":
                st.session_state["messages"].append(event["data"])
            elif event["type"] == "system":
                st.session_state["messages"].append(
                    {"sender": "System", "content": event["data"]["content"]}
                )

        # ---- Draw messages ----
        with chat_area.container():
            for msg in st.session_state["messages"]:
                sender = msg.get("sender", "")
                content = msg.get("content", "")
                ts = msg.get("timestamp", "")[:19]
                if sender == username:
                    st.markdown(
                        f"<div style='text-align:right;color:#4CAF50;margin:5px 0;'>"
                        f"<b>You:</b> {content} <sub>{ts}</sub></div>",
                        unsafe_allow_html=True,
                    )
                elif sender == "System":
                    st.markdown(
                        f"<div style='text-align:center;color:gray;font-style:italic;margin:5px 0;'>"
                        f"{content}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='text-align:left;margin:5px 0;'>"
                        f"<b>{sender}:</b> {content} <sub>{ts}</sub></div>",
                        unsafe_allow_html=True,
                    )

        # ---- Input field and send button ----
        with input_area.container():
            msg = st.text_input("Type your message:", key=str(time.time()))
            send = st.button("Send Message", key=str(time.time()) + "_btn")
            if send and msg.strip():
                sio.emit("send_message", {
                    "room_id": room_id,
                    "sender": username,
                    "content": msg.strip()
                })
                st.session_state["messages"].append(
                    {"sender": username, "content": msg.strip(),
                     "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
                )

        time.sleep(1)  # refresh rate in seconds
        st.experimental_rerun() if hasattr(st, "experimental_rerun") else None

import time

def render_chat(username):
    room_id = st.session_state["room_id"]
    st.markdown(f"### 💬 Room ID: `{room_id[:8]}`")

    # ---- Refresh control ----
    if st.button("🔄 Refresh Chat"):
        st.session_state["force_refresh"] = True
    else:
        st.session_state["force_refresh"] = False

    # ---- Process new incoming messages ----
    if st.session_state.get("force_refresh", False):
        while not INCOMING_QUEUE.empty():
            event = INCOMING_QUEUE.get()
            if event["type"] == "history":
                st.session_state["messages"] = event["data"]
            elif event["type"] == "new":
                st.session_state["messages"].append(event["data"])
            elif event["type"] == "system":
                st.session_state["messages"].append(
                    {"sender": "System", "content": event["data"]["content"]}
                )

    # ---- Display chat messages ----
    chat_box = st.container()
    for msg in st.session_state["messages"]:
        sender = msg.get("sender", "")
        content = msg.get("content", "")
        ts = msg.get("timestamp", "")[:19]
        if sender == username:
            chat_box.markdown(
                f"<div style='text-align:right;color:#4CAF50;margin:5px 0;'>"
                f"<b>You:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )
        elif sender == "System":
            chat_box.markdown(
                f"<div style='text-align:center;color:gray;font-style:italic;margin:5px 0;'>"
                f"{content}</div>",
                unsafe_allow_html=True,
            )
        else:
            chat_box.markdown(
                f"<div style='text-align:left;margin:5px 0;'>"
                f"<b>{sender}:</b> {content} <sub>{ts}</sub></div>",
                unsafe_allow_html=True,
            )

    # ---- Message input + send ----
    msg = st.text_input("Type your message:", key="chat_input")
    if st.button("Send Message"):
        if msg.strip():
            if sio.connected:
                sio.emit("send_message", {
                    "room_id": room_id,
                    "sender": username,
                    "content": msg.strip()
                })
                # instantly show for sender
                st.session_state["messages"].append(
                    {"sender": username, "content": msg.strip(),
                     "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
                )
                st.session_state["chat_input"] = ""  # clear input

            else:
                st.warning("⚠️ Chat server not connected.")
        else:
            st.warning("Message cannot be empty.")'''



# ======================================================
# ENTRY POINT
# ======================================================
if __name__ == "__main__":
    app()
