import streamlit as st
import json
import pandas as pd
from helpers import get_redis, time_to_seconds

# Browser Title
st.set_page_config(page_title="BBPB-Admin", layout="wide")

r = get_redis()
if not st.session_state.get('authenticated'): 
    st.error("Please login on the Home page.")
    st.stop()

st.header("🏅 BBPB-Admin: Championship Management")
tab_cal, tab_app, tab_man, tab_log = st.tabs(["Calendar Setup", "Review Submissions", "Manual Entry", "Master Log"])

# Common Data
cal_raw = r.get("champ_calendar_2026")
calendar = json.loads(cal_raw) if cal_raw else []
champ_races = [rc['name'] for rc in calendar if rc['name'] != "TBC"]

raw_mem = r.lrange("members", 0, -1)
member_names = sorted([json.loads(m)['name'] for m in raw_mem])

# 1. Calendar Setup
with tab_cal:
    st.subheader("Set the 15 Championship Races")
    new_cal = []
    for i in range(15):
        ra = calendar[i] if i < len(calendar) else {"date": "2026-01-01", "name": "TBC"}
        with st.expander(f"Race {i+1}: {ra['name']}"):
            d = st.text_input("Date (YYYY-MM-DD)", ra['date'], key=f"cd_{i}")
            n = st.text_input("Race Name", ra['name'], key=f"cn_{i}")
            new_cal.append({"date": d, "name": n})
    if st.button("💾 Save Calendar"): 
        r.set("champ_calendar_2026", json.dumps(new_cal))
        st.success("Calendar updated successfully!")

# 2. Review Submissions
with tab_app:
    c_pend = r.lrange("champ_pending", 0, -1)
    if not c_pend:
        st.info("No pending championship results.")
    
    for i, cj in enumerate(c_pend):
        cp = json.loads(cj)
        with st.container(border=True):
            st.markdown(f"#### Submission: {cp['name']}")
            c1, c2, c3 = st.columns(3)
            
            # Pre-filled based on submission
            en = c1.selectbox("Confirm Member", member_names, index=member_names.index(cp['name']) if cp['name'] in member_names else 0, key=f"c_n_{i}")
            er = c2.selectbox("Confirm Race", champ_races, index=champ_races.index(cp['race_name']) if cp['race_name'] in champ_races else 0, key=f"c_r_{i}")
            et = c3.text_input("Time (HH:MM:SS)", value=cp['time_display'], key=f"c_t_{i}")
            
            # Winner Time for calculation
            win_time = st.text_input("🏆 Category Winner Time (HH:MM:SS)", placeholder="00:15:30", key=f"c_w_{i}")
            
            b1, b2, _ = st.columns([1,1,2])
            if b1.button("✅ Approve Points", key=f"c_ok_{i}"):
                if win_time:
                    u_s = time_to_seconds(et)
                    w_s = time_to_seconds(win_time)
                    # Points Formula: (Winner Time / User Time) * 100
                    pts = round((w_s / u_s) * 100, 2)
                    
                    final_date = next((rc['date'] for rc in calendar if rc['name'] == er), "2026-01-01")
                    
                    r.rpush("champ_results_final", json.dumps({
                        "name": en, "race": er, "points": pts, "date": final_date
                    }))
                    r.lrem("champ_pending", 1, cj)
                    st.success(f"Approved: {pts} pts")
                    st.rerun()
                else:
                    st.error("Please enter the Winner's Time.")
            
            if b2.button("🗑️ Reject", key=f"c_rej_{i}"):
                r.lrem("champ_pending", 1, cj)
                st.rerun()

# 3. Manual Entry
with tab_man:
    st.subheader("Manually Add Points")
    with st.form("man_pts"):
        m_name = st.selectbox("Runner", member_names)
        r_name = st.selectbox("Race", champ_races)
        u_t = st.text_input("Runner Time (HH:MM:SS)")
        w_t = st.text_input("Winner Time (HH:MM:SS)")
        
        if st.form_submit_button("Add Points Record"):
            if u_t and w_t:
                u_s = time_to_seconds(u_t)
                w_s = time_to_seconds(w_t)
                pts = round((w_s / u_s) * 100, 2)
                f_date = next((rc['date'] for rc in calendar if rc['name'] == r_name), "2026-01-01")
                
                r.rpush("champ_results_final", json.dumps({
                    "name": m_name, "race": r_name, "points": pts, "date": f_date
                }))
                st.success(f"Added {pts} points for {m_name}")
            else:
                st.error("Please fill in both times.")

# 4. Master Log
with tab_log:
    st.subheader("Finalized Points Log")
    all_p = r.lrange("champ_results_final", 0, -1)
    if all_p:
        log_data = []
        for idx, pj in enumerate(all_p):
            p = json.loads(pj)
            p['idx'] = idx
            log_data.append(p)
        
        log_df = pd.DataFrame(log_data)
        st.dataframe(log_df[['date', 'name', 'race', 'points']], use_container_width=True, hide_index=True)
        
        to_del = st.selectbox("Select entry to delete", options=[(x['idx'], f"{x['name']} - {x['race']}") for x in log_data], format_func=lambda x: x[1])
        if st.button("🗑️ Delete Selected Entry"):
            r.lset("champ_results_final", to_del[0], "WIPE")
            r.lrem("champ_results_final", 1, "WIPE")
            st.rerun()
    else:
        st.info("No championship points have been finalized yet.")
