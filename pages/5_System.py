import streamlit as st
import json
import os
import pandas as pd
from helpers import get_redis, get_club_settings, rebuild_leaderboard_cache

st.set_page_config(page_title="System Settings", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.warning("Please login on the Home page.")
    st.stop()

st.header("⚙️ System Settings")

# --- CLUB SETTINGS ---
st.subheader("Club Configuration")
settings = get_club_settings()

with st.form("settings_form"):
    club_name = st.text_input("Club Name", settings.get('club_name', 'Bramley Breezers'))
    logo_url = st.text_input("Logo URL", settings.get('logo_url', ''))
    
    if st.form_submit_button("Save Settings"):
        new_settings = {"club_name": club_name, "logo_url": logo_url}
        r.set("club_settings", json.dumps(new_settings))
        rebuild_leaderboard_cache(r)
        st.success("Settings saved and cache updated!")
        st.rerun()

st.divider()

# --- CACHE MANAGEMENT ---
st.subheader("Data Synchronization")
st.info("Force a refresh of the public leaderboards and championship standings.")
if st.button("🔄 Rebuild All Caches", use_container_width=True):
    with st.spinner("Recalculating standings..."):
        if rebuild_leaderboard_cache(r):
            st.success("Public cache rebuilt successfully!")
        else:
            st.error("Cache rebuild failed.")

st.divider()

# --- BACKUP & EXPORT ---
st.subheader("💾 Backup & Data Export")
col_exp, col_imp = st.columns(2)

with col_exp:
    st.write("**Export Database**")
    db_export = {
        "members": [json.loads(m) for m in r.lrange("members", 0, -1)],
        "race_results": [json.loads(res) for res in r.lrange("race_results", 0, -1)],
        "champ_results_final": [json.loads(c) for c in r.lrange("champ_results_final", 0, -1)],
        "champ_calendar": json.loads(r.get("champ_calendar_2026") or "[]"),
        "club_settings": settings
    }
    json_str = json.dumps(db_export, indent=2)
    st.download_button(
        label="📥 Download JSON Backup",
        data=json_str,
        file_name=f"bbpb_backup_{pd.Timestamp.now().strftime('%Y%m%d')}.json",
        mime="application/json",
        use_container_width=True
    )

with col_imp:
    st.write("**Restore / Import**")
    uploaded_file = st.file_uploader("Upload JSON Backup", type="json")
    if uploaded_file is not None:
        if st.button("⚠️ Confirm Restore", use_container_width=True):
            data = json.load(uploaded_file)
            # Members
            r.delete("members")
            for m in data.get("members", []): r.rpush("members", json.dumps(m))
            # Results
            r.delete("race_results")
            for res in data.get("race_results", []): r.rpush("race_results", json.dumps(res))
            # Champ
            r.delete("champ_results_final")
            for c in data.get("champ_results_final", []): r.rpush("champ_results_final", json.dumps(c))
            # Calendar
            r.set("champ_calendar_2026", json.dumps(data.get("champ_calendar", [])))
            
            rebuild_leaderboard_cache(r)
            st.success("Database restored successfully!")
            st.rerun()

st.divider()

# --- MEMBER STATUS TOGGLES ---
st.subheader("🏃 Member Status Toggles")
st.write("Quickly toggle members between Active (1.0 opacity) and Inactive (0.5 opacity).")
members_raw = r.lrange("members", 0, -1)
if members_raw:
    for i, m_json in enumerate(members_raw):
        m = json.loads(m_json)
        c1, c2, c3 = st.columns([3, 2, 2])
        c1.write(f"**{m['name']}**")
        current_status = m.get('status', 'Active')
        c2.write(f"Current: {current_status}")
        
        new_label = "Set Inactive" if current_status == "Active" else "Set Active"
        if c3.button(new_label, key=f"tog_{i}"):
            m['status'] = "Inactive" if current_status == "Active" else "Active"
            r.lset("members", i, json.dumps(m))
            rebuild_leaderboard_cache(r)
            st.rerun()
else:
    st.info("No members found.")

st.divider()

with st.expander("⚠️ Danger Zone"):
    st.write("Current Database Keys:")
    st.json(r.keys("*"))
    if st.button("Clear All Pending Queues"):
        r.delete("pending_results")
        r.delete("champ_pending")
        st.warning("Pending queues cleared.")
        st.rerun()
