import streamlit as st
import redis
import json
import pandas as pd
import os
from datetime import datetime

def get_redis():
    """Establish connection to Redis using the UPPERCASE environment variable."""
    redis_url = os.environ.get("REDIS_URL")
    return redis.from_url(redis_url, decode_responses=True)

def get_club_settings():
    """Retrieve club-wide settings."""
    r = get_redis()
    s = r.get("club_settings")
    if s:
        return json.loads(s)
    return {
        "club_name": "Bramley Breezers",
        "logo_url": ""
    }

def get_category(dob_str, race_date_str, age_mode="Age on Day"):
    """
    Calculate age category. 
    Accepts optional 'age_mode' to prevent Admin site TypeErrors, 
    but logic is strictly 'Age on Day' as requested.
    """
    try:
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        ref_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        age = ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
        
        if age < 40: return "SEN"
        if age < 45: return "V40"
        if age < 50: return "V45"
        if age < 55: return "V50"
        if age < 60: return "V55"
        if age < 65: return "V60"
        if age < 70: return "V65"
        return "V70+"
    except:
        return "SEN"

def rebuild_leaderboard_cache(r):
    """Calculates and caches the PB Leaderboard and Championship Standings."""
    # 1. PB LEADERBOARD CACHE
    raw_res = r.lrange("race_results", 0, -1)
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        r.set("cached_pb_leaderboard", df.to_json())
    
    # 2. CHAMPIONSHIP STANDINGS CACHE
    champ_raw = r.lrange("champ_results_final", 0, -1)
    if champ_raw:
        c_df = pd.DataFrame([json.loads(x) for x in champ_raw])
        c_df = c_df.sort_values(['name', 'points'], ascending=[True, False])
        
        # Take top 6 results
        top_6 = c_df.groupby('name').head(6)
        
        standings = top_6.groupby('name').agg({
            'points': 'sum',
            'race_name': 'count'
        }).reset_index()
        
        standings.columns = ['Name', 'Total Points', 'Races Run']
        
        # Merge back category and gender (latest)
        latest_info = c_df.drop_duplicates('name', keep='first')[['name', 'category', 'gender']]
        standings = standings.merge(latest_info, left_on='Name', right_on='name').drop('name', axis=1)
        
        standings = standings[['Name', 'category', 'gender', 'Races Run', 'Total Points']]
        standings = standings.sort_values('Total Points', ascending=False)
        
        r.set("cached_champ_standings", standings.to_json())
    
    return True
