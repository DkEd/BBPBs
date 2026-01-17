import streamlit as st
import json
import pandas as pd
from helpers import get_redis, get_club_settings, rebuild_leaderboard_cache

st.set_page_config(page_title="System Management", layout="wide")
r = get_redis()
settings = get_club_settings()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page.")
    st.stop()

st.header("⚙️ System Management")
tabs = st.tabs(["Club Settings", "Bulk Upload", "Backup & Export", "Cache Engine"])

with tabs[0]:
    st.subheader("General Settings")
    with st.form("settings_form"):
        new_mode = st.selectbox("Age Category Mode", ["5 Year", "10 Year"], 
                               index=0 if settings.get('age_mode') == "5 Year" else 1)
        new_logo = st.text_input("Logo URL", settings.get('logo_url', ''))
        new_pwd = st.text_input("Admin Password", settings.get('admin_password', 'admin'), type="password")
        if st.form_submit_button("Save Settings"):
            r.set("club_settings", json.dumps({"age_mode": new_mode, "logo_url": new_logo, "admin_password": new_pwd}))
            st.success("Settings saved!")

with tabs[1]:
    st.subheader("Bulk Import")
    target = st.radio("Target Database", ["Members", "Race Results", "Championship Results"], horizontal=True)
    f = st.file_uploader(f"Upload {target} CSV", type="csv")
    if f and st.button("🚀 Execute Import"):
        df = pd.read_csv(f)
        key = {"Members": "members", "Race Results": "race_results", "Championship Results": "champ_results_final"}[target]
        for _, row in df.iterrows():
            r.rpush(key, json.dumps(row.to_dict()))
        rebuild_leaderboard_cache(r)
        st.success(f"Imported {len(df)} records.")

with tabs[2]:
    st.subheader("Data Export")
    col1, col2, col3 = st.columns(3)
    
    # 1. Members Backup
    m_raw = r.lrange("members", 0, -1)
    if m_raw:
        m_df = pd.DataFrame([json.loads(x) for x in m_raw])
        col1.download_button("📥 Members CSV", m_df.to_csv(index=False), "members_backup.csv", "text/csv")
    else:
        col1.info("No members to export.")
    
    # 2. Race Results (PBs) Backup
    r_raw = r.lrange("race_results", 0, -1)
    if r_raw:
        r_df = pd.DataFrame([json.loads(x) for x in r_raw])
        col2.download_button("📥 Races CSV", r_df.to_csv(index=False), "races_backup.csv", "text/csv")
    else:
        col2.info("No race results to export.")
        
    # 3. Championship Results Backup
    c_raw = r.lrange("champ_results_final", 0, -1)
    if c_raw:
        c_df = pd.DataFrame([json.loads(x) for x in c_raw])
        col3.download_button("📥 Champ CSV", c_df.to_csv(index=False), "championship_backup.csv", "text/csv")
    else:
        col3.info("No champ results to export.")

with tabs[3]:
    st.subheader("Cache Engine")
    st.info("Manually force a leaderboard recalculation if data appears out of sync.")
    if st.button("🔄 Rebuild Global Cache"):
        rebuild_leaderboard_cache(r)
        st.success("Global Cache Rebuilt!")
