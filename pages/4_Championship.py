import streamlit as st
import json
from helpers import get_redis, time_to_seconds

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("🏅 Championship Admin")
tab_cal, tab_app = st.tabs(["Calendar Editor", "Point Approvals"])

with tab_cal:
    cal_raw = r.get("champ_calendar_2026")
    cal = json.loads(cal_raw) if cal_raw else []
    new_cal = []
    for i in range(15):
        ra = cal[i] if i < len(cal) else {"date": "TBC", "name": "TBC", "distance": "TBC", "terrain": "Road"}
        with st.expander(f"Race {i+1}: {ra['name']}"):
            d, n = st.text_input("Date", ra['date'], key=f"d_{i}"), st.text_input("Name", ra['name'], key=f"n_{i}")
            new_cal.append({"date": d, "name": n, "distance": "TBC", "terrain": "Road"})
    if st.button("Save Calendar"): r.set("champ_calendar_2026", json.dumps(new_cal)); st.success("Saved")

with tab_app:
    c_pend = r.lrange("champ_pending", 0, -1)
    for i, cj in enumerate(c_pend):
        cp = json.loads(cj)
        st.write(f"**{cp['name']}** - {cp['race_name']} ({cp['time_display']})")
        wt = st.text_input("Winner Time", key=f"wt_{i}")
        if st.button("Approve & Calc", key=f"c_ap_{i}"):
            pts = round((time_to_seconds(wt) / time_to_seconds(cp['time_display'])) * 100, 1)
            r.rpush("champ_results_final", json.dumps({"name": cp['name'], "race": cp['race_name'], "points": pts, "date": cp['date']}))
            r.lrem("champ_pending", 1, cj); st.rerun()
