import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings, get_category

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

st.sidebar.image(settings['logo_url'], width=150)
st.sidebar.title("🛡️ Admin Login")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

stored_password = r.get("admin_password") or "admin123"
pwd_input = st.sidebar.text_input("Password", type="password")
if st.sidebar.button("Login"):
    if pwd_input == stored_password:
        st.session_state['authenticated'] = True
        st.rerun()
    else:
        st.sidebar.error("Incorrect Password")

st.title("🏃 Club PB Leaderboard (Admin View)")
# (Rest of Leaderboard and Runner Search code identical to BBPB.py above)
