import streamlit as st
import json
import pandas as pd
from datetime import datetime
from helpers import get_redis, get_club_settings, get_category, rebuild_leaderboard_cache

st.set_page_config(page_title="Champ Management", layout="wide")
r = get_redis()
settings = get_club_settings()

st.header("🏅 Championship Management")
tabs = st.tabs(["📥 Pending", "🗓️ Calendar", "📊 Log", "🏆 Leaderboard"])

def get_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        return parts[0]*3600 + parts[1]*60 + parts[2] if len(parts)==3 else parts[0]*60 + parts[1]
    except: return 0

raw_mems = r.lrange("members", 0, -1)
member_db = {json.loads(m)['name']: json.loads(m) for m in raw_mems}

with tabs[0]: # Pending
    pending = r.lrange("champ_pending", 0, -1)
    for i, p_raw in enumerate(pending):
        p = json.loads(p_raw)
        with st.expander(f"{p['name']} - {p['race_name']}"):
            pts = st.number_input("Points", 0.0, 100.0, key=f"pts_{i}")
            dist = st.selectbox("Dist", ["5k", "10k", "10 Mile", "HM", "Marathon"], key=f"d_{i}")
            if st.button("Approve", key=f"a_{i}"):
                m = member_db.get(p['name'], {})
                cat = get_category(m.get('dob','2000-01-01'), p['date'], settings['age_mode'])
                entry = {**p, "points": pts, "category": cat, "gender": m.get('gender','M')}
                r.rpush("champ_results_final", json.dumps(entry))
                # Auto-sync to PB list
                pb = {"name": p['name'], "distance": dist, "location": p['race_name'], "race_date": p['date'], "time_display": p['time_display'], "time_seconds": get_seconds(p['time_display']), "gender": m.get('gender','M'), "dob": m.get('dob','2000-01-01')}
                r.rpush("race_results", json.dumps(pb))
                rebuild_leaderboard_cache(r) # TRIGGER
                r.lset("champ_pending", i, "WIPE")
                r.lrem("champ_pending", 1, "WIPE")
                st.rerun()

with tabs[1]: # Calendar
    cal_raw = r.get("champ_calendar_2026")
    curr_cal = json.loads(cal_raw) if cal_raw else [{"name": "TBC", "date": "2026-01-01", "distance": "5k", "terrain": "Road"} for _ in range(15)]
    with st.form("cal"):
        new_cal = []
        for i in range(15):
            c1, c2, c3, c4 = st.columns(4)
            n = c1.text_input(f"R{i+1}", curr_cal[i]['name'])
            d = c2.date_input("Date", value=datetime.strptime(curr_cal[i]['date'], '%Y-%m-%d'), key=f"dt_{i}")
            dist = c3.selectbox("Dist", ["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"], index=0, key=f"ds_{i}")
            terr = c4.selectbox("Terr", ["Road", "Trail", "Fell", "XC"], index=0, key=f"tr_{i}")
            new_cal.append({"name": n, "date": str(d), "distance": dist, "terrain": terr})
        if st.form_submit_button("Save"):
            r.set("champ_calendar_2026", json.dumps(new_cal))
            st.success("Saved")

with tabs[2]: # Log
    final = r.lrange("champ_results_final", 0, -1)
    if final:
        st.dataframe(pd.DataFrame([json.loads(x) for x in final]))
        if st.button("Clear Log"):
            r.delete("champ_results_final")
            rebuild_leaderboard_cache(r)
            st.rerun()

with tabs[3]: # Leaderboard
    cache = r.get("cached_champ_standings")
    if cache: st.table(pd.read_json(cache))
