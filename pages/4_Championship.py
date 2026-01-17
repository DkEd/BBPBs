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

raw_mems = r.lrange("members", 0, -1)
member_db = {json.loads(m)['name']: json.loads(m) for m in raw_mems}

# Load calendar for auto-population
cal_raw = r.get("champ_calendar_2026")
champ_calendar = json.loads(cal_raw) if cal_raw else []

with tabs[0]: # --- PENDING APPROVALS ---
    pending = r.lrange("champ_pending", 0, -1)
    if not pending:
        st.info("No pending results.")
    else:
        for i, p_raw in enumerate(pending):
            p = json.loads(p_raw)
            with st.expander(f"Review: {p['name']} - {p['race_name']}"):
                st.write(f"**Runner's Time:** {p['time_display']}")
                
                # Race Selection Logic
                race_options = [f"Race {idx+1}: {r.get('name')}" for idx, r in enumerate(champ_calendar)]
                if not race_options:
                    st.error("Please setup the Calendar first.")
                    st.stop()
                
                selected_race_str = st.selectbox("Assign to Championship Race", race_options, key=f"sel_race_{i}")
                race_idx = race_options.index(selected_race_str)
                
                # Logic for Race 15 vs Others
                is_race_15 = (race_idx == 14) # Index 14 is the 15th race
                
                col1, col2 = st.columns(2)
                
                if is_race_15:
                    st.info("🏆 **Race 15 (Power of 10 Marathon):** Manual entry required.")
                    final_date = col1.text_input("Marathon Date (YYYY-MM-DD)", p.get('date'), key=f"date_15_{i}")
                    final_loc = col2.text_input("Marathon Location", p.get('race_name'), key=f"loc_15_{i}")
                    final_race_name = "Power of 10 Marathon"
                else:
                    cal_entry = champ_calendar[race_idx]
                    final_date = cal_entry['date']
                    final_loc = cal_entry['name']
                    final_race_name = cal_entry['name']
                    st.success(f"Linked to {final_race_name} on {final_date}")

                win_time = st.text_input(f"Winner's Time for this Category/Gender", "00:00", key=f"win_{i}")
                
                runner_sec = get_seconds(p['time_display'])
                winner_sec = get_seconds(win_time)
                calc_pts = round((winner_sec / runner_sec) * 100, 2) if winner_sec > 0 else 0.0
                st.info(f"Calculated Points: **{calc_pts}**")
                
                pts = st.number_input("Final Points to Award", 0.0, 100.0, calc_pts, key=f"pts_{i}")
                pb_dist = st.selectbox("PB Distance Log", ["5k", "10k", "10 Mile", "HM", "Marathon"], 
                                      index=4 if is_race_15 else 0, key=f"pb_dist_{i}")

                if st.button("✅ Approve Result", key=f"app_{i}"):
                    m_info = member_db.get(p['name'], {})
                    cat = get_category(m_info.get('dob','2000-01-01'), final_date, settings['age_mode'])
                    
                    champ_entry = {
                        "name": p['name'],
                        "race_name": final_race_name,
                        "date": final_date,
                        "points": pts,
                        "category": cat,
                        "gender": m_info.get('gender', 'U')
                    }
                    r.rpush("champ_results_final", json.dumps(champ_entry))
                    
                    pb_entry = {
                        "name": p['name'], 
                        "distance": pb_dist, 
                        "location": final_loc, 
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
                    st.rerun()

with tabs[1]: # --- CALENDAR SETUP ---
    st.subheader("15-Race Calendar Setup")
    # Force 15th race name to the specific "Power of 10" text if not set
    if len(champ_calendar) < 15:
        champ_calendar = [{"name": "TBC", "date": "2026-01-01", "distance": "5k", "terrain": "Road"} for _ in range(15)]
    
    with st.form("cal_form"):
        updated_cal = []
        for i in range(15):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            default_name = "Any Marathon (Power of 10)" if i == 14 else champ_calendar[i]['name']
            n = c1.text_input(f"Race {i+1}", default_name, key=f"n_{i}")
            
            try: d_val = datetime.strptime(champ_calendar[i]['date'], '%Y-%m-%d')
            except: d_val = datetime(2026, 1, 1)
            
            # For Race 15, date is less critical here as it's manually entered per runner
            d = c2.date_input("Date", d_val, key=f"d_{i}")
            di = c3.selectbox("Dist", ["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"], 
                              index=5 if champ_calendar[i].get('distance') == "TBC" else 0, key=f"di_{i}")
            te = c4.selectbox("Terrain", ["Road", "Trail", "Fell", "XC"], key=f"te_{i}")
            updated_cal.append({"name": n, "date": str(d), "distance": di, "terrain": te})
            
        if st.form_submit_button("Save Calendar"):
            r.set("champ_calendar_2026", json.dumps(updated_cal))
            rebuild_leaderboard_cache(r)
            st.success("Calendar Saved!")

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
                t = data[idx]
                with st.form("c_edit_form"):
                    e_name = st.text_input("Name", t.get('name'))
                    e_pts = st.number_input("Points", 0.0, 100.0, float(t.get('points', 0)))
                    e_cat = st.text_input("Category", t.get('category'))
                    if st.form_submit_button("Update Entry"):
                        data[idx].update({"name": e_name, "points": e_pts, "category": e_cat})
                        r.lset("champ_results_final", int(idx), json.dumps(data[idx]))
                        rebuild_leaderboard_cache(r)
                        st.rerun()
        with d_col:
            with st.expander("🗑️ Delete Result"):
                d_idx = st.number_input("Index to Delete", 0, len(df)-1, 0, key="c_del_idx")
                if st.button("Confirm Delete"):
                    r.lset("champ_results_final", int(d_idx), "WIPE")
                    r.lrem("champ_results_final", 1, "WIPE")
                    rebuild_leaderboard_cache(r)
                    st.rerun()

with tabs[3]: # --- LEADERBOARD ---
    cache = r.get("cached_champ_standings")
    if cache: st.table(pd.read_json(cache))
    else: st.info("No standings found.")
