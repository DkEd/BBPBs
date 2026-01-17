import streamlit as st
import json
import os
from helpers import get_redis, get_club_settings, rebuild_leaderboard_cache

st.set_page_config(page_title="System Settings", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.warning("Please login on the Home page.")
    st.stop()

st.header("⚙️ System Settings")

st.subheader("Club Configuration")
settings = get_club_settings()

with st.form("settings_form"):
    club_name = st.text_input("Club Name", settings.get('club_name', 'Bramley Breezers'))
    logo_url = st.text_input("Logo URL", settings.get('logo_url', ''))
    
    if st.form_submit_button("Save Settings"):
        # Age mode removed from form - strictly Age on Day
        new_settings = {
            "club_name": club_name,
            "logo_url": logo_url
        }
        r.set("club_settings", json.dumps(new_settings))
        rebuild_leaderboard_cache(r)
        st.success("Settings saved and cache updated!")
        st.rerun()

st.divider()

st.subheader("Data Synchronization")
st.info("Use the button below to force a refresh of the public leaderboards and championship standings.")

if st.button("🔄 Rebuild All Caches", use_container_width=True):
    with st.spinner("Recalculating standings..."):
        success = rebuild_leaderboard_cache(r)
        if success:
            st.success("Public cache rebuilt successfully! Both sites are now in sync.")
        else:
            st.error("Cache rebuild failed. Check database logs.")

st.divider()

with st.expander("⚠️ Danger Zone"):
    st.write("Current Database Keys:")
    keys = r.keys("*")
    st.json(keys)
    if st.button("Clear Pending Approvals"):
        r.delete("pending_results")
        r.delete("champ_pending")
        st.warning("Pending queues cleared."); st.rerun()
