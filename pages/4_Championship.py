import streamlit as st
import json
import pandas as pd
from helpers import get_redis, time_to_seconds, get_category

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("🏅 Championship Admin")
tabs = st.tabs(["🗓️ Calendar Editor", "⏱️ Set Category Winners", "📥 Point Approvals", "📊 Final Log"])

# --- DATA LOADING ---
cal_raw = r.get("champ_calendar_2026")
if not cal_raw:
    cal = [{"date": "TBC", "name": "TBC", "distance": "TBC", "terrain": "Road"} for _ in range(15)]
else:
    cal = json.loads(cal_raw)

champ_races = [rc['name'] for rc in cal if rc['name'] != "TBC"]
categories = ["Senior", "V35", "V40", "V45", "V50", "V55", "V60", "V65", "V70", "V75+"]

# --- TAB 1: CALENDAR ---
with tabs[0]:
    new_cal = []
    for i in range(15):
        ra = cal[i] if i < len(cal) else {"date": "TBC", "name": "TBC", "distance": "TBC", "terrain": "Road"}
        with st.expander(f"Race {i+1}: {ra['name']}"):
            c1, c2, c3 = st.columns(3)
            d = c1.text_input("Date", ra.get('date', 'TBC'), key=f"d_{i}")
            n = c2.text_input("Name", ra.get('name', 'TBC'), key=f"n_{i}")
            dist = c3.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"], 
                               index=["5k", "10k", "10 Mile", "HM", "Marathon"].index(ra.get('distance', '5k')) if ra.get('distance') in ["5k", "10k", "10 Mile", "HM", "Marathon"] else 0,
                               key=f"dist_cal_{i}")
            new_cal.append({"date": d, "name": n, "distance": dist, "terrain": "Road"})
    if st.button("Save Calendar"):
        r.set("champ_calendar_2026", json.dumps(new_cal))
        st.success("Calendar Saved")

# --- TAB 2: WINNER GRID ---
with tabs[1]:
    st.subheader("Enter Category Winner Times")
    sel_race = st.selectbox("Select Race to Update", [""] + champ_races)
    
    if sel_race:
        grid = json.loads(r.get("champ_winners_grid") or "{}")
        if sel_race not in grid:
            grid[sel_race] = {}
            
        m_col, f_col = st.columns(2)
        for gen in ["Male", "Female"]:
            with m_col if gen == "Male" else f_col:
                st.write(f"**{gen} Winners**")
                for cat in categories:
                    key_name = f"{gen}_{cat}"
                    grid[sel_race][key_name] = st.text_input(
                        f"{cat} Time", 
                        grid[sel_race].get(key_name, ""), 
                        key=f"win_{sel_race}_{gen}_{cat}"
                    )
        
        if st.button("Save Winner Times"):
            r.set("champ_winners_grid", json.dumps(grid))
            st.success(f"Winners updated for {sel_race}")

# --- TAB 3: POINT APPROVALS ---
with tabs[2]:
    c_pend = r.lrange("champ_pending", 0, -1)
    grid = json.loads(r.get("champ_winners_grid") or "{}")
    mems = {m['name']: m for m in [json.loads(x) for x in r.lrange("members", 0, -1)]}

    if not c_pend:
        st.info("No pending championship submissions.")
    
    for i, cj in enumerate(c_pend):
        cp = json.loads(cj)
        m = mems.get(cp['name'])
        
        if m:
            cat = get_category(m['dob'], cp['date'], mode="5Y")
            win_time = grid.get(cp['race_name'], {}).get(f"{m['gender']}_{cat}", "")
            # Find the distance set in the calendar for this race
            race_dist = next((rc['distance'] for rc in cal if rc['name'] == cp['race_name']), "5k")
            
            with st.container(border=True):
                st.write(f"**{cp['name']}** ({m['gender']} {cat})")
                st.write(f"Race: {cp['race_name']} | Distance: {race_dist} | Time: {cp['time_display']}")
                
                if win_time:
                    pts = round((time_to_seconds(win_time) / time_to_seconds(cp['time_display'])) * 100, 1)
                    st.write(f"Winner Time: {win_time} | Points: **{pts}**")
                    
                    if st.button("✅ Approve (Post to Points & PBs)", key=f"c_ap_{i}"):
                        # 1. ADD TO CHAMPIONSHIP FINAL LOG
                        champ_entry = {
                            "name": cp['name'], 
                            "race": cp['race_name'], 
                            "points": pts, 
                            "date": cp['date']
                        }
                        r.rpush("champ_results_final", json.dumps(champ_entry))
                        
                        # 2. ADD TO PB LEADERBOARD (race_results)
                        pb_entry = {
                            "name": cp['name'],
                            "gender": m['gender'],
                            "dob": m['dob'],
                            "distance": race_dist,
                            "time_seconds": time_to_seconds(cp['time_display']),
                            "time_display": cp['time_display'],
                            "location": cp['race_name'],
                            "race_date": cp['date']
                        }
                        r.rpush("race_results", json.dumps(pb_entry))
                        
                        # 3. CLEAN UP
                        r.lrem("champ_pending", 1, cj)
                        st.rerun()
                else:
                    st.warning(f"Enter {m['gender']} {cat} winner time in Tab 2 to approve.")
        
        if st.button("❌ Reject", key=f"c_rj_{i}"):
            r.lrem("champ_pending", 1, cj)
            st.rerun()

# --- TAB 4: FINAL LOG ---
with tabs[3]:
    st.subheader("Final Championship Points Log")
    final = r.lrange("champ_results_final", 0, -1)
    if final:
        final_list = [json.loads(f) for f in final]
        for idx, entry in enumerate(final_list):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{entry['name']}** | {entry['race']} | **{entry['points']} pts**")
                if c2.button("🗑️ Delete Points Entry", key=f"f_del_{idx}"):
                    r.lrem("champ_results_final", 1, json.dumps(entry))
                    st.rerun()
    else:
        st.info("No final points recorded yet.")
