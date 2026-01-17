import streamlit as st
import pandas as pd
from helpers import get_redis, get_club_settings

st.set_page_config(page_title="BBPB Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

st.title("🛡️ Admin Dashboard")

if not st.session_state.get('authenticated'):
    pwd = st.text_input("Admin Password", type="password")
    if pwd == settings['admin_password']:
        st.session_state['authenticated'] = True
        st.rerun()
    else:
        st.stop()

st.success("Authenticated")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Current Champ Standings (Cached)")
    cache = r.get("cached_champ_standings")
    if cache:
        st.table(pd.read_json(cache))
    else:
        st.info("No cache found. Rebuild via Championship page.")

with col2:
    st.subheader("System Status")
    st.write(f"**Age Mode:** {settings['age_mode']}")
    if st.button("Manual Cache Refresh"):
        from helpers import rebuild_leaderboard_cache
        rebuild_leaderboard_cache(r)
        st.success("Global Cache Rebuilt!")
