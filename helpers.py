import redis
import streamlit as st
import json
import pandas as pd
from datetime import datetime

@st.cache_resource
def get_redis():
    return redis.from_url(st.secrets["REDIS_URL"], decode_responses=True)

def get_club_settings():
    r = get_redis()
    s = r.get("club_settings")
    return json.loads(s) if s else {"age_mode": "5 Year", "logo_url": "", "admin_password": "admin"}

def get_category(dob_str, race_date_str, mode):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        rd = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = rd.year - dob.year - ((rd.month, rd.day) < (dob.month, dob.day))
        step = 5 if mode == "5 Year" else 10
        if age < 35: return "Senior"
        cat_base = (age // step) * step
        return f"V{cat_base}"
    except: return "Senior"

def rebuild_leaderboard_cache(r):
    settings = get_club_settings()
    
    # --- 1. PB LEADERBOARD CACHE ---
    raw_res = r.lrange("race_results", 0, -1)
    if raw_res:
        df = pd.DataFrame([json.loads(x) for x in raw_res])
        # Logic to find fastest per person/distance/category
        df = df.sort_values("time_seconds", ascending=True)
        # We store the simplified PB set for the public BBPB.py to read
        r.set("cached_pb_leaderboard", df.to_json(orient="records"))
    
    # --- 2. CHAMPIONSHIP CACHE ---
    final_raw = r.lrange("champ_results_final", 0, -1)
    if final_raw:
        c_df = pd.DataFrame([json.loads(x) for x in final_raw])
        c_df = c_df.sort_values(['name', 'points'], ascending=[True, False])
        c_df['rank'] = c_df.groupby('name').cumcount() + 1
        league = c_df[c_df['rank'] <= 6].groupby('name')['points'].sum().reset_index()
        league.columns = ['Runner', 'Total Points']
        league = league.sort_values('Total Points', ascending=False).reset_index(drop=True)
        r.set("cached_champ_standings", league.to_json(orient="records"))
