import streamlit as st
import pandas as pd
import json
from helpers import get_redis, time_to_seconds, format_time_string

# Set page title to BBPB-Admin
st.set_page_config(page_title="BBPB-Admin", layout="wide")

r = get_redis()

# Auth check (Persistence)
if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page.")
    st.stop()

st.title("⚙️ BBPB-Admin: System & Backups")

# --- 1. PUBLIC VISIBILITY CONTROL ---
st.subheader("🌐 Public Site Controls")
current_viz = r.get("show_champ_tab") == "True"
if st.toggle("Show Championship Page on Public Site", value=current_viz):
    r.set("show_champ_tab", "True")
else:
    r.set("show_champ_tab", "False")

st.divider()

# --- 2. DATA BACKUPS & EXPORTS ---
st.subheader("💾 Data Backups & Exports")
st.info("Download these CSVs regularly to keep a local backup of your club records.")

b_col1, b_col2, b_col3 = st.columns(3)

# --- BACKUP MEMBERS ---
with b_col1:
    raw_m = r.lrange("members", 0, -1)
    if raw_m:
        df_m = pd.DataFrame([json.loads(x) for x in raw_m])
        st.download_button(
            label="📥 Download Member List",
            data=df_m.to_csv(index=False),
            file_name=f"bbpb_members_backup_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.button("No Members Found", disabled=True, use_container_width=True)

# --- BACKUP PB RECORDS ---
with b_col2:
    raw_p = r.lrange("race_results", 0, -1)
    if raw_p:
        df_p = pd.DataFrame([json.loads(x) for x in raw_p])
        st.download_button(
            label="📥 Download PB Records",
            data=df_p.to_csv(index=False),
            file_name=f"bbpb_pb_records_backup_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.button("No PBs Found", disabled=True, use_container_width=True)

# --- BACKUP CHAMPIONSHIP ---
with b_col3:
    raw_c = r.lrange("champ_results_final", 0, -1)
    if raw_c:
        df_c = pd.DataFrame([json.loads(x) for x in raw_c])
        st.download_button(
            label="📥 Download Champ Points",
            data=df_c.to_csv(index=False),
            file_name=f"bbpb_champ_points_backup_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.button("No Champ Points Found", disabled=True, use_container_width=True)

st.divider()

# --- 3. SETTINGS & LOGO ---
st.subheader("🎨 Branding & Rules")
col_s1, col_s2 = st.columns(2)
with col_s1:
    logo_url = st.text_input("Club Logo URL", r.get("club_logo_url") or "")
    if st.button("Update Logo"):
        r.set("club_logo_url", logo_url)
        st.success("Logo Updated")

with col_s2:
    mode = r.get("age_mode") or "10Y"
    new_mode = st.radio("Age Category Mode", ["10Y", "5Y"], index=0 if mode=="10Y" else 1)
    if st.button("Save Age Mode"): 
        r.set("age_mode", new_mode)
        st.success("Mode Saved")

st.divider()

# --- 4. BULK UPLOADS ---
st.subheader("📤 Bulk Import Tools")
col_up1, col_up2 = st.columns(2)
with col_up1:
    st.caption("Import Members (CSV must have: name, gender, dob)")
    m_file = st.file_uploader("Upload Members CSV", type="csv")
    if m_file and st.button("Process Member Import"):
        df_im = pd.read_csv(m_file)
        for _, row in df_im.iterrows():
            r.rpush("members", json.dumps({"name": row['name'], "gender": row['gender'], "dob": str(row['dob']), "status": "Active"}))
        st.success("Members Imported!")

with col_up2:
    st.caption("Import PBs (CSV must have: name, distance, time, location, date)")
    r_file = st.file_uploader("Upload PBs CSV", type="csv")
    if r_file and st.button("Process PB Import"):
        m_list = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
        df_ir = pd.read_csv(r_file)
        for _, row in df_ir.iterrows():
            if row['name'] in m_list:
                m = m_list[row['name']]
                entry = {
                    "name": row['name'], "gender": m['gender'], "dob": m['dob'], 
                    "distance": row['distance'], "time_seconds": time_to_seconds(row['time']), 
                    "time_display": format_time_string(row['time']), "location": row['location'], 
                    "race_date": str(row['date'])
                }
                r.rpush("race_results", json.dumps(entry))
        st.success("PBs Imported!")
