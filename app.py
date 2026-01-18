# app.py - COMPLETE OPTIMIZED BBPB ADMIN WITH FULL CHAMPIONSHIP
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
                self._connection.ping()
            except Exception as e:
                st.error(f"⚠️ Redis connection failed: {str(e)[:100]}")
                return None
        return self._connection
    
    def get_cached(self, key: str, max_age: int = 60) -> Optional[Any]:
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).seconds < max_age:
                return data
        return None
    
    def set_cached(self, key: str, data: Any):
        self._cache[key] = (data, datetime.now())
    
    def clear_cache(self, key_prefix: str = None):
        if key_prefix:
            for k in list(self._cache.keys()):
                if k.startswith(key_prefix):
                    del self._cache[k]
        else:
            self._cache.clear()

# Global instance
redis_mgr = RedisManager()

# ============================================================
# SECTION 3: AUTHENTICATION
# ============================================================
def require_auth():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        if 'login_time' in st.session_state:
            session_age = datetime.now() - st.session_state.login_time
            if session_age > timedelta(hours=8):
                st.session_state.authenticated = False
                return False
        return True
    return False

def render_login():
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
    members = load_members(redis_mgr)
    return {m['name']: m for m in members}

# ============================================================
# SECTION 5: UTILITY FUNCTIONS
# ============================================================
def format_time_string(t_str: str) -> str:
    try:
        t_str = str(t_str).strip()
        if not t_str:
            return "00:00:00"
        
        parts = t_str.split(':')
        if len(parts) == 2:
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        else:
            return "00:00:00"
    except:
        return "00:00:00"

def time_to_seconds(t_str: str) -> int:
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
        else:
            return 999999
    except:
        return 999999

