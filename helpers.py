import redis
import streamlit as st
import json
import pandas as pd
import os
from datetime import datetime

@st.cache_resource
def get_redis():
    try:
        url = st.secrets.get("REDIS_URL") or os.environ.get("REDIS_URL")
    except:
        url = os.environ.get("REDIS_URL")
    if not url:
        st.error("REDIS_URL not found.")
        st.stop()
    return redis.from_url(url, decode_responses=True)

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
    # --- 1. PB LEADERBOARD CACHE ---
    raw_res = r.lrange("race_results", 0, -1)
    if raw_res:
        # Exclude any entries that might be TBC or incomplete
        res_list = [json.loads(x) for x in raw_res]
        df = pd.DataFrame(res_list)
        if not df.empty and 'time_seconds' in df.columns:
            df = df.sort_values("time_seconds", ascending=True)
            r.set("cached_pb_leaderboard", df.to_json(orient="records"))

    # --- 2. CHAMPIONSHIP CACHE ---
    final_raw = r.lrange("champ_results_final", 0, -1)
    if final_raw:
        c_list = [json.loads(x) for x in final_raw]
        c_df = pd.DataFrame(c_list)
        # CRITICAL: Exclude TBC races from calculations
        if not c_df.empty:
            if 'race_name' in c_df.columns:
                c_df = c_df[c_df['race_name'].str.upper() != "TBC"]
            
            if not c_df.empty:
                c_df = c_df.sort_values(['name', 'points'], ascending=[True, False])
                c_df['rank'] = c_df.groupby('name').cumcount() + 1
                league = c_df[c_df['rank'] <= 6].groupby('name')['points'].sum().reset_index()
                league.columns = ['Runner', 'Total Points']
                league = league.sort_values('Total Points', ascending=False).reset_index(drop=True)
                r.set("cached_champ_standings", league.to_json(orient="records"))
