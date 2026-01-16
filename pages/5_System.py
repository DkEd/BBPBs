import streamlit as st
import pandas as pd
import json
from helpers import get_redis, time_to_seconds, format_time_string

r = get_redis()
if not st.session_state.get('authenticated'): 
    st.error("Please login on the Home page.")
    st.stop()

st.header("⚙️ System Tools & Bulk Uploads")

# --- BULK UPLOAD SECTION ---
st.subheader("📤 Bulk Import")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**1. Import Members**")
    st.caption("CSV columns: name, gender, dob (YYYY-MM-DD)")
    m_file = st.file_uploader("Upload Members CSV", type="csv")
    if m_file and st.button("Process Members"):
        df_m = pd.read_csv(m_file)
        for _, row in df_m.iterrows():
            r.rpush("members", json.dumps({
                "name": row['name'], "gender": row['gender'], 
                "dob": str(row['dob']), "status": "Active"
            }))
        st.success("Members Imported!")

with col2:
    st.markdown("**2. Import Race Results**")
    st.caption("CSV columns: name, distance, time, location, date")
    r_file = st.file_uploader("Upload PBs CSV", type="csv")
    if r_file and st.button("Process PBs"):
        m_list = [json.loads(m) for m in r.lrange("members", 0, -1)]
        m_map = {m['name']: m for m in m_list}
        df_r = pd.read_csv(r_file)
        for _, row in df_r.iterrows():
            if row['name'] in m_map:
                m = m_map[row['name']]
                entry = {
                    "name": row['name'], "gender": m['gender'], "dob": m['dob'],
                    "distance": row['distance'], "time_seconds": time_to_seconds(row['time']),
                    "time_display": format_time_string(row['time']),
                    "location": row['location'], "race_date": str(row['date'])
                }
                r.rpush("race_results", json.dumps(entry))
        st.success("PBs Imported!")

st.divider()

# --- SETTINGS ---
st.subheader("🔧 Club Settings")
c1, c2 = st.columns(2)
with c1:
    logo_url = st.text_input("Club Logo URL", r.get("club_logo_url") or "")
    if st.button("Update Logo"):
        r.set("club_logo_url", logo_url)
        st.success("Logo Updated")

with c2:
    mode = r.get("age_mode") or "10Y"
    new_mode = st.radio("Age Category Mode", ["10Y", "5Y"], index=0 if mode=="10Y" else 1)
    if st.button("Save Age Mode"): 
        r.set("age_mode", new_mode)
        st.success("Mode Saved")

st.divider()

# --- BACKUPS ---
if st.button("💾 Generate PB Backup CSV"):
    res_df = pd.DataFrame([json.loads(x) for x in r.lrange("race_results", 0, -1)])
    st.download_button("Download CSV", res_df.to_csv(index=False), "pb_backup.csv")
