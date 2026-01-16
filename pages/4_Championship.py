import streamlit as st
import json
import pandas as pd
from helpers import get_redis, time_to_seconds, get_category

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'): 
    st.error("Please login on the Home page.")
    st.stop()

st.header("🏅 BBPB-Admin: Championship Management")
tabs = st.tabs(["🗓️ Calendar", "⏱️ Set 5-Year Winners", "📥 Review & Approve", "📊 Master Log"])

# --- DATA LOADING ---
cal_raw = r.get("champ_calendar_2026")
calendar = json.loads(cal_raw) if cal_raw else []
champ_races = [rc['name'] for rc in calendar if rc['name'] != "TBC"]

# Force 5Y Categories for Championship Grid
categories = ["Senior", "V35", "V40", "V45", "V50", "V55", "V60", "V65", "V70", "V75+"]

# Load Winners Grid
winners_raw = r.get("champ_winners_grid")
winners_grid = json.loads(winners_raw) if winners_raw else {}

# --- TAB 1: CALENDAR ---
with tabs[0]:
    st.subheader("Race Calendar")
    new_cal = []
    for i in range(15):
        ra = calendar[i] if i < len(calendar) else {"date": "2026-01-01", "name": "TBC"}
        c1, c2 = st.columns(2)
        d = c1.text_input(f"Date R{i+1}", ra['date'], key=f"d_{i}")
        n = c2.text_input(f"Name R{i+1}", ra['name'], key=f"n_{i}")
        new_cal.append({"date": d, "name": n})
    if st.button("💾 Save Calendar"):
        r.set("champ_calendar_2026", json.dumps(new_cal))
        st.success("Calendar updated!")

# --- TAB 2: SET WINNER GRID ---
with tabs[1]:
    st.subheader("🏆 Set Winner Times (5-Year Bands)")
    sel_race = st.selectbox("Select Race", [""] + champ_races)
    
    if sel_race:
        if sel_race not in winners_grid: winners_grid[sel_race] = {}
        st.info(f"Enter the fastest time for each category in **{sel_race}**.")
        
        m_col, f_col = st.columns(2)
        for gender in ["Male", "Female"]:
            col = m_col if gender == "Male" else f_col
            with col:
                st.markdown(f"**{gender}**")
                for cat in categories:
                    key = f"{gender}_{cat}"
                    existing = winners_grid[sel_race].get(key, "")
                    winners_grid[sel_race][key] = st.text_input(
                        f"{cat}", value=existing, placeholder="HH:MM:SS", key=f"w_{sel_race}_{key}"
                    )
        
        if st.button("💾 Save Grid"):
            r.set("champ_winners_grid", json.dumps(winners_grid))
            st.success("Winner times saved.")

# --- TAB 3: REVIEW ---
with tabs[2]:
    c_pend = r.lrange("champ_pending", 0, -1)
    raw_mem = r.lrange("members", 0, -1)
    members_lookup = {json.loads(m)['name']: json.loads(m) for m in raw_mem}
    
    if not c_pend:
        st.info("No pending submissions.")
    
    for i, cj in enumerate(c_pend):
        cp = json.loads(cj)
        m_info = members_lookup.get(cp['name'])
        
        if m_info:
            # FORCE 5Y MODE here for calculation
            cat = get_category(m_info['dob'], cp['date'], "5Y")
            lookup_key = f"{m_info['gender']}_{cat}"
            win_time_str = winners_grid.get(cp['race_name'], {}).get(lookup_key, "")
            
            with st.container(border=True):
                st.markdown(f"#### {cp['name']} ({lookup_key})")
                st.write(f"Race: **{cp['race_name']}** | Time: **{cp['time_display']}**")
                
                if not win_time_str or win_time_str in ["", "00:00:00"]:
                    st.warning(f"⚠️ Missing winner time for {lookup_key}. Please set it in Tab 2.")
                else:
                    u_s = time_to_seconds(cp['time_display'])
                    w_s = time_to_seconds(win_time_str)
                    try:
                        pts = round((w_s / u_s) * 100, 2)
                        st.success(f"Calculated: **{pts} Points** (Winner: {win_time_str})")
                        if st.button(f"✅ Approve", key=f"ap_{i}"):
                            r.rpush("champ_results_final", json.dumps({
                                "name": cp['name'], "race": cp['race_name'], "points": pts, "date": cp['date']
                            }))
                            r.lrem("champ_pending", 1, cj); st.rerun()
                    except:
                        st.error("Time format error.")
                
                if st.button("🗑️ Reject", key=f"rj_{i}"):
                    r.lrem("champ_pending", 1, cj); st.rerun()

# --- TAB 4: LOG ---
with tabs[3]:
    all_p = r.lrange("champ_results_final", 0, -1)
    if all_p:
        df = pd.DataFrame([json.loads(x) for x in all_p])
        st.dataframe(df.sort_values(['date', 'name'], ascending=[False, True]), use_container_width=True)
        if st.button("⚠️ Clear All Points"):
             if st.checkbox("Confirm Delete"): r.delete("champ_results_final"); st.rerun()
