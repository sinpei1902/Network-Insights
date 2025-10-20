import streamlit as st
import account
import chat, chattest, powerbi , news, database
from general_performance import app as general_performance
from news import fetch_news

# -------------------------------
# ⚙️ APP CONFIG
# -------------------------------
st.set_page_config(page_title="Network Insights", layout="wide", initial_sidebar_state="expanded")

# -------------------------------
# 🧭 SESSION SETUP
# -------------------------------
if "username" not in st.session_state:
    st.session_state["username"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "login"

# -------------------------------
# 🧱 SIDEBAR (for logged-in users)
# -------------------------------
def sidebar():
    with st.sidebar:
        col1,col2= st.columns([3,3])
        with col1:
            st.markdown(f"👤 **{st.session_state['username']}**")
        with col2:
            if st.button("⚙️ Edit Profile"):
                st.session_state["page"] = "editprofile"
                st.rerun()
        
        st.markdown("---")
        roles_data = database.supabase.table("user_details").select("*").eq("username",st.session_state['username']).execute().data[0]
        with st.container():
            col1,col2= st.columns([3,6])
            with col1:
                st.markdown(f"**Role:** ")
            with col2:
                st.markdown(f"{roles_data['role'] or '_No role assigned_'}")
        with st.container():
            col1,col2= st.columns([3,6])
            with col1:
                st.markdown(f"**Department:** ")
            with col2:
                st.markdown(f"{roles_data['department'] or '_No department assigned_'}")
        with st.container():
            col1,col2= st.columns([3,6])
            with col1:
                st.markdown(f"**Job Title:** ")
            with col2:
                st.markdown(f"{roles_data['job_title'] or '_No job title assigned_'}")
    
        st.markdown("---")
    
        col1,col2= st.columns([3,3])
        with col1:

            if st.button("🚪 Log Out"):
                st.session_state["username"] = None
                st.session_state["page"] = "login"
                st.rerun()

# -------------------------------
# 🔀 PAGE ROUTER
# -------------------------------
def router():
    page = st.session_state["page"]

    if page == "login":
        account.logIn()  # your login function
        return

    # Sidebar only visible when logged in
    sidebar()

    if page == "home":
        show_home()

    elif page == "powerbi":
        if st.button("🏠 Back to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        powerbi.app()
    elif page == "chat":
        if st.button("🏠 Back to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        chat.bot()
    elif page == "chattest":
        if st.button("🏠 Back to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        chattest.app()
    elif page == "editprofile":
        if st.button("🏠 Back to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        edit_profile()
    elif page == "news":
        if st.button("🏠 Back to Home"):
            st.session_state["page"] = "home"
            st.rerun()
        news.app()
        
   # elif page == "reports":
   #     if st.button("🏠 Back to Home"):
   #         st.session_state["page"] = "home"
   #         st.rerun()
    else:
        st.error("❌ Page not found.")

def show_home():
    st.title("🏠 Network Insights Dashboard")

    col1, col2 = st.columns([3, 4], gap="large")

    # Left column → analytics section
    with col1:
        with st.container(border=True):
            general_performance()
        with st.container():
            st.write("")
            st.write("")
        
        col21, col22, col23= st.columns(3)

        with col21:
            if st.button("🤖 Chatbot"):
                st.session_state["page"] = "chat"
                st.rerun()
        with col22:
            if st.button("💬 Business Chat"):
                st.session_state["page"] = "chattest"
                st.rerun()
        with col23:
            if st.button("📊 Generate Report"):
                st.session_state["page"] = "powerbi"
                st.rerun()  
        
    # Right column → news + navigation
    with col2:
        with st.container(border=True):
            st.header("📰 Latest News")

            # Fetch news dynamically
            try:
                articles = fetch_news(["port congestion", "shipping", "logistics"])
            except Exception as e:
                st.error(f"⚠️ Failed to fetch news: {e}")
                articles = []
        
            # Display articles
            if articles:
                for i, item in enumerate(articles[:5]):  # show 5 latest
                    published = item.get("published", "")
                    st.markdown(
                        f"""
                        **[{item['title']}]({item['link']})**  
                        <small>{published}</small>  
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown("---")
            else:
                st.info("📰 No recent news found.")

            # Optional button to open full news page
            if st.button("🌍 View Full News & Risk Analysis"):
                st.session_state["page"] = "news"
                st.rerun()

        
def edit_profile():
    st.title("👤 Profile")

    username = st.session_state.get("username")
    if not username:
        st.warning("Please log in to view your profile.")
        return

    # -----------------------------
    # Fetch user info
    # -----------------------------
    user_info = database.get_info(username)
    st.markdown(f"### 👋 Welcome, **{username}**")

    with st.container(border=True):
        st.subheader("🧾 User Details")

        col1, col2 = st.columns(2)
        with col1:
            role = st.text_input("Role", value=user_info.get("role", ""), placeholder="Enter your role")
            dept = st.text_input("Department", value=user_info.get("department", ""), placeholder="Enter your department")
        with col2:
            job = st.text_input("Job Title", value=user_info.get("job_title", ""), placeholder="Enter your job title")

        if st.button("💾 Save Changes", use_container_width=True):
            database.modify_role(username, role)
            database.modify_dept(username, dept)
            database.modify_job(username, job)
            st.success("✅ Profile updated successfully!")

# -------------------------------
# 🚀 RUN APP
# -------------------------------
router()
