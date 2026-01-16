import streamlit as st
import json
from helpers import get_redis, time_to_seconds

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("🏅 Championship Admin")
tab_cal, tab_app, tab_man = st.tabs(["Calendar Editor", "Pending Approvals", "Manual Point Entry"])

# ... (Calendar Editor and Pending logic same as before) ...

with tab_man:
    st.subheader("➕ Manually Add Points")
    raw_mem = r.lrange("members", 0, -1)
    members = sorted([json.loads(m)['name'] for m in raw_mem])
    
    cal_raw = r.get("champ_calendar_2026")
    races = [rc['name'] for rc in json.loads(cal_raw)] if cal_raw else ["No Races Found"]

    with st.form("manual_champ_points"):
        m_name = st.selectbox("Select Runner", members)
        r_name = st.selectbox("Select Race", races)
        u_time = st.text_input("Runner's Time (HH:MM:SS)")
        w_time = st.text_input("Category Winner's Time (HH:MM:SS)")
        r_date = st.date_input("Race Date")
        
        if st.form_submit_button("Calculate & Add Points"):
            if u_time and w_time:
                u_sec = time_to_seconds(u_time)
                w_sec = time_to_seconds(w_time)
                pts = round((w_sec / u_sec) * 100, 1)
                
                entry = {"name": m_name, "race": r_name, "points": pts, "date": str(r_date)}
                r.rpush("champ_results_final", json.dumps(entry))
                st.success(f"Added {pts} points for {m_name}!")
            else:
                st.error("Please enter both times.")
