import streamlit as st
from helpers import get_redis

st.set_page_config(page_title="AutoKudos Admin", layout="wide")
r = get_redis()

st.title("🛡️ AutoKudos Master Admin")

with st.sidebar:
    pwd = st.text_input("Enter Admin Password", type="password")
    if pwd == (r.get("admin_password") or "admin123"):
        st.session_state['authenticated'] = True
        st.success("Authenticated")
    else:
        st.session_state['authenticated'] = False
        st.warning("Please login to see management pages.")

# Database Stats Overview
if st.session_state.get('authenticated'):
    st.info("Use the sidebar to navigate between Members, Race Logs, and Championship settings.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total PBs", r.llen("race_results"))
    c2.metric("Total Members", r.llen("members"))
    c3.metric("Pending Approvals", r.llen("pending_results"))
