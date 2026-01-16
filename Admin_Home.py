import streamlit as st
import os
from helpers import get_redis

st.set_page_config(page_title="BBPB-Admin", layout="wide")

# Simple Password Check
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.title("🛡️ Admin Login")
    pwd = st.text_input("Password", type="password")
    # You can change 'admin123' to whatever you want, or set an env var ADMIN_PASS
    correct_pass = os.getenv("ADMIN_PASS", "admin123")
    
    if st.button("Login"):
        if pwd == correct_pass:
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.error("Incorrect Password")
    st.stop()

# --- DASHBOARD ---
r = get_redis()
st.title("Admin Dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    pending_count = r.llen("pending_results")
    st.metric("Standard PBs Pending", pending_count)
with col2:
    champ_count = r.llen("champ_pending")
    st.metric("Champ Results Pending", champ_count)
with col3:
    mem_count = r.llen("members")
    st.metric("Total Members", mem_count)

st.info("👈 Use the sidebar to manage Members, PBs, or the Championship.")
