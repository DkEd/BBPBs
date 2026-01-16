import streamlit as st
import json
import pandas as pd
from helpers import get_redis, time_to_seconds, get_category

st.set_page_config(page_title="Championship Admin", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("🏅 Championship Management")
tabs = st.tabs(["🗓️ Calendar", "⏱️ Set Winners", "📥 Approve Points", "📊 Final Log"])

# Data Loading
cal_raw = r.get("champ_calendar_2026")
calendar = json.loads(cal_raw) if cal_raw else []
champ_races = [rc['name'] for rc in calendar if rc['name'] != "TBC"]
categories = ["Senior", "V35", "V40", "V45", "V50", "V55", "V60", "V65", "V70", "V75+"]

with tabs[0]:
    new_cal = []
    for i in range(15):
        ra = calendar[i] if i < len(calendar) else {"date": "2026-01-01", "name": "TBC"}
        c1, c2 = st.columns(2)
        d = c1.text_input(f"Date R{i+1}", ra['date'], key=f"d_{i}")
        n = c2.text_input(f"Name R{i+1}", ra['name'], key=f"n_{i}")
        new_cal.append({"date": d, "name": n})
    if st.button("Save Calendar"):
        r.set("champ_calendar_2026", json.dumps(new_cal))
        st.success("Saved.")

with tabs[1]:
    sel_race = st.selectbox("Race", [""] + champ_races)
    if sel_race:
        grid = json.loads(r.get("champ_winners_grid") or "{}")
        if sel_race not in grid: grid[sel_race] = {}
        m_col, f_col = st.columns(2)
        for gen in ["Male", "Female"]:
            with m_col if gen == "Male" else f_col:
                st.write(f"**{gen}**")
                for cat in categories:
                    grid[sel_race][f"{gen}_{cat}"] = st.text_input(f"{cat}", grid[sel_race].get(f"{gen}_{cat}", ""), key=f"{sel_race}_{gen}_{cat}")
        if st.button("Save Winners"):
            r.set("champ_winners_grid", json.dumps(grid))
            st.success("Saved.")

with tabs[2]:
    pending = r.lrange("champ_pending", 0, -1)
    mems = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
    grid = json.loads(r.get("champ_winners_grid") or "{}")
    
    for i, pj in enumerate(pending):
        p = json.loads(pj)
        m = mems.get(p['name'])
        if m:
            cat = get_category(m['dob'], p['date'], "5Y")
            win_time = grid.get(p['race_name'], {}).get(f"{m['gender']}_{cat}", "")
            with st.container(border=True):
                st.write(f"**{p['name']}** ({m['gender']} {cat}) - {p['race_name']}")
                st.write(f"Time: {p['time_display']} | Cat Winner: {win_time}")
                if win_time:
                    pts = round((time_to_seconds(win_time) / time_to_seconds(p['time_display'])) * 100, 2)
                    st.write(f"Points: **{pts}**")
                    if st.button("Approve", key=f"cp_a_{i}"):
                        r.rpush("champ_results_final", json.dumps({"name": p['name'], "race": p['race_name'], "points": pts, "date": p['date']}))
                        r.lrem("champ_pending", 1, pj); st.rerun()
                st.button("Reject", key=f"cp_r_{i}", on_click=lambda: r.lrem("champ_pending", 1, pj))

with tabs[3]:
    final = r.lrange("champ_results_final", 0, -1)
    if final:
        st.dataframe(pd.DataFrame([json.loads(f) for f in final]), use_container_width=True)