def seconds_to_time(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def get_category(dob_str: str, race_date_str: str, age_mode: str = None) -> str:
    try:
        if age_mode is None:
            r = redis_mgr.conn
            if r:
                stored = r.get("age_mode") or "5 Year"
                age_mode = "5Y" if "5" in stored else "10Y"
            else:
                age_mode = "10Y"
        
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        race_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        
        age = race_date.year - dob.year
        if (race_date.month, race_date.day) < (dob.month, dob.day):
            age -= 1
        
        if age_mode == "5Y":
            threshold = 35
            step = 5
        else:
            threshold = 40
            step = 10
        
        if age < threshold:
            return "Senior"
        
        base_age = (age // step) * step
        return f"V{base_age}"
        
    except Exception as e:
        return "Unknown"

def get_seconds(t_str: str) -> int:
    """Alias for time_to_seconds for compatibility with 4_Championship.py"""
    return time_to_seconds(t_str)

def rebuild_leaderboard_cache():
    r = redis_mgr.conn
    if not r:
        return False
    
    try:
        raw_results = r.lrange("race_results", 0, -1)
        if not raw_results:
            r.delete("cached_pb_leaderboard")
            return True
        
        results = [json.loads(res) for res in raw_results]
        df = pd.DataFrame(results)
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        r.set("cached_pb_leaderboard", df.to_json())
        
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
    with st.sidebar:
        r = redis_mgr.conn
        logo_url = None
        if r:
            logo_url = r.get("club_logo_url") or r.get("logo_url")
        
        if logo_url and logo_url.startswith("http"):
            st.image(logo_url, width=180)
        else:
            st.title("🏃 BBPB Admin")
        
        st.divider()
        
        if not require_auth():
            render_login()
            st.stop()
        
        st.success("✅ Authenticated")
        
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            st.session_state.authenticated = False
            redis_mgr.clear_cache()
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
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
    st.title("🏆 Personal Best Leaderboard")
    
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    cached_json = r.get("cached_pb_leaderboard")
    
    if cached_json:
        try:
            df = pd.read_json(cached_json)
            cache_status = "✅ Using cached leaderboard"
        except:
            cache_status = "⚠️ Cache corrupted, rebuilding..."
            cached_json = None
    
    if not cached_json:
        with st.spinner("Building leaderboard from raw data..."):
            results = load_race_results(redis_mgr)
            if not results:
                st.info("No race results found in database.")
                return
            
            df = pd.DataFrame(results)
            df['race_date_dt'] = pd.to_datetime(df['race_date'])
            r.set("cached_pb_leaderboard", df.to_json())
            cache_status = "🔄 Built new leaderboard cache"
    
    st.sidebar.caption(cache_status)
    
    members = load_members(redis_mgr)
    active_names = [m['name'] for m in members if m.get('status', 'Active') == 'Active']
    
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    years = ["All-Time"] + sorted(
        [str(y) for y in df['race_date_dt'].dt.year.unique()],
        reverse=True
    )
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_year = st.selectbox("Select Season:", years, key="year_filter")
    
    display_df = df.copy()
    if selected_year != "All-Time":
        display_df = display_df[display_df['race_date_dt'].dt.year == int(selected_year)]
    
    age_mode_setting = r.get("age_mode") or "5 Year"
    age_mode = "5Y" if "5" in age_mode_setting else "10Y"
    
    display_df['Category'] = display_df.apply(
        lambda x: get_category(x['dob'], x['race_date'], age_mode),
        axis=1
    )
    
    total_records = len(display_df)
    unique_members = display_df['name'].nunique()
    st.caption(f"Showing {total_records} results for {unique_members} members")
    
    distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]
    
    for distance in distances:
        st.markdown(f"### 🏁 {distance}")
        
        col_male, col_female = st.columns(2)
        
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
    st.title("👥 Member Management")
    
    members = load_members(redis_mgr)
    search_term = st.text_input("🔍 Search members by name", "")
    
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
                        }
                        r.rpush("members", json.dumps(member_data))
                        redis_mgr.clear_cache("members_data")
                        st.cache_data.clear()
                        st.success(f"Added member: {new_name}")
                        time.sleep(1)
                        st.rerun()
    
    st.divider()
    st.subheader(f"Members ({len(members)} total)")
    
    if not members:
        st.info("No members in database.")
        return
    
    filtered_members = members
    if search_term:
        filtered_members = [m for m in members if search_term.lower() in m['name'].lower()]
        st.caption(f"Found {len(filtered_members)} members matching '{search_term}'")
    
    filtered_members.sort(key=lambda x: x['name'].lower())
    
    for idx, member in enumerate(filtered_members):
        member_key = f"member_{member['name'].replace(' ', '_')}_{idx}"
        status = member.get('status', 'Active')
        status_emoji = "✅" if status == 'Active' else "🚫"
        
        with st.expander(f"{status_emoji} {member['name']} ({member['gender']}, {member['dob']})", 
                        expanded=False):
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
                        if not edit_name or not edit_dob:
                            st.error("Name and DOB are required")
                        else:
                            r = redis_mgr.conn
                            if r:
                                updated_member = {
                                    "name": edit_name.strip(),
                                    "dob": edit_dob,
                                    "gender": edit_gender,
                                    "status": edit_status
                                }
                                raw_members = r.lrange("members", 0, -1)
                                for i, raw_member in enumerate(raw_members):
                                    m = json.loads(raw_member)
                                    if m['name'] == member['name']:
                                        r.lset("members", i, json.dumps(updated_member))
                                        break
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
                            raw_members = r.lrange("members", 0, -1)
                            for raw_member in raw_members:
                                m = json.loads(raw_member)
                                if m['name'] == member['name']:
                                    r.lrem("members", 1, raw_member)
                                    break
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
    st.title("📥 PB Submissions Approval")
    
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    pending_raw = r.lrange("pending_results", 0, -1)
    pending = [json.loads(p) for p in pending_raw]
    
    if not pending:
        st.info("✅ No pending PB submissions.")
        return
    
    st.subheader(f"Pending Submissions ({len(pending)})")
    member_dict = get_member_dict()
    
    for idx, submission in enumerate(pending):
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**{submission['name']}** - {submission['distance']}")
                st.caption(f"Time: {submission['time_display']} | Location: {submission['location']}")
                st.caption(f"Date: {submission['race_date']}")
            
            with col2:
                member_info = member_dict.get(submission['name'])
                
                if not member_info:
                    st.error("Member not found")
                    continue
                
                if st.button("✅ Approve", key=f"approve_{idx}", use_container_width=True):
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
                    r.rpush("race_results", json.dumps(race_entry))
                    r.lrem("pending_results", 1, json.dumps(submission))
                    redis_mgr.clear_cache("race_results_data")
                    redis_mgr.clear_cache("cached_pb_leaderboard")
                    st.cache_data.clear()
                    st.success(f"Approved PB for {submission['name']}")
                    time.sleep(1)
                    st.rerun()
                
                if st.button("❌ Reject", key=f"reject_{idx}", use_container_width=True, type="secondary"):
                    r.lrem("pending_results", 1, json.dumps(submission))
                    st.warning(f"Rejected submission for {submission['name']}")
                    time.sleep(1)
                    st.rerun()

