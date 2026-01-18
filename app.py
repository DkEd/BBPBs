# app.py - COMPLETE OPTIMIZED BBPB ADMIN
# ============================================================
# SECTION 1: IMPORTS & SETUP
# ============================================================
import streamlit as st
import pandas as pd
import numpy as np
import redis
import json
import os
import io
import csv
from datetime import datetime, date, timedelta
from functools import lru_cache
from typing import List, Dict, Any, Optional, Tuple
import time

# Set page config FIRST
st.set_page_config(
    page_title="BBPB Admin",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SECTION 2: OPTIMIZED REDIS MANAGER
# ============================================================
class RedisManager:
    """Singleton Redis connection manager with smart caching"""
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
            cls._instance._last_refresh = {}
        return cls._instance
    
    @property
    def conn(self):
        if self._connection is None:
            try:
                self._connection = redis.from_url(
                    os.environ.get("REDIS_URL", "redis://localhost:6379"),
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_keepalive=True,
                    retry_on_timeout=True,
                    max_connections=5
                )
                # Quick ping test
                self._connection.ping()
            except Exception as e:
                st.error(f"⚠️ Redis connection failed: {str(e)[:100]}")
                return None
        return self._connection
    
    def get_cached(self, key: str, max_age: int = 60) -> Optional[Any]:
        """Get from memory cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).seconds < max_age:
                return data
        return None
    
    def set_cached(self, key: str, data: Any):
        """Store in memory cache"""
        self._cache[key] = (data, datetime.now())
    
    def clear_cache(self, key_prefix: str = None):
        """Clear cache entries"""
        if key_prefix:
            for k in list(self._cache.keys()):
                if k.startswith(key_prefix):
                    del self._cache[k]
        else:
            self._cache.clear()
    
    def pipeline_execute(self, commands: List[Tuple[str, Any]]) -> List[Any]:
        """Execute multiple Redis commands in pipeline"""
        if not self.conn:
            return []
        pipe = self.conn.pipeline()
        for cmd, *args in commands:
            getattr(pipe, cmd)(*args)
        return pipe.execute()

# Global instance
redis_mgr = RedisManager()

# ============================================================
# SECTION 3: AUTHENTICATION
# ============================================================
def require_auth():
    """Check authentication, return True if authenticated"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        # Check session timeout (8 hours)
        if 'login_time' in st.session_state:
            session_age = datetime.now() - st.session_state.login_time
            if session_age > timedelta(hours=8):
                st.session_state.authenticated = False
                return False
        return True
    return False

def render_login():
    """Render login form in sidebar"""
    with st.sidebar:
        st.title("🔐 BBPB Admin")
        
        r = redis_mgr.conn
        if r:
            stored_pwd = r.get("admin_password") or "Breezersrock!"
        else:
            stored_pwd = "Breezersrock!"
        
        pwd = st.text_input("Admin Password", type="password", key="login_input")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                if pwd == stored_pwd:
                    st.session_state.authenticated = True
                    st.session_state.login_time = datetime.now()
                    st.session_state.current_tab = "leaderboard"
                    st.rerun()
                else:
                    st.error("Incorrect password")
        with col2:
            if st.button("Clear", use_container_width=True):
                st.rerun()
        
        st.divider()
        return False
    
    return False

# ============================================================
# SECTION 4: DATA LOADERS WITH CACHING
# ============================================================
@st.cache_data(ttl=300)
def load_members(_redis_mgr: RedisManager) -> List[Dict]:
    """Load all members from Redis"""
    r = _redis_mgr.conn
    if not r:
        return []
    
    cached = _redis_mgr.get_cached("members_data", max_age=120)
    if cached:
        return cached
    
    raw = r.lrange("members", 0, -1)
    members = [json.loads(m) for m in raw]
    _redis_mgr.set_cached("members_data", members)
    return members

@st.cache_data(ttl=60)
def load_race_results(_redis_mgr: RedisManager) -> List[Dict]:
    """Load all race results from Redis"""
    r = _redis_mgr.conn
    if not r:
        return []
    
    cached = _redis_mgr.get_cached("race_results_data", max_age=30)
    if cached:
        return cached
    
    raw = r.lrange("race_results", 0, -1)
    results = [json.loads(r) for r in raw]
    _redis_mgr.set_cached("race_results_data", results)
    return results

def get_member_dict() -> Dict[str, Dict]:
    """Get members as lookup dictionary"""
    members = load_members(redis_mgr)
    return {m['name']: m for m in members}

# ============================================================
# SECTION 5: UTILITY FUNCTIONS
# ============================================================
def format_time_string(t_str: str) -> str:
    """Format time as HH:MM:SS"""
    try:
        t_str = str(t_str).strip()
        if not t_str:
            return "00:00:00"
        
        parts = t_str.split(':')
        if len(parts) == 2:  # MM:SS
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3:  # HH:MM:SS
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        else:
            return "00:00:00"
    except:
        return "00:00:00"

def time_to_seconds(t_str: str) -> int:
    """Convert time string to total seconds"""
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3:  # HH:MM:SS
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:  # MM:SS
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:  # SS only
            return parts[0]
        else:
            return 999999
    except:
        return 999999

def seconds_to_time(seconds: int) -> str:
    """Convert seconds to HH:MM:SS string"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def get_category(dob_str: str, race_date_str: str, age_mode: str = None) -> str:
    """Calculate age category (from app.py logic)"""
    try:
        # Get age mode from Redis if not provided
        if age_mode is None:
            r = redis_mgr.conn
            if r:
                stored = r.get("age_mode") or "5 Year"
                age_mode = "5Y" if "5" in stored else "10Y"
            else:
                age_mode = "10Y"
        
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        race_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        
        # Calculate age at race
        age = race_date.year - dob.year
        if (race_date.month, race_date.day) < (dob.month, dob.day):
            age -= 1
        
        # Apply category logic from app.py
        if age_mode == "5Y":
            threshold = 35
            step = 5
        else:  # "10Y"
            threshold = 40
            step = 10
        
        if age < threshold:
            return "Senior"
        
        base_age = (age // step) * step
        return f"V{base_age}"
        
    except Exception as e:
        return "Unknown"

def rebuild_leaderboard_cache():
    """Rebuild and cache the PB leaderboard"""
    r = redis_mgr.conn
    if not r:
        return False
    
    try:
        # Load raw data
        raw_results = r.lrange("race_results", 0, -1)
        if not raw_results:
            r.delete("cached_pb_leaderboard")
            return True
        
        # Parse results
        results = [json.loads(res) for res in raw_results]
        df = pd.DataFrame(results)
        
        # Convert date
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        
        # Cache the processed DataFrame
        r.set("cached_pb_leaderboard", df.to_json())
        
        # Clear memory cache
        redis_mgr.clear_cache("members_data")
        redis_mgr.clear_cache("race_results_data")
        st.cache_data.clear()
        
        return True
    except Exception as e:
        st.error(f"Cache rebuild failed: {e}")
        return False

# ============================================================
# SECTION 6: SIDEBAR & NAVIGATION
# ============================================================
def render_sidebar():
    """Render the application sidebar"""
    with st.sidebar:
        # Logo
        r = redis_mgr.conn
        logo_url = None
        if r:
            logo_url = r.get("club_logo_url") or r.get("logo_url")
        
        if logo_url and logo_url.startswith("http"):
            st.image(logo_url, width=180)
        else:
            st.title("🏃 BBPB Admin")
        
        st.divider()
        
        # Authentication check
        if not require_auth():
            render_login()
            st.stop()  # Stop here if not authenticated
        
        # User is authenticated from here
        st.success("✅ Authenticated")
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            st.session_state.authenticated = False
            redis_mgr.clear_cache()
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
        # Navigation
        st.subheader("📋 Navigation")
        
        tabs = [
            ("🏆 Leaderboard", "leaderboard"),
            ("👥 Members", "members"),
            ("📥 PB Submissions", "submissions"),
            ("📋 Race Log", "racelog"),
            ("🎖️ Championship", "championship"),
            ("⚙️ System", "system")
        ]
        
        current_tab = st.session_state.get("current_tab", "leaderboard")
        
        for tab_name, tab_key in tabs:
            if st.button(
                tab_name,
                use_container_width=True,
                type="primary" if current_tab == tab_key else "secondary",
                key=f"nav_{tab_key}"
            ):
                st.session_state.current_tab = tab_key
                if tab_key == "leaderboard":
                    st.cache_data.clear()
                st.rerun()
        
        st.divider()
        
        # Quick Stats
        st.subheader("📊 Quick Stats")
        
        members = load_members(redis_mgr)
        results = load_race_results(redis_mgr)
        
        active_count = len([m for m in members if m.get('status', 'Active') == 'Active'])
        left_count = len([m for m in members if m.get('status') == 'Left'])
        race_count = len(results)
        
        col1, col2 = st.columns(2)
        col1.metric("Active", active_count)
        col2.metric("Races", race_count)
        
        if left_count > 0:
            st.caption(f"Left: {left_count}")
        
        # Refresh button
        st.divider()
        if st.button("🔄 Refresh All Data", use_container_width=True):
            redis_mgr.clear_cache()
            st.cache_data.clear()
            st.success("Cache cleared!")
            time.sleep(0.5)
            st.rerun()

# ============================================================
# SECTION 7: TAB 1 - LEADERBOARD
# ============================================================
def render_leaderboard_tab():
    """Render the PB leaderboard tab"""
    st.title("🏆 Personal Best Leaderboard")
    
    # Check Redis connection
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    # Try to get cached leaderboard
    cached_json = r.get("cached_pb_leaderboard")
    
    if cached_json:
        # Use cached data (FAST)
        try:
            df = pd.read_json(cached_json)
            cache_status = "✅ Using cached leaderboard"
        except:
            cache_status = "⚠️ Cache corrupted, rebuilding..."
            cached_json = None
    
    if not cached_json:
        # Build from scratch (SLOWER)
        with st.spinner("Building leaderboard from raw data..."):
            results = load_race_results(redis_mgr)
            if not results:
                st.info("No race results found in database.")
                return
            
            df = pd.DataFrame(results)
            df['race_date_dt'] = pd.to_datetime(df['race_date'])
            
            # Cache for next time
            r.set("cached_pb_leaderboard", df.to_json())
            cache_status = "🔄 Built new leaderboard cache"
    
    # Show cache status in sidebar
    st.sidebar.caption(cache_status)
    
    # Get active members for opacity
    members = load_members(redis_mgr)
    active_names = [m['name'] for m in members if m.get('status', 'Active') == 'Active']
    
    # Year filter
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    years = ["All-Time"] + sorted(
        [str(y) for y in df['race_date_dt'].dt.year.unique()],
        reverse=True
    )
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_year = st.selectbox("Select Season:", years, key="year_filter")
    
    # Filter by year
    display_df = df.copy()
    if selected_year != "All-Time":
        display_df = display_df[display_df['race_date_dt'].dt.year == int(selected_year)]
    
    # Add category column
    age_mode_setting = r.get("age_mode") or "5 Year"
    age_mode = "5Y" if "5" in age_mode_setting else "10Y"
    
    display_df['Category'] = display_df.apply(
        lambda x: get_category(x['dob'], x['race_date'], age_mode),
        axis=1
    )
    
    # Show summary
    total_records = len(display_df)
    unique_members = display_df['name'].nunique()
    st.caption(f"Showing {total_records} results for {unique_members} members")
    
    # Display by distance
    distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]
    
    for distance in distances:
        st.markdown(f"### 🏁 {distance}")
        
        col_male, col_female = st.columns(2)
        
        # Male column
        with col_male:
            st.markdown(
                '<div style="background:#003366; color:white; padding:10px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; font-size:1.1em; border:2px solid #003366;">MALE</div>',
                unsafe_allow_html=True
            )
            
            male_data = display_df[
                (display_df['distance'] == distance) & 
                (display_df['gender'] == 'Male')
            ]
            
            if not male_data.empty:
                # Get leaders per category
                leaders = male_data.sort_values('time_seconds').groupby('Category').head(1)
                
                for _, row in leaders.sort_values('Category').iterrows():
                    is_active = row['name'] in active_names
                    opacity = "1.0" if is_active else "0.6"
                    
                    html = f'''
                    <div style="border:2px solid #003366; border-top:none; padding:12px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                        <div>
                            <span style="background:#FFD700; color:#003366; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:0.8em; margin-right:8px;">
                                {row['Category']}
                            </span>
                            <b style="color:#003366; font-size:1.05em;">{row['name']}</b><br>
                            <small style="color:#666; font-size:0.85em;">{row['location']} ({row['race_date']})</small>
                        </div>
                        <div style="font-weight:bold; color:#003366; font-size:1.2em; font-family:monospace;">
                            {row['time_display']}
                        </div>
                    </div>
                    '''
                    st.markdown(html, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="border:2px solid #003366; border-top:none; padding:20px; text-align:center; color:#666; font-style:italic;">No records</div>',
                    unsafe_allow_html=True
                )
        
        # Female column
        with col_female:
            st.markdown(
                '<div style="background:#FFD700; color:#003366; padding:10px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; font-size:1.1em; border:2px solid #003366;">FEMALE</div>',
                unsafe_allow_html=True
            )
            
            female_data = display_df[
                (display_df['distance'] == distance) & 
                (display_df['gender'] == 'Female')
            ]
            
            if not female_data.empty:
                leaders = female_data.sort_values('time_seconds').groupby('Category').head(1)
                
                for _, row in leaders.sort_values('Category').iterrows():
                    is_active = row['name'] in active_names
                    opacity = "1.0" if is_active else "0.6"
                    
                    html = f'''
                    <div style="border:2px solid #003366; border-top:none; padding:12px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                        <div>
                            <span style="background:#003366; color:#FFD700; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:0.8em; margin-right:8px;">
                                {row['Category']}
                            </span>
                            <b style="color:#003366; font-size:1.05em;">{row['name']}</b><br>
                            <small style="color:#666; font-size:0.85em;">{row['location']} ({row['race_date']})</small>
                        </div>
                        <div style="font-weight:bold; color:#003366; font-size:1.2em; font-family:monospace;">
                            {row['time_display']}
                        </div>
                    </div>
                    '''
                    st.markdown(html, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="border:2px solid #003366; border-top:none; padding:20px; text-align:center; color:#666; font-style:italic;">No records</div>',
                    unsafe_allow_html=True
                )
        
        st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# SECTION 8: TAB 2 - MEMBERS MANAGEMENT
# ============================================================
def render_members_tab():
    """Render member management tab"""
    st.title("👥 Member Management")
    
    # Load members
    members = load_members(redis_mgr)
    
    # Search box
    search_term = st.text_input("🔍 Search members by name", "")
    
    # Add new member section
    with st.expander("➕ Add New Member", expanded=False):
        with st.form("add_member_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            new_name = col1.text_input("Full Name*", "")
            new_dob = col2.date_input("Date of Birth*", value=None)
            new_gender = col3.selectbox("Gender*", ["Male", "Female"])
            
            if st.form_submit_button("Add Member", type="primary"):
                if not new_name or not new_dob:
                    st.error("Name and Date of Birth are required")
                else:
                    r = redis_mgr.conn
                    if r:
                        member_data = {
                            "name": new_name.strip(),
                            "dob": str(new_dob),
                            "gender": new_gender
                            # Status not stored - all are Active unless marked Left
                        }
                        r.rpush("members", json.dumps(member_data))
                        
                        # Clear caches
                        redis_mgr.clear_cache("members_data")
                        st.cache_data.clear()
                        
                        st.success(f"Added member: {new_name}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Redis connection failed")
    
    st.divider()
    
    # Display and edit members
    st.subheader(f"Members ({len(members)} total)")
    
    if not members:
        st.info("No members in database.")
        return
    
    # Filter by search
    filtered_members = members
    if search_term:
        filtered_members = [m for m in members if search_term.lower() in m['name'].lower()]
        st.caption(f"Found {len(filtered_members)} members matching '{search_term}'")
    
    # Sort alphabetically
    filtered_members.sort(key=lambda x: x['name'].lower())
    
    # Display in expandable sections
    for idx, member in enumerate(filtered_members):
        member_key = f"member_{member['name'].replace(' ', '_')}_{idx}"
        
        # Determine status (default Active)
        status = member.get('status', 'Active')
        status_emoji = "✅" if status == 'Active' else "🚫"
        
        with st.expander(f"{status_emoji} {member['name']} ({member['gender']}, {member['dob']})", 
                        expanded=False):
            
            # Edit form
            with st.form(f"edit_form_{member_key}"):
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                
                edit_name = col1.text_input("Name", member['name'], key=f"name_{member_key}")
                edit_dob = col2.text_input("DOB (YYYY-MM-DD)", member['dob'], key=f"dob_{member_key}")
                edit_gender = col3.selectbox("Gender", ["Male", "Female"], 
                                           index=0 if member['gender'] == 'Male' else 1,
                                           key=f"gender_{member_key}")
                edit_status = col4.selectbox("Status", ["Active", "Left"],
                                           index=0 if status == 'Active' else 1,
                                           key=f"status_{member_key}")
                
                col5, col6 = st.columns(2)
                
                with col5:
                    if st.form_submit_button("💾 Save Changes", use_container_width=True):
                        # Validate
                        if not edit_name or not edit_dob:
                            st.error("Name and DOB are required")
                        else:
                            r = redis_mgr.conn
                            if r:
                                # Update in Redis list
                                updated_member = {
                                    "name": edit_name.strip(),
                                    "dob": edit_dob,
                                    "gender": edit_gender,
                                    "status": edit_status
                                }
                                
                                # Find and replace in list
                                raw_members = r.lrange("members", 0, -1)
                                for i, raw_member in enumerate(raw_members):
                                    m = json.loads(raw_member)
                                    if m['name'] == member['name']:
                                        r.lset("members", i, json.dumps(updated_member))
                                        break
                                
                                # Clear caches
                                redis_mgr.clear_cache("members_data")
                                redis_mgr.clear_cache("cached_pb_leaderboard")
                                st.cache_data.clear()
                                
                                st.success(f"Updated {edit_name}")
                                time.sleep(1)
                                st.rerun()
                
                with col6:
                    if st.form_submit_button("🗑️ Delete Member", use_container_width=True, type="secondary"):
                        r = redis_mgr.conn
                        if r:
                            # Find and remove from list
                            raw_members = r.lrange("members", 0, -1)
                            for raw_member in raw_members:
                                m = json.loads(raw_member)
                                if m['name'] == member['name']:
                                    r.lrem("members", 1, raw_member)
                                    break
                            
                            # Clear caches
                            redis_mgr.clear_cache("members_data")
                            redis_mgr.clear_cache("cached_pb_leaderboard")
                            st.cache_data.clear()
                            
                            st.warning(f"Deleted {member['name']}")
                            time.sleep(1)
                            st.rerun()

# ============================================================
# SECTION 9: TAB 3 - PB SUBMISSIONS
# ============================================================
def render_submissions_tab():
    """Render PB submissions approval tab"""
    st.title("📥 PB Submissions Approval")
    
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    # Load pending submissions
    pending_raw = r.lrange("pending_results", 0, -1)
    pending = [json.loads(p) for p in pending_raw]
    
    if not pending:
        st.info("✅ No pending PB submissions.")
        return
    
    st.subheader(f"Pending Submissions ({len(pending)})")
    
    # Load members for lookup
    member_dict = get_member_dict()
    
    for idx, submission in enumerate(pending):
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**{submission['name']}** - {submission['distance']}")
                st.caption(f"Time: {submission['time_display']} | Location: {submission['location']}")
                st.caption(f"Date: {submission['race_date']}")
            
            with col2:
                # Check if member exists
                member_info = member_dict.get(submission['name'])
                
                if not member_info:
                    st.error("Member not found")
                    continue
                
                # Approve button
                if st.button("✅ Approve", key=f"approve_{idx}", use_container_width=True):
                    # Create race result entry
                    race_entry = {
                        "name": submission['name'],
                        "gender": member_info['gender'],
                        "dob": member_info['dob'],
                        "distance": submission['distance'],
                        "time_seconds": time_to_seconds(submission['time_display']),
                        "time_display": format_time_string(submission['time_display']),
                        "location": submission['location'],
                        "race_date": submission['race_date']
                    }
                    
                    # Add to race results
                    r.rpush("race_results", json.dumps(race_entry))
                    
                    # Remove from pending
                    r.lrem("pending_results", 1, json.dumps(submission))
                    
                    # Clear caches
                    redis_mgr.clear_cache("race_results_data")
                    redis_mgr.clear_cache("cached_pb_leaderboard")
                    st.cache_data.clear()
                    
                    st.success(f"Approved PB for {submission['name']}")
                    time.sleep(1)
                    st.rerun()
                
                # Reject button
                if st.button("❌ Reject", key=f"reject_{idx}", use_container_width=True, type="secondary"):
                    r.lrem("pending_results", 1, json.dumps(submission))
                    st.warning(f"Rejected submission for {submission['name']}")
                    time.sleep(1)
                    st.rerun()

# ============================================================
# SECTION 10: TAB 4 - RACE LOG
# ============================================================
def render_racelog_tab():
    """Render race log management tab"""
    st.title("📋 Race Log Management")
    
    # Load data
    results = load_race_results(redis_mgr)
    
    if not results:
        st.info("No race results in database.")
        return
    
    st.subheader(f"Race Results ({len(results)} total)")
    
    # Convert to DataFrame for display
    df = pd.DataFrame(results)
    
    # Add calculated columns for display
    df['date_dt'] = pd.to_datetime(df['race_date'])
    df = df.sort_values('date_dt', ascending=False)
    
    # Search and filter
    col1, col2, col3 = st.columns(3)
    with col1:
        search_name = st.text_input("Search by name", "")
    with col2:
        filter_distance = st.selectbox("Filter by distance", 
                                     ["All"] + sorted(df['distance'].unique().tolist()))
    with col3:
        items_per_page = st.selectbox("Results per page", [10, 25, 50, 100], index=1)
    
    # Apply filters
    filtered_df = df.copy()
    if search_name:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search_name, case=False, na=False)]
    if filter_distance != "All":
        filtered_df = filtered_df[filtered_df['distance'] == filter_distance]
    
    # Pagination
    total_pages = max(1, (len(filtered_df) + items_per_page - 1) // items_per_page)
    page_number = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    
    start_idx = (page_number - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(filtered_df))
    
    # Display current page
    st.caption(f"Showing {start_idx + 1}-{end_idx} of {len(filtered_df)} results")
    
    # Edit/Delete interface
    for idx in range(start_idx, end_idx):
        result = filtered_df.iloc[idx]
        
        # Find original index in Redis list
        r = redis_mgr.conn
        if not r:
            continue
        
        raw_results = r.lrange("race_results", 0, -1)
        redis_idx = None
        for i, raw in enumerate(raw_results):
            if json.loads(raw)['name'] == result['name'] and \
               json.loads(raw)['race_date'] == result['race_date'] and \
               json.loads(raw)['distance'] == result['distance']:
                redis_idx = i
                break
        
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"**{result['name']}** ({result['gender']})")
                st.caption(f"{result['distance']} - {result['time_display']}")
                st.caption(f"{result['location']} on {result['race_date']}")
            
            with col2:
                edit_key = f"edit_race_{redis_idx}"
                if st.button("✏️ Edit", key=f"edit_btn_{redis_idx}", use_container_width=True):
                    st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                
                if st.button("🗑️", key=f"del_btn_{redis_idx}", use_container_width=True, type="secondary"):
                    if redis_idx is not None:
                        r.lset("race_results", redis_idx, "DELETE_ME")
                        r.lrem("race_results", 1, "DELETE_ME")
                        
                        # Clear caches
                        redis_mgr.clear_cache("race_results_data")
                        redis_mgr.clear_cache("cached_pb_leaderboard")
                        st.cache_data.clear()
                        
                        st.success(f"Deleted race result for {result['name']}")
                        time.sleep(1)
                        st.rerun()
            
            # Edit form (if opened)
            if st.session_state.get(edit_key, False):
                with st.form(f"edit_race_form_{redis_idx}"):
                    col1, col2, col3 = st.columns(3)
                    
                    edit_name = col1.text_input("Name", result['name'])
                    edit_distance = col2.selectbox("Distance", 
                                                 ["5k", "10k", "10 Mile", "HM", "Marathon"],
                                                 index=["5k", "10k", "10 Mile", "HM", "Marathon"].index(result['distance']))
                    edit_time = col3.text_input("Time (HH:MM:SS)", result['time_display'])
                    
                    col4, col5 = st.columns(2)
                    edit_location = col4.text_input("Location", result['location'])
                    edit_date = col5.text_input("Date (YYYY-MM-DD)", result['race_date'])
                    
                    if st.form_submit_button("💾 Save Changes", type="primary"):
                        if not all([edit_name, edit_time, edit_location, edit_date]):
                            st.error("All fields are required")
                        else:
                            # Get member info
                            member_dict = get_member_dict()
                            member_info = member_dict.get(edit_name)
                            
                            if not member_info:
                                st.error(f"Member '{edit_name}' not found in database")
                            else:
                                updated_entry = {
                                    "name": edit_name,
                                    "gender": member_info['gender'],
                                    "dob": member_info['dob'],
                                    "distance": edit_distance,
                                    "time_seconds": time_to_seconds(edit_time),
                                    "time_display": format_time_string(edit_time),
                                    "location": edit_location,
                                    "race_date": edit_date
                                }
                                
                                # Update in Redis
                                if redis_idx is not None:
                                    r.lset("race_results", redis_idx, json.dumps(updated_entry))
                                
                                # Clear caches
                                redis_mgr.clear_cache("race_results_data")
                                redis_mgr.clear_cache("cached_pb_leaderboard")
                                st.cache_data.clear()
                                
                                st.success("Race result updated")
                                st.session_state[edit_key] = False
                                time.sleep(1)
                                st.rerun()

# ============================================================
# SECTION 11: TAB 5 - CHAMPIONSHIP (BASIC VERSION)
# ============================================================
def render_championship_tab():
    """Render championship management tab"""
    st.title("🎖️ Championship Management")
    
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    # Create tabs for championship features
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Calendar", 
        "⏱️ Winner Times", 
        "📥 Submissions", 
        "📊 Standings"
    ])
    
    with tab1:
        st.subheader("Championship Calendar 2026")
        
        # Load or create calendar
        cal_json = r.get("champ_calendar_2026")
        if cal_json:
            calendar = json.loads(cal_json)
        else:
            # Create default calendar
            calendar = []
            for i in range(15):
                if i == 14:  # Race 15
                    calendar.append({
                        "name": "Any Marathon (Power of 10)",
                        "date": "Any 2026 Marathon",
                        "distance": "Marathon",
                        "terrain": "Road"
                    })
                else:
                    calendar.append({
                        "name": f"Race {i+1}",
                        "date": "TBC",
                        "distance": "TBC",
                        "terrain": "Road"
                    })
        
        # Edit calendar
        with st.form("calendar_form"):
            updated_calendar = []
            
            for i in range(15):
                st.markdown(f"**Race {i+1}**")
                race = calendar[i] if i < len(calendar) else {}
                
                col1, col2, col3, col4 = st.columns(4)
                
                if i == 14:  # Race 15 is fixed
                    name = col1.text_input("Name", "Any Marathon (Power of 10)", 
                                          key=f"name_{i}", disabled=True)
                    date_val = col2.text_input("Date", "Any 2026 Marathon", 
                                              key=f"date_{i}", disabled=True)
                    distance = col3.text_input("Distance", "Marathon", 
                                              key=f"dist_{i}", disabled=True)
                    terrain = col4.selectbox("Terrain", ["Road"], 
                                           key=f"terr_{i}", disabled=True)
                else:
                    name = col1.text_input("Name", race.get("name", f"Race {i+1}"), 
                                          key=f"name_{i}")
                    date_val = col2.text_input("Date (YYYY-MM-DD or TBC)", 
                                              race.get("date", "TBC"), key=f"date_{i}")
                    distance = col3.selectbox("Distance", 
                                             ["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"],
                                             index=["5k", "10k", "10 Mile", "HM", "Marathon", "TBC"]
                                             .index(race.get("distance", "TBC")),
                                             key=f"dist_{i}")
                    terrain = col4.selectbox("Terrain", 
                                            ["Road", "Trail", "Fell", "XC", "TBC"],
                                            index=["Road", "Trail", "Fell", "XC", "TBC"]
                                            .index(race.get("terrain", "Road")),
                                            key=f"terr_{i}")
                
                updated_calendar.append({
                    "name": name,
                    "date": date_val,
                    "distance": distance,
                    "terrain": terrain
                })
                
                st.divider()
            
            if st.form_submit_button("💾 Save Calendar", type="primary"):
                r.set("champ_calendar_2026", json.dumps(updated_calendar))
                st.success("Calendar saved!")
                time.sleep(1)
                st.rerun()
    
    with tab2:
        st.subheader("Winner Times Setup")
        st.info("This page will allow setting winner times per category/gender for each race.")
        st.write("Feature to be implemented based on your category structure.")
    
    with tab3:
        st.subheader("Championship Submissions")
        
        # Load pending championship submissions
        pending_raw = r.lrange("champ_pending", 0, -1)
        pending = [json.loads(p) for p in pending_raw]
        
        if not pending:
            st.info("No pending championship submissions.")
        else:
            st.write(f"Pending submissions: {len(pending)}")
            # Implementation would go here
    
    with tab4:
        st.subheader("Championship Standings")
        st.info("Standings will be calculated once winner times are set.")
        st.write("Feature to be implemented.")

# ============================================================
# SECTION 12: TAB 6 - SYSTEM TOOLS
# ============================================================
def render_system_tab():
    """Render system tools tab"""
    st.title("⚙️ System Tools")
    
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    # Create tabs for different system functions
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔧 Settings", 
        "💾 Export", 
        "📥 Import", 
        "🛠️ Maintenance"
    ])
    
    with tab1:
        st.subheader("Club Settings")
        
        # Load current settings
        settings_json = r.get("club_settings")
        if settings_json:
            settings = json.loads(settings_json)
        else:
            settings = {
                "club_name": "Bramley Breezers",
                "logo_url": "",
                "admin_password": "Breezersrock!",
                "age_mode": "5 Year"
            }
        
        with st.form("settings_form"):
            col1, col2 = st.columns(2)
            
            club_name = col1.text_input("Club Name", settings.get("club_name", ""))
            logo_url = col2.text_input("Logo URL", settings.get("logo_url", ""))
            
            col3, col4 = st.columns(2)
            admin_pwd = col3.text_input("Admin Password", 
                                       settings.get("admin_password", ""), 
                                       type="password")
            age_mode = col4.selectbox("Age Category Mode", 
                                     ["5 Year (V35, V40, V45...)", "10 Year (V40, V50, V60...)"],
                                     index=0 if "5" in settings.get("age_mode", "") else 1)
            
            if st.form_submit_button("💾 Save Settings", type="primary"):
                updated_settings = {
                    "club_name": club_name,
                    "logo_url": logo_url,
                    "admin_password": admin_pwd,
                    "age_mode": "5 Year" if "5" in age_mode else "10 Year"
                }
                
                # Save to Redis
                r.set("club_settings", json.dumps(updated_settings))
                r.set("age_mode", "5Y" if "5" in age_mode else "10Y")
                if logo_url:
                    r.set("club_logo_url", logo_url)
                    r.set("logo_url", logo_url)
                
                # Clear caches
                redis_mgr.clear_cache()
                st.cache_data.clear()
                
                st.success("Settings saved!")
                time.sleep(1)
                st.rerun()
    
    with tab2:
        st.subheader("Data Export")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 Export Members", use_container_width=True):
                members = load_members(redis_mgr)
                if members:
                    df = pd.DataFrame(members)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Members CSV",
                        data=csv,
                        file_name="bbpb_members.csv",
                        mime="text/csv",
                        key="export_members"
                    )
                else:
                    st.warning("No members to export")
        
        with col2:
            if st.button("📥 Export Race Results", use_container_width=True):
                results = load_race_results(redis_mgr)
                if results:
                    # Create simplified export (without internal fields)
                    export_data = []
                    for r in results:
                        export_data.append({
                            "name": r['name'],
                            "distance": r['distance'],
                            "location": r['location'],
                            "race_date": r['race_date'],
                            "time_display": r['time_display']
                        })
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Race Results CSV",
                        data=csv,
                        file_name="bbpb_race_results.csv",
                        mime="text/csv",
                        key="export_results"
                    )
                else:
                    st.warning("No race results to export")
        
        with col3:
            if st.button("📥 Export Championship", use_container_width=True):
                # This would export championship data
                st.info("Championship export to be implemented")
    
    with tab3:
        st.subheader("Data Import")
        
        import_type = st.selectbox("Select import type", 
                                 ["Members CSV", "Race Results CSV"])
        
        uploaded_file = st.file_uploader(f"Choose {import_type} file", 
                                        type="csv")
        
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            st.write(f"Preview ({len(df)} rows):")
            st.dataframe(df.head(), use_container_width=True)
            
            if st.button("Import Data", type="primary"):
                if import_type == "Members CSV":
                    # Import members
                    imported = 0
                    for _, row in df.iterrows():
                        member_data = {
                            "name": str(row.get('name', '')).strip(),
                            "dob": str(row.get('dob', '2000-01-01')),
                            "gender": str(row.get('gender', 'Male'))
                        }
                        if member_data['name']:
                            r.rpush("members", json.dumps(member_data))
                            imported += 1
                    
                    st.success(f"Imported {imported} members")
                
                elif import_type == "Race Results CSV":
                    # Import race results
                    member_dict = get_member_dict()
                    imported = 0
                    
                    for _, row in df.iterrows():
                        name = str(row.get('name', '')).strip()
                        if name in member_dict:
                            member_info = member_dict[name]
                            race_entry = {
                                "name": name,
                                "gender": member_info['gender'],
                                "dob": member_info['dob'],
                                "distance": str(row.get('distance', '5k')),
                                "time_seconds": time_to_seconds(str(row.get('time_display', '00:00:00'))),
                                "time_display": format_time_string(str(row.get('time_display', '00:00:00'))),
                                "location": str(row.get('location', 'Unknown')),
                                "race_date": str(row.get('race_date', '2026-01-01'))
                            }
                            r.rpush("race_results", json.dumps(race_entry))
                            imported += 1
                    
                    st.success(f"Imported {imported} race results")
                
                # Clear caches
                redis_mgr.clear_cache()
                st.cache_data.clear()
                time.sleep(2)
                st.rerun()
    
    with tab4:
        st.subheader("Maintenance Tools")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Rebuild Leaderboard Cache", use_container_width=True):
                with st.spinner("Rebuilding cache..."):
                    if rebuild_leaderboard_cache():
                        st.success("Leaderboard cache rebuilt!")
                    else:
                        st.error("Cache rebuild failed")
        
        with col2:
            if st.button("🧹 Clear Pending Submissions", use_container_width=True, type="secondary"):
                r.delete("pending_results")
                r.delete("champ_pending")
                st.success("Pending submissions cleared!")
        
        st.divider()
        
        # Danger zone
        with st.expander("⚠️ Danger Zone", expanded=False):
            st.warning("These actions cannot be undone!")
            
            if st.button("🗑️ Clear All Race Results", type="secondary"):
                if st.checkbox("I understand this will delete ALL race results"):
                    r.delete("race_results")
                    r.delete("cached_pb_leaderboard")
                    redis_mgr.clear_cache()
                    st.cache_data.clear()
                    st.error("All race results deleted!")
                    time.sleep(2)
                    st.rerun()
            
            if st.button("🔥 Reset Entire System", type="secondary"):
                if st.checkbox("I understand this will reset ALL data except settings"):
                    # Keep only settings and password
                    settings = r.get("club_settings")
                    password = r.get("admin_password")
                    
                    # Delete all keys except settings
                    keys = r.keys("*")
                    for key in keys:
                        if key not in ["club_settings", "admin_password", "club_logo_url", "logo_url", "age_mode"]:
                            r.delete(key)
                    
                    redis_mgr.clear_cache()
                    st.cache_data.clear()
                    st.error("System reset complete!")
                    time.sleep(2)
                    st.rerun()

# ============================================================
# SECTION 13: MAIN APPLICATION CONTROLLER
# ============================================================
def main():
    """Main application entry point"""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "leaderboard"
    
    # Render sidebar (includes auth check)
    render_sidebar()
    
    # Get current tab and render
    current_tab = st.session_state.get("current_tab", "leaderboard")
    
    if current_tab == "leaderboard":
        render_leaderboard_tab()
    elif current_tab == "members":
        render_members_tab()
    elif current_tab == "submissions":
        render_submissions_tab()
    elif current_tab == "racelog":
        render_racelog_tab()
    elif current_tab == "championship":
        render_championship_tab()
    elif current_tab == "system":
        render_system_tab()
    else:
        render_leaderboard_tab()

# ============================================================
# RUN THE APPLICATION
# ============================================================
if __name__ == "__main__":
    main()