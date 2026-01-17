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

# --- HELPERS ---
def get_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
    except: return 0
    return 0

# Load Members for lookup logic
raw_mems = r.lrange("members", 0, -1)
member_db = {json.loads(m)['name']: json.loads(m) for m in raw_mems}

# --- TAB 1: PENDING APPROVALS ---
with tabs[0]:
    st.subheader("Results Awaiting Review")
    pending = r.lrange("champ_pending", 0, -1)
    
    if not pending:
        st.info("No pending championship results.")
    else:
        for i, p_raw in enumerate(pending):
            p = json.loads(p_raw)
            with st.expander(f"Review: {p['name']} - {p['race_name']}"):
                col1, col2, col3 = st.columns(3)
                col1.write(f"**Time:** {p['time_display']}")
                col2.write(f"**Date:** {p['date']}")
                
                pts = st.number_input(f"Points for {p['name']}", 0.0, 100.0, 0.0, key=f"pts_{i}")
                dist = st.selectbox("Confirm Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"], key=f"dist_{i}")
                
                c_app, c_rej = st.columns(2)
                
                if c_app.button("✅ Approve & Add to PB Log", key=f"app_{i}"):
                    m_info = member_db.get(p['name'], {})
                    cat = get_category(m_info.get('dob','2000-01-01'), p['date'], settings['age_mode'])
                    
                    champ_entry = {
                        **p, 
                        "points": pts, 
                        "category": cat,
                        "gender": m_info.get('gender', 'Unknown')
                    }
                    r.rpush("champ_results_final", json.dumps(champ_entry))
                    
                    pb_entry = {
                        "name": p['name'],
                        "distance": dist,
                        "location": p['race_name'],
                        "race_date": p['date'],
                        "time_display": p['time_display'],
                        "time_seconds": get_seconds(p['time_display']),
                        "gender": m_info.get('gender', 'Unknown'),
                        "dob": m_info.get('dob', '2000-01-01')
                    }
                    r.rpush("race_results", json.dumps(pb_entry))
                    
                    # TRIGGER CACHE REFRESH
                    rebuild_leaderboard_cache(r)
                    
                    r.lset("champ_pending", i, "WIPE")
                    r.lrem("champ_pending", 1, "WIPE")
                    st.success(f"Approved! Added to Championship, PBs, and Cache.")
                    st.rerun()

                if c_rej.button("❌ Reject", key=f"rej_{i}"):
                    r.lset("champ_pending", i, "WIPE")
                    r.lrem("champ_pending", 1, "WIPE")
                    st.rerun()

# --- TAB 2: CALENDAR SETUP ---
with tabs[1]:
    st.subheader("15-Race Calendar Setup")
    cal_raw = r.get("champ_calendar_2026")
    current_cal = json.loads(cal_raw) if cal_raw else [{"name": "TBC", "date": "2026-01-01", "distance": "5k", "terrain": "Road"} for _ in range(15)]
    
    with st.form("cal_form"):
        updated_cal = []
        track_distances = ["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"]
        
        for i in range(15):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            n = c1.text_input(f"Race {i+1}", current_cal[i]['name'], key=f"n_{i}")
            
            try:
                curr_date = datetime.strptime(current_cal[i]['date'], '%Y-%m-%d')
            except:
                curr_date = datetime(2026, 1, 1)
            d = c2.date_input("Date", value=curr_date, key=f"d_{i}")
            
            curr_dist = current_cal[i].get('distance', '5k')
            dist_idx = track_distances.index(curr_dist) if curr_dist in track_distances else 0
            dist = c3.selectbox("Dist", track_distances, index=dist_idx, key=f"dist_cal_{i}")
            
            curr_terr = current_cal[i].get('terrain', 'Road')
            terr_opts = ["Road", "Trail", "Fell", "XC"]
            terr_idx = terr_opts.index(curr_terr) if curr_terr in terr_opts else 0
            terr = c4.selectbox("Terrain", terr_opts, index=terr_idx, key=f"terr_{i}")
            
            updated_cal.append({"name": n, "date": str(d), "distance": dist, "terrain": terr})
        
        if st.form_submit_button("Save 2026 Calendar"):
            r.set("champ_calendar_2026", json.dumps(updated_cal))
            # REBUILD CACHE in case a TBC was filled in
            rebuild_leaderboard_cache(r)
            st.success("Calendar Saved and Cache Updated!")
            st.rerun()

# --- TAB 3: CHAMPIONSHIP LOG ---
with tabs[2]:
    st.subheader("Approved Results")
    final_res = r.lrange("champ_results_final", 0, -1)
    if final_res:
        log_df = pd.DataFrame([json.loads(x) for x in final_res])
        st.dataframe(log_df, use_container_width=True)
        
        if st.button("🗑️ Clear All Champ Results"):
            if st.checkbox("Confirm full deletion?"):
                r.delete("champ_results_final")
                rebuild_leaderboard_cache(r)
                st.rerun()
    else:
        st.info("No approved results yet.")

# --- TAB 4: LEADERBOARD (Admin View) ---
with tabs[3]:
    st.subheader("Current Standings (Best 6)")
    # Use cache for the leaderboard tab too for consistency and speed
    cache = r.get("cached_champ_standings")
    if cache:
        league = pd.read_json(cache)
        st.table(league)
    else:
        st.info("No cached standings. Approve a result or refresh cache in System.")
