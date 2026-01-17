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

with tabs[0]: # Pending
    pending = r.lrange("champ_pending", 0, -1)
    if not pending:
        st.info("No pending results.")
    else:
        for i, p_raw in enumerate(pending):
            p = json.loads(p_raw)
            with st.expander(f"Review: {p['name']} - {p['race_name']}"):
                col1, col2 = st.columns(2)
                pts = col1.number_input(f"Points", 0.0, 100.0, 0.0, key=f"pts_{i}")
                dist = col2.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"], key=f"dist_{i}")
                
                if st.button("✅ Approve", key=f"app_{i}"):
                    m_info = member_db.get(p['name'], {})
                    cat = get_category(m_info.get('dob','2000-01-01'), p['date'], settings['age_mode'])
                    entry = {**p, "points": pts, "category": cat, "gender": m_info.get('gender', 'U')}
                    r.rpush("champ_results_final", json.dumps(entry))
                    
                    pb_entry = {"name": p['name'], "distance": dist, "location": p['race_name'], "race_date": p['date'], "time_display": p['time_display'], "time_seconds": get_seconds(p['time_display']), "gender": m_info.get('gender', 'U'), "dob": m_info.get('dob', '2000-01-01')}
                    r.rpush("race_results", json.dumps(pb_entry))
                    
                    rebuild_leaderboard_cache(r)
                    r.lset("champ_pending", i, "WIPE")
                    r.lrem("champ_pending", 1, "WIPE")
                    st.rerun()

with tabs[1]: # Calendar Setup
    st.subheader("15-Race Calendar")
    cal_raw = r.get("champ_calendar_2026")
    current_cal = json.loads(cal_raw) if cal_raw else [{"name": "TBC", "date": "2026-01-01", "distance": "5k", "terrain": "Road"} for _ in range(15)]
    
    with st.form("cal_form"):
        updated_cal = []
        for i in range(15):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            n = c1.text_input(f"Race {i+1}", current_cal[i]['name'], key=f"n_{i}")
            try:
                curr_date = datetime.strptime(current_cal[i]['date'], '%Y-%m-%d')
            except:
                curr_date = datetime(2026, 1, 1)
            d = c2.date_input("Date", value=curr_date, key=f"d_{i}")
            dist = c3.selectbox("Dist", ["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"], index=0, key=f"di_{i}")
            terr = c4.selectbox("Terrain", ["Road", "Trail", "Fell", "XC"], index=0, key=f"te_{i}")
            updated_cal.append({"name": n, "date": str(d), "distance": dist, "terrain": terr})
        
        if st.form_submit_button("Save Calendar"):
            r.set("champ_calendar_2026", json.dumps(updated_cal))
            rebuild_leaderboard_cache(r) # Refresh in case TBC was changed to a real name
            st.success("Calendar Saved!")

with tabs[2]: # Log
    final_res = r.lrange("champ_results_final", 0, -1)
    if final_res:
        df = pd.DataFrame([json.loads(x) for x in final_res])
        st.dataframe(df)
        if st.button("🗑️ Clear All Results"):
            if st.checkbox("Confirm Deletion"):
                r.delete("champ_results_final")
                rebuild_leaderboard_cache(r)
                st.rerun()

with tabs[3]: # Leaderboard
    cache = r.get("cached_champ_standings")
    if cache:
        st.table(pd.read_json(cache))
    else:
        st.info("No standings found. Refresh cache on Home.")
