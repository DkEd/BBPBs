import streamlit as st
import redis
import json
import pandas as pd
from datetime import datetime

def get_redis():
    """Establish connection to Redis database."""
    return redis.from_url(st.secrets["redis_url"], decode_responses=True)

def get_club_settings():
    """Retrieve club-wide settings; returns defaults if not set."""
    r = get_redis()
    s = r.get("club_settings")
    if s:
        return json.loads(s)
    return {
        "club_name": "Bramley Breezers",
        "age_mode": "Age on Day",
        "logo_url": ""
    }

def get_category(dob_str, race_date_str, age_mode):
    """Calculate age category (e.g., SEN, V40) based on club settings."""
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        # If 'Age on Day' is selected, use race date; else use Jan 1st of race year
        if age_mode == "Age on Day":
            ref_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        else:
            ref_date = datetime(datetime.strptime(race_date_str, '%Y-%m-%d').year, 1, 1)
        
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
    
    # 2. CHAMPIONSHIP STANDINGS CACHE (Best 6)
    champ_raw = r.lrange("champ_results_final", 0, -1)
    if champ_raw:
        c_df = pd.DataFrame([json.loads(x) for x in champ_raw])
        
        # Sort by points descending so we can pick the top 6 per person
        c_df = c_df.sort_values(['name', 'points'], ascending=[True, False])
        
        # Group by name and take top 6 results
        top_6 = c_df.groupby('name').head(6)
        
        # Sum points and count races
        standings = top_6.groupby('name').agg({
            'points': 'sum',
            'race_name': 'count'
        }).reset_index()
        
        standings.columns = ['Name', 'Total Points', 'Races Run']
        
        # Merge back category and gender for display (taking latest info)
        latest_info = c_df.drop_duplicates('name', keep='first')[['name', 'category', 'gender']]
        standings = standings.merge(latest_info, left_on='Name', right_on='name').drop('name', axis=1)
        
        # Final formatting and sort by total points
        standings = standings[['Name', 'category', 'gender', 'Races Run', 'Total Points']]
        standings = standings.sort_values('Total Points', ascending=False)
        
        r.set("cached_champ_standings", standings.to_json())
    
    return True
