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
        st.warning("Locked. Please login.")

if st.session_state.get('authenticated'):
    st.info("Select a management tool from the sidebar to begin.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", r.llen("race_results"))
    c2.metric("Total Members", r.llen("members"))
    c3.metric("Pending Approvals", r.llen("pending_results"))
