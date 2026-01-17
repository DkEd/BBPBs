import streamlit as st
import json
import pandas as pd
from datetime import datetime
from helpers import get_redis, get_club_settings, get_category, rebuild_leaderboard_cache

st.set_page_config(page_title="Champ Management", layout="wide")
r = get_redis()
settings = get_club_settings()

if not st.session_state.get('authenticated'):
    st.warning("Please login on the Home page.")
    st.stop()

st.header("🏅 Championship Management")
tabs = st.tabs(["📥 Pending Approvals", "🗓️ Calendar Setup", "📊 Championship Log", "🏆 Leaderboard"])

def get_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
    except: return 0
    return 0

# Pre-load members for category calculation
raw_mems = r.lrange("members", 0, -1)
member_db = {json.loads(m)['name']: json.loads(m) for m in raw_mems}

# Pre-load calendar for auto-assignment
cal_raw = r.get("champ_calendar_2026")
champ_calendar = json.loads(cal_raw) if cal_raw else []

with tabs[0]: # --- PENDING APPROVALS ---
    pending = r.lrange("champ_pending", 0, -1)
    if not pending:
        st.info("No pending championship results.")
    else:
        for i, p_raw in enumerate(pending):
            p = json.loads(p_raw)
            with st.expander(f"Review: {p['name']} - {p['race_name']}"):
                st.write(f"**Submitted Time:** {p['time_display']}")
                st.write(f"**Submitted Date/Location:** {p.get('date')} / {p.get('race_name')}")
                
                if not champ_calendar:
                    st.error("Setup the calendar in the next tab first.")
                    continue

                # 1. Select which Calendar Race this belongs to
                race_options = [f"Race {idx+1}: {rc.get('name')}" for idx, rc in enumerate(champ_calendar)]
                sel_race_str = st.selectbox("Assign to Calendar Race", race_options, key=f"conf_race_{i}")
                race_idx = race_options.index(sel_race_str)
                is_race_15 = (race_idx == 14)

                col1, col2 = st.columns(2)
                
                # 2. Points Calculation using Winner's Time
                win_time = col1.text_input(f"Winner's Time (MM:SS or HH:MM:SS)", "00:00", key=f"win_{i}")
                runner_sec = get_seconds(p['time_display'])
                winner_sec = get_seconds(win_time)
                calc_pts = round((winner_sec / runner_sec) * 100, 2) if winner_sec > 0 else 0.0
                
                pts = col2.number_input("Final Points to Award", 0.0, 100.0, calc_pts, key=f"pts_{i}")
                st.caption(f"Calculated based on winner: {calc_pts}")

                # 3. PB Leaderboard Assignment
                st.markdown("---")
                log_pb = st.checkbox("Also add to Main PB Leaderboard?", value=True, key=f"log_pb_{i}")
                
                if is_race_15:
                    st.warning("🏆 Race 15 (Any Marathon) detected. Locked to 'Marathon' PB Category.")
                    pb_dist = "Marathon"
                else:
                    pb_dist = st.selectbox("PB Category", ["5k", "10k", "10 Mile", "HM", "Marathon"], key=f"pb_dist_{i}")

                if st.button("✅ Approve Result", key=f"app_{i}"):
                    m_info = member_db.get(p['name'], {})
                    # Logic: Use Calendar date for 1-14, User's submitted date for Race 15
                    final_date = p.get('date') if is_race_15 else champ_calendar[race_idx]['date']
                    cat = get_category(m_info.get('dob','2000-01-01'), final_date, settings['age_mode'])
                    
                    # Entry for Championship Log
                    champ_entry = {
                        "name": p['name'], 
                        "race_name": p['race_name'], 
                        "date": final_date,
                        "points": pts, 
                        "category": cat, 
                        "gender": m_info.get('gender', 'U')
                    }
                    r.rpush("champ_results_final", json.dumps(champ_entry))
                    
                    # Entry for PB Leaderboard
                    if log_pb:
                        pb_entry = {
                            "name": p['name'], 
                            "distance": pb_dist, 
                            "location": p['race_name'],
                            "race_date": final_date, 
                            "time_display": p['time_display'],
                            "time_seconds": runner_sec, 
                            "gender": m_info.get('gender', 'U'),
                            "dob": m_info.get('dob', '2000-01-01')
                        }
                        r.rpush("race_results", json.dumps(pb_entry))
                    
                    rebuild_leaderboard_cache(r)
                    r.lset("champ_pending", i, "WIPE")
                    r.lrem("champ_pending", 1, "WIPE")
                    st.success(f"Approved {p['name']}!")
                    st.rerun()

