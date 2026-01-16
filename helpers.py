import redis
import os
import json
from datetime import datetime

def get_redis():
    """Establish connection to Redis using the environment variable."""
    # Use the internal URL provided by Render, or fallback for local testing
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(redis_url, decode_responses=True)

def time_to_seconds(time_str):
    """Converts HH:MM:SS or MM:SS to total seconds."""
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 3:  # HH:MM:SS
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:  # MM:SS
            return parts[0] * 60 + parts[1]
        return 0
    except (ValueError, AttributeError):
        return 0

def format_time_string(time_str):
    """Ensures time is stored in a clean HH:MM:SS format."""
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 3:
            return f"{parts[0]:02}:{parts[1]:02}:{parts[2]:02}"
        elif len(parts) == 2:
            # Assumes MM:SS, so add 00 for hours
            return f"00:{parts[0]:02}:{parts[1]:02}"
        return time_str
    except (ValueError, AttributeError):
        return time_str

def get_category(dob_str, race_date_str, mode="10Y"):
    """
    Calculates age category based on DOB and Race Date.
    mode="10Y" -> Senior, V40, V50, V60, V70+
    mode="5Y"  -> Senior, V35, V40, V45, V50, V55, V60, V65, V70, V75+
    """
    try:
        # Standardize dates
        if isinstance(dob_str, str):
            dob = datetime.strptime(dob_str, '%Y-%m-%d')
        else:
            dob = dob_str
            
        if isinstance(race_date_str, str):
            race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        else:
            race_date = race_date_str

        # Age on race day
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        
        # --- 5-Year Banding Logic ---
        if mode == "5Y":
            if age < 35: 
                return "Senior"
            if age >= 75: 
                return "V75+"
            # Floors to nearest 5 (e.g., 44 -> 40, 46 -> 45)
            base = (age // 5) * 5
            return f"V{base}"
        
        # --- 10-Year Banding Logic (Default) ---
        else:
            if age < 40: 
                return "Senior"
            if age >= 70: 
                return "V70+"
            # Floors to nearest 10 (e.g., 49 -> 40)
            base = (age // 10) * 10
            return f"V{base}"
            
    except Exception:
        return "Unknown"

def get_club_settings():
    """Helper to fetch common club settings from Redis."""
    r = get_redis()
    return {
        "logo_url": r.get("club_logo_url") or "https://cdn-icons-png.flaticon.com/512/55/55281.png",
        "age_mode": r.get("age_mode") or "10Y",
        "show_champ": r.get("show_champ_tab") == "True"
    }