# ============================================================
# SECTION 10: TAB 4 - RACE LOG
# ============================================================
def render_racelog_tab():
    st.title("📋 Race Log Management")
    
    results = load_race_results(redis_mgr)
    
    if not results:
        st.info("No race results in database.")
        return
    
    st.subheader(f"Race Results ({len(results)} total)")
    df = pd.DataFrame(results)
    df['date_dt'] = pd.to_datetime(df['race_date'])
    df = df.sort_values('date_dt', ascending=False)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        search_name = st.text_input("Search by name", "")
    with col2:
        filter_distance = st.selectbox("Filter by distance", 
                                     ["All"] + sorted(df['distance'].unique().tolist()))
    with col3:
        items_per_page = st.selectbox("Results per page", [10, 25, 50, 100], index=1)
    
    filtered_df = df.copy()
    if search_name:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search_name, case=False, na=False)]
    if filter_distance != "All":
        filtered_df = filtered_df[filtered_df['distance'] == filter_distance]
    
    total_pages = max(1, (len(filtered_df) + items_per_page - 1) // items_per_page)
    page_number = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    
    start_idx = (page_number - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(filtered_df))
    
    st.caption(f"Showing {start_idx + 1}-{end_idx} of {len(filtered_df)} results")
    
    for idx in range(start_idx, end_idx):
        result = filtered_df.iloc[idx]
        
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
                        redis_mgr.clear_cache("race_results_data")
                        redis_mgr.clear_cache("cached_pb_leaderboard")
                        st.cache_data.clear()
                        st.success(f"Deleted race result for {result['name']}")
                        time.sleep(1)
                        st.rerun()
            
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
                                if redis_idx is not None:
                                    r.lset("race_results", redis_idx, json.dumps(updated_entry))
                                redis_mgr.clear_cache("race_results_data")
                                redis_mgr.clear_cache("cached_pb_leaderboard")
                                st.cache_data.clear()
                                st.success("Race result updated")
                                st.session_state[edit_key] = False
                                time.sleep(1)
                                st.rerun()

# ============================================================
# SECTION 11: TAB 5 - CHAMPIONSHIP (COMPLETE FROM 4_Championship.py)
# ============================================================
def render_championship_tab():
    """Complete championship system from 4_Championship.py"""
    st.title("🏅 Championship Management")
    
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    # Load essential data
    raw_mems = r.lrange("members", 0, -1)
    member_db = {json.loads(m)['name']: json.loads(m) for m in raw_mems}
    
    # Get calendar
    cal_raw = r.get("champ_calendar_2026")
    if cal_raw:
        champ_calendar = json.loads(cal_raw)
    else:
        # Create default calendar
        champ_calendar = []
        for i in range(15):
            if i == 14:  # Race 15
                champ_calendar.append({
                    "name": "Any Marathon (Power of 10)",
                    "date": "Any 2026 Marathon",
                    "distance": "Marathon",
                    "terrain": "Road"
                })
            else:
                champ_calendar.append({
                    "name": f"Race {i+1}",
                    "date": "TBC",
                    "distance": "TBC",
                    "terrain": "Road"
                })
    
    # Create tabs matching 4_Championship.py
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Pending Approvals", 
        "🗓️ Calendar Setup", 
        "📊 Championship Log", 
        "🏆 Leaderboard"
    ])
    
    # ========== TAB 1: PENDING APPROVALS ==========
    with tab1:
        st.subheader("📥 Championship Submissions Pending Approval")
        
        # Load pending submissions
        pending_raw = r.lrange("champ_pending", 0, -1)
        pending = [json.loads(p) for p in pending_raw]
        
        if not pending:
            st.info("No pending championship results.")
        else:
            for i, p_raw in enumerate(pending):
                p = json.loads(p_raw)
                with st.expander(f"Review: {p['name']} - {p.get('race_name', 'Unknown Race')}"):
                    st.write(f"**Submitted Time:** {p['time_display']}")
                    st.write(f"**Submitted Date/Location:** {p.get('date', 'Unknown')} / {p.get('race_name', 'Unknown')}")
                    
                    if not champ_calendar:
                        st.error("Setup the calendar in the next tab first.")
                        continue
                    
                    # Race selection
                    race_options = [f"Race {idx+1}: {rc.get('name')}" for idx, rc in enumerate(champ_calendar)]
                    sel_race_str = st.selectbox("Assign to Calendar Race", race_options, key=f"conf_race_{i}")
                    race_idx = race_options.index(sel_race_str)
                    is_race_15 = (race_idx == 14)
                    
                    col1, col2 = st.columns(2)
                    
                    # Winner time input
                    win_time = col1.text_input(f"Winner's Time (HH:MM:SS)", "00:00:00", key=f"win_{i}")
                    runner_sec = get_seconds(p['time_display'])
                    winner_sec = get_seconds(win_time)
                    
                    # Points calculation (from 4_Championship.py)
                    calc_pts = round((winner_sec / runner_sec) * 100, 2) if winner_sec > 0 else 0.0
                    pts = col2.number_input("Final Points to Award", 0.0, 200.0, calc_pts, key=f"pts_{i}")
                    st.caption(f"Calculated based on winner: {calc_pts:.2f}")
                    
                    st.markdown("---")
                    
                    # Option to add to PB leaderboard
                    log_pb = st.checkbox("Also add to Main PB Leaderboard?", value=True, key=f"log_pb_{i}")
                    
                    if is_race_15:
                        st.warning("🏆 Race 15 (Any Marathon) detected. Locked to 'Marathon' PB Category.")
                        pb_dist = "Marathon"
                    else:
                        pb_dist = st.selectbox("PB Category", ["5k", "10k", "10 Mile", "HM", "Marathon"], 
                                             key=f"pb_dist_{i}")
                    
                    # Approve button
                    if st.button("✅ Approve Result", key=f"app_{i}", type="primary"):
                        # Get member info
                        m_info = member_db.get(p['name'], {})
                        if not m_info:
                            st.error(f"Member {p['name']} not found in database")
                            continue
                        
                        # Determine date
                        if is_race_15:
                            final_date = p.get('date', '2026-01-01')
                        else:
                            final_date = champ_calendar[race_idx].get('date', '2026-01-01')
                        
                        # Calculate category
                        settings_raw = r.get("club_settings")
                        if settings_raw:
                            settings = json.loads(settings_raw)
                            age_mode = settings.get('age_mode', '5 Year')
                        else:
                            age_mode = '5 Year'
                        
                        cat = get_category(m_info.get('dob', '2000-01-01'), final_date, 
                                         "5Y" if "5" in age_mode else "10Y")
                        
                        # Create championship entry
                        champ_entry = {
                            "name": p['name'], 
                            "race_name": p.get('race_name', champ_calendar[race_idx].get('name', 'Unknown')),
                            "date": final_date,
                            "points": pts,
                            "category": cat,
                            "gender": m_info.get('gender', 'U')
                        }
                        
                        # Save to championship results
                        r.rpush("champ_results_final", json.dumps(champ_entry))
                        
                        # Optionally add to PB leaderboard
                        if log_pb:
                            pb_entry = {
                                "name": p['name'],
                                "distance": pb_dist,
                                "location": p.get('race_name', 'Unknown'),
                                "race_date": final_date,
                                "time_display": p['time_display'],
                                "time_seconds": runner_sec,
                                "gender": m_info.get('gender', 'U'),
                                "dob": m_info.get('dob', '2000-01-01')
                            }
                            r.rpush("race_results", json.dumps(pb_entry))
                        
                        # Rebuild caches
                        rebuild_leaderboard_cache()
                        
                        # Remove from pending
                        r.lset("champ_pending", i, "WIPE")
                        r.lrem("champ_pending", 1, "WIPE")
                        
                        st.success(f"Approved {p['name']}!")
                        time.sleep(2)
                        st.rerun()
    
    # ========== TAB 2: CALENDAR SETUP ==========
    with tab2:
        st.subheader("🗓️ 15-Race Championship Calendar Setup")
        
        if len(champ_calendar) < 15:
            champ_calendar = [{"name": "TBC", "date": "TBC", "distance": "TBC", "terrain": "Road"} for _ in range(15)]
        
        with st.form("cal_form"):
            updated_cal = []
            
            for i in range(15):
                st.markdown(f"**Race {i+1}**")
                race = champ_calendar[i] if i < len(champ_calendar) else {}
                
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
                
                # Race 15 is fixed as Marathon
                if i == 14:
                    name = c1.text_input("Name", "Any Marathon (Power of 10)", 
                                        key=f"n_{i}", disabled=True)
                    is_tbc = False
                    date_val = "Any 2026 Marathon"
                    distance = "Marathon"
                    terrain = "Road"
                    c2.info("Any 2026 Marathon")
                    c3.info("Marathon")
                    c4.info("Road")
                else:
                    name = c1.text_input("Name", race.get("name", f"Race {i+1}"), 
                                        key=f"n_{i}")
                    is_tbc = c5.checkbox("TBC", value=(race.get('date') == "TBC"), 
                                        key=f"tbc_{i}")
                    
                    if is_tbc:
                        date_val = "TBC"
                        distance = "TBC"
                        terrain = "TBC"
                        c2.info("TBC")
                        c3.info("TBC")
                        c4.info("TBC")
                    else:
                        # Try to parse existing date
                        try:
                            d_val = datetime.strptime(race.get('date', '2026-01-01'), '%Y-%m-%d')
                        except:
                            d_val = datetime(2026, 1, 1)
                        
                        date_val = c2.date_input("Date", d_val, key=f"d_{i}", label_visibility="collapsed")
                        distance = c3.selectbox("Distance", 
                                              ["5k", "10k", "10 Mile", "HM", "Marathon"],
                                              index=["5k", "10k", "10 Mile", "HM", "Marathon"]
                                              .index(race.get('distance', '5k')) if race.get('distance') != "TBC" else 0,
                                              key=f"dist_{i}", label_visibility="collapsed")
                        terrain = c4.selectbox("Terrain", 
                                             ["Road", "Trail", "Fell", "XC"],
                                             index=["Road", "Trail", "Fell", "XC"]
                                             .index(race.get('terrain', 'Road')) if race.get('terrain') != "TBC" else 0,
                                             key=f"terr_{i}", label_visibility="collapsed")
                        date_val = str(date_val)
                
                updated_cal.append({
                    "name": name,
                    "date": date_val,
                    "distance": distance,
                    "terrain": terrain
                })
                
                st.divider()
            
            if st.form_submit_button("💾 Save Calendar", type="primary"):
                r.set("champ_calendar_2026", json.dumps(updated_cal))
                rebuild_leaderboard_cache()
                st.success("Calendar Saved and Cache Rebuilt!")
                time.sleep(1)
                st.rerun()
    
    # ========== TAB 3: CHAMPIONSHIP LOG ==========
    with tab3:
        st.subheader("📊 Championship Results Log")
        
        # Load final results
        final_raw = r.lrange("champ_results_final", 0, -1)
        if not final_raw:
            st.info("No championship results yet.")
        else:
            data = [json.loads(x) for x in final_raw]
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            
            # Edit and Delete functionality
            e_col, d_col = st.columns(2)
            
            with e_col:
                with st.expander("📝 Edit Result"):
                    if len(df) > 0:
                        idx = st.number_input("Index to Edit", 0, len(df)-1, 0, key="c_edit_idx")
                        result_to_edit = data[idx]
                        
                        with st.form("c_edit_form"):
                            new_pts = st.number_input("Points", 0.0, 200.0, float(result_to_edit.get('points', 0)))
                            new_cat = st.text_input("Category", result_to_edit.get('category', 'Unknown'))
                            
                            if st.form_submit_button("Save Changes"):
                                result_to_edit['points'] = new_pts
                                result_to_edit['category'] = new_cat
                                r.lset("champ_results_final", int(idx), json.dumps(result_to_edit))
                                rebuild_leaderboard_cache()
                                st.success("Updated!")
                                time.sleep(1)
                                st.rerun()
            
            with d_col:
                with st.expander("🗑️ Delete Result"):
                    if len(df) > 0:
                        del_idx = st.number_input("Index to Delete", 0, len(df)-1, 0, key="c_del_idx")
                        
                        if st.button("Confirm Deletion", type="secondary"):
                            r.lset("champ_results_final", int(del_idx), "WIPE")
                            r.lrem("champ_results_final", 1, "WIPE")
                            rebuild_leaderboard_cache()
                            st.success("Deleted!")
                            time.sleep(1)
                            st.rerun()
    
    # ========== TAB 4: LEADERBOARD ==========
    with tab4:
        st.subheader("🏆 Championship Standings")
        
        # Try to get cached standings
        cache = r.get("cached_champ_standings")
        if cache:
            try:
                standings_df = pd.read_json(cache)
                st.dataframe(standings_df, use_container_width=True)
            except:
                st.info("Standings cache corrupted. Rebuilding...")
                cache = None
        
        if not cache:
            st.info("Standings not yet generated. Approve some championship results first.")

