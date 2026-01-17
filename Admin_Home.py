import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings, rebuild_leaderboard_cache

st.set_page_config(page_title="BBPB - Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

# --- SIDEBAR LOGIN (Restored) ---
st.sidebar.title("🔐 Admin Access")
if not st.session_state.get('authenticated'):
    pwd = st.sidebar.text_input("Enter Password", type="password")
    if pwd == settings.get('admin_password', 'admin'):
        st.session_state['authenticated'] = True
        st.rerun()
    else:
        st.warning("Please login to manage the club.")
        st.stop()

if st.sidebar.button("Logout"):
    st.session_state['authenticated'] = False
    st.rerun()

# --- MAIN PAGE (Restored Leaderboard) ---
st.title("🏃 Bramley Breezers Admin")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Current Championship Standings")
    # New Cache Logic: Pull from cache first for speed
    cache = r.get("cached_champ_standings")
    if cache:
        league = pd.read_json(cache)
        st.table(league)
    else:
        st.info("No cache found. Click 'Refresh Cache' or approve a result.")

with col2:
    st.subheader("System Actions")
    if st.button("🔄 Manual Refresh Leaderboard Cache"):
        rebuild_leaderboard_cache(r)
        st.success("Cache Rebuilt!")

    st.write(f"**Age Mode:** {settings.get('age_mode')}")
    if settings.get('logo_url'):
        st.image(settings['logo_url'], width=100)
