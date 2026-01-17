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

tabs = st.tabs(["Club Settings", "Bulk Upload", "Export & Backup"])

with tabs[0]:
    st.subheader("General Settings")
    with st.form("settings_form"):
        new_mode = st.selectbox("Age Category Mode", ["5 Year", "10 Year"], 
                               index=0 if settings.get('age_mode') == "5 Year" else 1)
        new_logo = st.text_input("Logo URL", settings.get('logo_url', ''))
        new_pwd = st.text_input("Admin Password", settings.get('admin_password', 'admin'), type="password")
        
        if st.form_submit_button("Save Settings"):
            new_settings = {"age_mode": new_mode, "logo_url": new_logo, "admin_password": new_pwd}
            r.set("club_settings", json.dumps(new_settings))
            rebuild_leaderboard_cache(r) # Trigger refresh
            st.success("Settings saved and cache updated!")

with tabs[1]:
    st.subheader("Bulk Data Import")
    data_type = st.selectbox("Import Type", ["Members", "Race Results", "Championship Results"])
    uploaded_file = st.file_uploader(f"Choose {data_type} CSV", type="csv")
    
    if uploaded_file and st.button("🚀 Process Import"):
        df = pd.read_csv(uploaded_file)
        redis_key = {
            "Members": "members",
            "Race Results": "race_results",
            "Championship Results": "champ_results_final"
        }[data_type]
        
        for _, row in df.iterrows():
            r.rpush(redis_key, json.dumps(row.to_dict()))
        
        rebuild_leaderboard_cache(r)
        st.success(f"Successfully imported {len(df)} records to {data_type}!")

with tabs[2]:
    st.subheader("Data Export")
    # Export Members
    m_raw = r.lrange("members", 0, -1)
    if m_raw:
        m_df = pd.DataFrame([json.loads(x) for x in m_raw])
        st.download_button("📥 Download Member List", m_df.to_csv(index=False), "members.csv", "text/csv")
    
    # Export Races
    r_raw = r.lrange("race_results", 0, -1)
    if r_raw:
        r_df = pd.DataFrame([json.loads(x) for x in r_raw])
        st.download_button("📥 Download All Race Results", r_df.to_csv(index=False), "all_races.csv", "text/csv")
