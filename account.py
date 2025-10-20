import streamlit as st
import database

def app():
    # Initialize session state for username if not set
    if "username" not in st.session_state:
        st.session_state["username"] = None

    if "username" in st.session_state and st.session_state["username"]:
        loggedIn()  
    else:
        logIn() 

def logIn():
    #st.title("Welcome to :blue[AI Study Planner] 🤖")
    st.header("Please log in to access your account features.")

    choice = st.selectbox("Please Select: Login / Sign Up", ["Login", "Sign Up"])
    
    if choice == "Login":
        st.write("Please enter your login details.")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if database.validate_user(username, password):
                st.session_state["username"] = username
                st.session_state["page"] = "home"
                st.rerun()
            else:
                st.error("Invalid login details.")
        if st.button("quick login - wenxi"):
            st.session_state["username"] = "wenxi"
            st.session_state["page"] = "home"
            st.rerun()
        if st.button("quick login - sinpei"):
            st.session_state["username"] = "sinpei"
            st.session_state["page"] = "home"
            st.rerun()
    
    elif choice == "Sign Up":
        st.write("Create a new account.")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        if st.button("Sign Up"):
            if new_username and new_password:
                #check if user already exists
                if database.check_username_exists(new_username): 
                    st.error("Username already exists. Please choose a different username.")
                else:
                    database.create_user(new_username, new_password)
                    st.info("Account created successfully! You can now log in.")
            else:   
                st.error("Please fill all fields.")

def loggedIn():
    username = st.session_state["username"]
    st.write("Welcome, "+ username)
    with st.expander("User Details"):
        st.write("Role: " + database.get_info(username)["role"])
        st.write("Department: " + str(database.get_info(username)["department"]))
        st.write("Job Title: " + str(database.get_info(username)["job_title"]))
    if st.button("Logout"):
        st.session_state["username"] = None
        st.success("Logging out...")
        st.rerun()


