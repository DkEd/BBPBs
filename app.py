# app.py - OPTIMIZED REBUILD
# ============================================================
# SECTION 1: IMPORTS & SETUP
# ============================================================
import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date
from functools import lru_cache
import time
from typing import List, Dict, Any, Optional

# Set page config FIRST (must be first Streamlit command)
st.set_page_config(
    page_title="BBPB Admin - Optimized",
    page_icon="🏃",
    layout="wide",  # Keeping wide since you have multi-column layouts
    initial_sidebar_state="expanded"
)

# ============================================================
# SECTION 2: OPTIMIZED REDIS MANAGER (Connection Pooling)
# ============================================================
class RedisManager:
    """Singleton Redis connection manager with smart caching"""
    _instance = None
    _connection = None
    _cache = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def conn(self):
        if self._connection is None:
            try:
                self._connection = redis.from_url(
                    os.environ.get("REDIS_URL"),
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    retry_on_timeout=True,
                    max_connections=10
                )
                # Test connection
                self._connection.ping()
            except Exception as e:
                st.error(f"Redis connection failed: {e}")
                # Fallback to empty data mode for development
                return None
        return self._connection
    
    def clear_cache(self, key_prefix=None):
        """Clear all or specific cached items"""
        if key_prefix:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(key_prefix)]
            for k in keys_to_delete:
                del self._cache[k]
        else:
            self._cache.clear()
    
    def get_cached(self, key, max_age=60):
        """Get from memory cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).seconds < max_age:
                return data
        return None
    
    def set_cached(self, key, data):
        """Store in memory cache"""
        self._cache[key] = (data, datetime.now())

# Global Redis manager instance
redis_manager = RedisManager()

# ============================================================
# SECTION 3: AUTHENTICATION SYSTEM
# ============================================================
def check_auth():
    """Check if user is authenticated, redirect to login if not"""
    if not st.session_state.get('authenticated', False):
        return False
    return True

def login_form():
    """Display login form in sidebar"""
    with st.sidebar:
        st.title("🔐 Admin Login")
        
        # Get password from Redis or use default
        r = redis_manager.conn
        if not r:
            stored_pwd = "Breezersrock!"  # Fallback
        else:
            stored_pwd = r.get("admin_password") or "Breezersrock!"
        
        pwd = st.text_input("Enter Admin Password", type="password", key="login_pwd")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                if pwd == stored_pwd:
                    st.session_state.authenticated = True
                    st.session_state.login_time = datetime.now()
                    st.rerun()
                else:
                    st.error("Incorrect password")
        with col2:
            if st.button("Clear", use_container_width=True):
                st.rerun()
        
        return False

# ============================================================
# SECTION 4: SMART DATA LOADERS (With Caching)
# ============================================================
@st.cache_data(ttl=300)  # 5 minutes for members (rarely changes)
def load_members_cached():
    """Load all members with Redis caching"""
    r = redis_manager.conn
    if not r:
        return []
    
    # Try memory cache first
    cached = redis_manager.get_cached("members", max_age=120)
    if cached:
        return cached
    
    # Load from Redis
    raw_members = r.lrange("members", 0, -1)
    members = [json.loads(m) for m in raw_members]
    
    # Cache in memory
    redis_manager.set_cached("members", members)
    return members

@st.cache_data(ttl=60)  # 1 minute for race results
def load_race_results_cached():
    """Load all race results with caching"""
    r = redis_manager.conn
    if not r:
        return []
    
    cached = redis_manager.get_cached("race_results", max_age=30)
    if cached:
        return cached
    
    raw_results = r.lrange("race_results", 0, -1)
    results = [json.loads(r) for r in raw_results]
    
    redis_manager.set_cached("race_results", results)
    return results

def get_member_dict():
    """Get members as dictionary for quick lookups"""
    members = load_members_cached()
    return {m['name']: m for m in members}

# ============================================================
# SECTION 5: UTILITY FUNCTIONS (From app.py)
# ============================================================
def format_time_string(t_str):
    """Convert time string to HH:MM:SS format"""
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
    """Convert time string to total seconds"""
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
    """Calculate age category based on app.py logic"""
    try:
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        race_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        
        # Get mode from Redis or default
        r = redis_manager.conn
        if r:
            stored_mode = r.get("age_mode") or "5 Year"
            if "5" in stored_mode:
                mode = "5Y"
            else:
                mode = "10Y"
        
        # Apply logic from app.py
        threshold = 35 if mode == "5Y" else 40
        step = 5 if mode == "5Y" else 10
        
        if age < threshold: 
            return "Senior"
        
        base_age = (age // step) * step
        return f"V{base_age}"
    except Exception as e:
        return "Unknown"

# ============================================================
# SECTION 6: SIDEBAR SETUP
# ============================================================
def render_sidebar():
    """Render the sidebar with logo, auth, and navigation"""
    with st.sidebar:
        # Club Logo
        r = redis_manager.conn
        logo_url = None
        if r:
            logo_url = r.get("club_logo_url") or r.get("logo_url")
        
        if logo_url and logo_url.startswith("http"):
            st.image(logo_url, width=150)
        
        # Authentication
        if not check_auth():
            if login_form():
                return
        
        # User is authenticated from here
        st.success(f"✅ Authenticated")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            redis_manager.clear_cache()  # Clear all caches on logout
            st.rerun()
        
        st.divider()
        
        # Navigation
        st.subheader("📋 Navigation")
        
        # Define tabs
        tabs = [
            ("🏆 Leaderboard", "leaderboard"),
            ("👥 Members", "members"),
            ("📥 PB Submissions", "submissions"),
            ("📋 Race Log", "racelog"),
            ("🏅 Championship", "championship"),
            ("⚙️ System", "system")
        ]
        
        # Current tab from query params or session
        current_tab = st.session_state.get("current_tab", "leaderboard")
        
        for tab_name, tab_key in tabs:
            if st.button(
                tab_name, 
                use_container_width=True,
                type="primary" if current_tab == tab_key else "secondary",
                key=f"nav_{tab_key}"
            ):
                st.session_state.current_tab = tab_key
                st.rerun()
        
        st.divider()
        
        # Quick stats
        st.subheader("📊 Quick Stats")
        members = load_members_cached()
        results = load_race_results_cached()
        
        active_members = len([m for m in members if m.get('status', 'Active') == 'Active'])
        total_races = len(results)
        
        col1, col2 = st.columns(2)
        col1.metric("Active Members", active_members)
        col2.metric("Race Results", total_races)
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            redis_manager.clear_cache()
            st.cache_data.clear()
            st.success("Cache cleared!")
            st.rerun()

# ============================================================
# SECTION 7: MAIN APP LAYOUT
# ============================================================
def main():
    """Main application controller"""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "leaderboard"
    
    # Render sidebar (includes auth check)
    render_sidebar()
    
    # If not authenticated, stop here (login form is in sidebar)
    if not check_auth():
        st.warning("Please login in the sidebar to continue")
        return
    
    # Main content area based on selected tab
    current_tab = st.session_state.current_tab
    
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
# SECTION 8: TAB 1 - LEADERBOARD (First Implementation)
# ============================================================
def render_leaderboard_tab():
    """Render the leaderboard tab with optimizations"""
    
    st.title("🏆 Personal Best Leaderboard")
    
    # Load data with progress indicator
    with st.spinner("Loading leaderboard data..."):
        results = load_race_results_cached()
        members = load_members_cached()
    
    if not results:
        st.info("No race results found in the database.")
        return
    
    # Convert to DataFrame for fast operations
    df = pd.DataFrame(results)
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    
    # Get active member names
    active_members = [m['name'] for m in members if m.get('status', 'Active') == 'Active']
    
    # Year filter
    years = ["All-Time"] + sorted(
        [str(y) for y in df['race_date_dt'].dt.year.unique()], 
        reverse=True
    )
    
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_year = st.selectbox("Select Season:", years, key="year_filter")
    
    # Filter by year if needed
    display_df = df.copy()
    if selected_year != "All-Time":
        display_df = display_df[display_df['race_date_dt'].dt.year == int(selected_year)]
    
    # Add category column
    r = redis_manager.conn
    age_mode = "10Y"
    if r:
        mode_setting = r.get("age_mode") or "5 Year"
        age_mode = "5Y" if "5" in mode_setting else "10Y"
    
    display_df['Category'] = display_df.apply(
        lambda x: get_category(x['dob'], x['race_date'], age_mode), 
        axis=1
    )
    
    # Display by distance
    distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]
    
    for distance in distances:
        st.markdown(f"### 🏁 {distance}")
        
        col_male, col_female = st.columns(2)
        
        # Male leaders
        with col_male:
            st.markdown(
                '<div style="background:#003366; color:white; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">MALE</div>',
                unsafe_allow_html=True
            )
            
            male_results = display_df[
                (display_df['distance'] == distance) & 
                (display_df['gender'] == 'Male')
            ]
            
            if not male_results.empty:
                # Get fastest per category
                leaders = male_results.sort_values('time_seconds').groupby('Category').head(1)
                
                for _, row in leaders.sort_values('Category').iterrows():
                    is_active = row['name'] in active_members
                    opacity = "1.0" if is_active else "0.5"
                    
                    html = f'''
                    <div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                        <div>
                            <span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">
                                {row['Category']}
                            </span>
                            <b style="color:#003366;">{row['name']}</b><br>
                            <small style="color:#666;">{row['location']} ({row['race_date']})</small>
                        </div>
                        <div style="font-weight:bold; color:#003366; font-size:1.1em;">
                            {row['time_display']}
                        </div>
                    </div>
                    '''
                    st.markdown(html, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; color:#666;">No records</div>',
                    unsafe_allow_html=True
                )
        
        # Female leaders
        with col_female:
            st.markdown(
                '<div style="background:#FFD700; color:#003366; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">FEMALE</div>',
                unsafe_allow_html=True
            )
            
            female_results = display_df[
                (display_df['distance'] == distance) & 
                (display_df['gender'] == 'Female')
            ]
            
            if not female_results.empty:
                leaders = female_results.sort_values('time_seconds').groupby('Category').head(1)
                
                for _, row in leaders.sort_values('Category').iterrows():
                    is_active = row['name'] in active_members
                    opacity = "1.0" if is_active else "0.5"
                    
                    html = f'''
                    <div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                        <div>
                            <span style="background:#003366; color:#FFD700; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">
                                {row['Category']}
                            </span>
                            <b style="color:#003366;">{row['name']}</b><br>
                            <small style="color:#666;">{row['location']} ({row['race_date']})</small>
                        </div>
                        <div style="font-weight:bold; color:#003366; font-size:1.1em;">
                            {row['time_display']}
                        </div>
                    </div>
                    '''
                    st.markdown(html, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; color:#666;">No records</div>',
                    unsafe_allow_html=True
                )
        
        st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# RUN THE APP
# ============================================================
if __name__ == "__main__":
    main()