# ============================================================
# SECTION 12: TAB 6 - SYSTEM TOOLS
# ============================================================
def render_system_tab():
    st.title("⚙️ System Tools")
    
    r = redis_mgr.conn
    if not r:
        st.error("Redis connection unavailable")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔧 Settings", 
        "💾 Export", 
        "📥 Import", 
        "🛠️ Maintenance"
    ])
    
    with tab1:
        st.subheader("Club Settings")
        
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
                
                r.set("club_settings", json.dumps(updated_settings))
                r.set("age_mode", "5Y" if "5" in age_mode else "10Y")
                if logo_url:
                    r.set("club_logo_url", logo_url)
                    r.set("logo_url", logo_url)
                
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
                champ_raw = r.lrange("champ_results_final", 0, -1)
                if champ_raw:
                    champ_data = [json.loads(c) for c in champ_raw]
                    df = pd.DataFrame(champ_data)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Championship CSV",
                        data=csv,
                        file_name="bbpb_championship.csv",
                        mime="text/csv",
                        key="export_champ"
                    )
                else:
                    st.warning("No championship results to export")
    
    with tab3:
        st.subheader("Data Import")
        
        import_type = st.selectbox("Select import type", 
                                 ["Members CSV", "Race Results CSV", "Championship CSV"])
        
        uploaded_file = st.file_uploader(f"Choose {import_type} file", 
                                        type="csv")
        
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            st.write(f"Preview ({len(df)} rows):")
            st.dataframe(df.head(), use_container_width=True)
            
            if st.button("Import Data", type="primary"):
                if import_type == "Members CSV":
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
                
                elif import_type == "Championship CSV":
                    imported = 0
                    for _, row in df.iterrows():
                        champ_entry = {
                            "name": str(row.get('name', '')).strip(),
                            "race_name": str(row.get('race_name', 'Unknown')),
                            "date": str(row.get('date', '2026-01-01')),
                            "points": float(row.get('points', 0)),
                            "category": str(row.get('category', 'Unknown')),
                            "gender": str(row.get('gender', 'U'))
                        }
                        if champ_entry['name']:
                            r.rpush("champ_results_final", json.dumps(champ_entry))
                            imported += 1
                    st.success(f"Imported {imported} championship results")
                
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
                    settings = r.get("club_settings")
                    password = r.get("admin_password")
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
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "leaderboard"
    
    render_sidebar()
    
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