with tabs[1]: # --- CALENDAR SETUP ---
    st.subheader("15-Race Calendar Setup")
    if len(champ_calendar) < 15:
        champ_calendar = [{"name": "TBC", "date": "2026-01-01", "distance": "TBC", "terrain": "Road"} for _ in range(15)]
    
    with st.form("cal_form"):
        updated_cal = []
        for i in range(15):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            default_name = "Any Marathon (Power of 10)" if i == 14 else champ_calendar[i]['name']
            n = c1.text_input(f"Race {i+1}", default_name, key=f"n_{i}")
            
            try: d_val = datetime.strptime(champ_calendar[i]['date'], '%Y-%m-%d')
            except: d_val = datetime(2026, 1, 1)
            
            d = c2.date_input("Date", d_val, key=f"d_{i}")
            di = c3.selectbox("Dist", ["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"], 
                              index=["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"].index(champ_calendar[i].get('distance', 'TBC')),
                              key=f"di_{i}")
            te = c4.selectbox("Terrain", ["Road", "Trail", "Fell", "XC"], 
                              index=["Road", "Trail", "Fell", "XC"].index(champ_calendar[i].get('terrain', 'Road')),
                              key=f"te_{i}")
            updated_cal.append({"name": n, "date": str(d), "distance": di, "terrain": te})
            
        if st.form_submit_button("Save Calendar"):
            r.set("champ_calendar_2026", json.dumps(updated_cal))
            rebuild_leaderboard_cache(r)
            st.success("Calendar Saved and Cache Rebuilt!")
            st.rerun()

with tabs[2]: # --- CHAMPIONSHIP LOG ---
    final_raw = r.lrange("champ_results_final", 0, -1)
    if final_raw:
        data = [json.loads(x) for x in final_raw]
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        e_col, d_col = st.columns(2)
        with e_col:
            with st.expander("📝 Edit Result"):
                idx = st.number_input("Index to Edit", 0, len(df)-1, 0, key="c_edit_idx")
                t_to_edit = data[idx]
                with st.form("c_edit_form"):
                    new_pts = st.number_input("Points", 0.0, 100.0, float(t_to_edit.get('points', 0)))
                    new_cat = st.text_input("Category", t_to_edit.get('category'))
                    if st.form_submit_button("Save Changes"):
                        t_to_edit['points'] = new_pts
                        t_to_edit['category'] = new_cat
                        r.lset("champ_results_final", int(idx), json.dumps(t_to_edit))
                        rebuild_leaderboard_cache(r)
                        st.success("Updated!")
                        st.rerun()
        with d_col:
            with st.expander("🗑️ Delete Result"):
                del_idx = st.number_input("Index to Delete", 0, len(df)-1, 0, key="c_del_idx")
                if st.button("Confirm Deletion"):
                    r.lset("champ_results_final", int(del_idx), "WIPE")
                    r.lrem("champ_results_final", 1, "WIPE")
                    rebuild_leaderboard_cache(r)
                    st.success("Deleted!")
                    st.rerun()
    else:
        st.info("No final results found in the championship log.")

with tabs[3]: # --- LEADERBOARD ---
    st.subheader("Current Championship Standings (Cached)")
    cache = r.get("cached_champ_standings")
    if cache:
        st.table(pd.read_json(cache))
    else:
        st.info("Standings not yet generated. Approve a result or rebuild cache to view.")
