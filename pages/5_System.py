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

# Restoring the correct 4-tab structure
tabs = st.tabs(["🔧 Configuration", "💾 Backup & Export", "📥 Bulk Upload", "🔄 Sync & Maintenance"])

with tabs[0]: # --- CONFIGURATION ---
    st.subheader("Club Configuration")
    settings = get_club_settings()
    with st.form("settings_form"):
        club_name = st.text_input("Club Name", settings.get('club_name', 'Bramley Breezers'))
        logo_url = st.text_input("Logo URL", settings.get('logo_url', ''))
        
        if st.form_submit_button("Save Settings"):
            new_settings = {"club_name": club_name, "logo_url": logo_url}
            r.set("club_settings", json.dumps(new_settings))
            rebuild_leaderboard_cache(r)
            st.success("Settings saved!")
            st.rerun()

with tabs[1]: # --- BACKUP & EXPORT ---
    st.subheader("Database Portability")
    st.write("Export your entire database as a JSON file for a full system restore.")
    
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
        mime="application/json"
    )

    st.divider()
    st.write("**Restore from JSON**")
    uploaded_json = st.file_uploader("Upload JSON Backup File", type="json")
    if uploaded_json is not None:
        if st.button("⚠️ Confirm Full Restore"):
            data = json.load(uploaded_json)
            r.delete("members")
            for m in data.get("members", []): r.rpush("members", json.dumps(m))
            r.delete("race_results")
            for res in data.get("race_results", []): r.rpush("race_results", json.dumps(res))
            r.delete("champ_results_final")
            for c in data.get("champ_results_final", []): r.rpush("champ_results_final", json.dumps(c))
            r.set("champ_calendar_2026", json.dumps(data.get("champ_calendar", [])))
            rebuild_leaderboard_cache(r)
            st.success("System Restored.")
            st.rerun()

with tabs[2]: # --- BULK UPLOAD ---
    st.subheader("CSV Data Import")
    st.info("Upload CSV files to append data to the database. Ensure columns match the expected format.")
    
    # 1. Bulk Members
    with st.expander("Import Members (CSV)"):
        st.caption("Required Columns: name, dob, gender, status")
        up_m = st.file_uploader("Choose Members CSV", type="csv", key="up_m")
        if up_m and st.button("Upload Members"):
            df_m = pd.read_csv(up_m)
            for _, row in df_m.iterrows():
                m_data = {"name": str(row['name']), "dob": str(row['dob']), "gender": str(row['gender']), "status": str(row['status'])}
                r.rpush("members", json.dumps(m_data))
            st.success(f"Added {len(df_m)} members.")

    # 2. Bulk Race Results (PBs)
    with st.expander("Import Race Results / PBs (CSV)"):
        st.caption("Required Columns: name, distance, location, race_date, time_display, time_seconds, gender, dob")
        up_r = st.file_uploader("Choose Results CSV", type="csv", key="up_r")
        if up_r and st.button("Upload Results"):
            df_r = pd.read_csv(up_r)
            for _, row in df_r.iterrows():
                r_data = {
                    "name": str(row['name']), "distance": str(row['distance']), "location": str(row['location']),
                    "race_date": str(row['race_date']), "time_display": str(row['time_display']),
                    "time_seconds": int(row['time_seconds']), "gender": str(row['gender']), "dob": str(row['dob'])
                }
                r.rpush("race_results", json.dumps(r_data))
            rebuild_leaderboard_cache(r)
            st.success(f"Added {len(df_r)} race results.")

    # 3. Bulk Championship Results
    with st.expander("Import Championship Results (CSV)"):
        st.caption("Required Columns: name, race_name, date, points, category, gender")
        up_c = st.file_uploader("Choose Champ CSV", type="csv", key="up_c")
        if up_c and st.button("Upload Champ Results"):
            df_c = pd.read_csv(up_c)
            for _, row in df_c.iterrows():
                c_data = {
                    "name": str(row['name']), "race_name": str(row['race_name']), "date": str(row['date']),
                    "points": float(row['points']), "category": str(row['category']), "gender": str(row['gender'])
                }
                r.rpush("champ_results_final", json.dumps(c_data))
            rebuild_leaderboard_cache(r)
            st.success(f"Added {len(df_c)} championship entries.")

with tabs[3]: # --- SYNC & MAINTENANCE ---
    st.subheader("Maintenance Tools")
    if st.button("🔄 Force Rebuild Leaderboard Caches", use_container_width=True):
        if rebuild_leaderboard_cache(r):
            st.success("Cache refreshed.")
        else:
            st.error("Refresh failed.")

    st.divider()
    with st.expander("🗑️ Danger Zone"):
        if st.button("Clear Pending Approval Queues"):
            r.delete("pending_results")
            r.delete("champ_pending")
            st.warning("Pending queues cleared.")
