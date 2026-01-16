import streamlit as st
import redis
import json
import os
from datetime import datetime

def get_redis():
    return redis.from_url(os.environ.get("REDIS_URL"), decode_responses=True)

def get_club_settings():
    r = get_redis()
    return {
        "age_mode": r.get("age_mode") or "10Y",
        "logo_url": r.get("logo_url") or "",
        "admin_password": r.get("admin_password") or "admin123",
        "show_champ_tab": r.get("show_champ_tab") or "False"
    }

def format_time_string(t_str):
    try:
        parts = str(t_str).strip().split(':')
        if len(parts) == 2: 
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3: 
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return str(t_str)
    except: 
        return str(t_str)

def time_to_seconds(t_str):
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: 
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: 
            return parts[0] * 60 + parts[1]
        return 999999
    except: 
        return 999999

def get_category(dob_str, race_date_str, mode="10Y"):
    try:
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        race_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        step = 5 if mode == "5Y" else 10
        if age < (35 if mode == "5Y" else 40): 
            return "Senior"
        return f"V{(age // step) * step}"
    except: 
        return "Unknown"
