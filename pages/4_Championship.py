import streamlit as st
import json
import pandas as pd
from helpers import get_redis, time_to_seconds

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("🏅 Championship Admin")
tab_cal, tab_app, tab_man, tab_log = st.tabs([
    "Calendar Editor", "Review Submissions", "Manual Point Entry", "Master Points Log"
])

# --- 1. CALENDAR EDITOR ---
with tab_cal:
    cal_raw = r.get("champ_calendar_2026")
    cal = json.loads(cal_raw) if cal_raw else []
    st.subheader("Manage 2026 Calendar")
    new_cal = []
    for i in range(15):
        ra = cal[i] if i < len(cal) else {"date": "TBC", "name": "TBC"}
        with st.expander(f"Race {i+1}: {ra['name']} ({ra['date']})"):
            d = st.text_input("Date (YYYY-MM-DD)", ra['date'], key=f"cd_{i}")
            n = st.text_input("Race Name", ra['name'], key=f"cn_{i}")
            new_cal.append({"date": d, "name": n})
    if st.button("Save Full Calendar"):
        r.set("champ_calendar_2026", json.dumps(new_cal))
        st.success("Calendar Updated!")

# --- 2. REVIEW SUBMISSIONS ---
with tab_app:
    st.subheader("Pending Champ Submissions")
    c_pend = r.lrange("champ_pending", 0, -1)
    raw_mem = r.lrange("members", 0, -1)
    member_names = sorted([json.loads(m)['name'] for m in raw_mem])

    if not c_pend:
        st.info("No pending championship submissions.")

    for i, cj in enumerate(c_pend):
        cp = json.loads(cj)
        with st.container(border=True):
            st.markdown(f"#### Review: {cp['name']}")
            c1, c2, c3 = st.columns(3)
            match_idx = member_names.index(cp['name']) if cp['name'] in member_names else 0
            edit_name = c1.selectbox("Correct Member", member_names, index=match_idx, key=f"c_n_{i}")
            edit_race = c2.text_input("Race Name", value=cp['race_name'], key=f"c_r_{i}")
            edit_time = c3.text_input("Runner's Time", value=cp['time_display'], key=f"c_t_{i}")
            
            w_col, p_col = st.columns([1, 2])
            win_time = w_col.text_input("🏆 Category Winner Time", placeholder="HH:MM:SS", key=f"c_w_{i}")
            if win_time:
                try:
                    u_sec = time_to_seconds(edit_time); w_sec = time_to_seconds(win_time)
                    p_col.metric("Points Preview", f"{round((w_sec/u_sec)*100, 1)} pts")
                except: p_col.error("Format: HH:MM:SS")

            b1, b2, _ = st.columns([1,1,3])
            if b1.button("✅ Calculate & Approve", key=f"c_ok_{i}"):
                if win_time:
                    u_sec, w_sec = time_to_seconds(edit_time), time_to_seconds(win_time)
                    pts = round((w_sec / u_sec) * 100, 1)
                    r.rpush("champ_results_final", json.dumps({"name":edit_name, "race":edit_race, "points":pts, "date":cp.get('date','2026-01-01')}))
                    r.lrem("champ_pending", 1, cj); st.rerun()
                else: st.error("Enter Winner's Time")
            if b2.button("🗑️ Reject", key=f"c_del_{i}"):
                r.lrem("champ_pending", 1, cj); st.rerun()

# --- 3. MANUAL POINT ENTRY ---
with tab_man:
    st.subheader("➕ Direct Point Entry")
    with st.form("manual_points"):
        m_name = st.selectbox("Runner", member_names)
        r_name = st.text_input("Race Name")
        u_time = st.text_input("Runner Time (HH:MM:SS)")
        w_time = st.text_input("Winner Time (HH:MM:SS)")
        r_date = st.date_input("Race Date")
        if st.form_submit_button("Add Points"):
            u_sec, w_sec = time_to_seconds(u_time), time_to_seconds(w_time)
            pts = round((w_sec / u_sec) * 100, 1)
            r.rpush("champ_results_final", json.dumps({"name":m_name, "race":r_name, "points":pts, "date":str(r_date)}))
            st.success("Points Added!")

# --- 4. MASTER POINTS LOG (The Edit/Delete Tool) ---
with tab_log:
    st.subheader("📋 Approved Points History")
    all_points = r.lrange("champ_results_final", 0, -1)
    
    if all_points:
        # We show them in a list with delete buttons
        for idx, pj in enumerate(all_points):
            p = json.loads(pj)
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.write(f"**{p['name']}**")
                col1.caption(f"{p['race']} ({p['date']})")
                col2.write(f"Points: **{p['points']}**")
                if col3.button("🗑️ Delete", key=f"log_del_{idx}"):
                    # Using WIPE method to ensure clean removal from Redis list
                    r.lset("champ_results_final", idx, "WIPE")
                    r.lrem("champ_results_final", 1, "WIPE")
                    st.rerun()
    else:
        st.info("No approved points in the log yet.")
