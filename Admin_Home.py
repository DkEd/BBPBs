import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings, get_category

st.set_page_config(page_title="BBPB - Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

# --- SIDEBAR: LOGIN & TOGGLES (Restored) ---
st.sidebar.title("🔐 Admin Access")
if not st.session_state.get('authenticated'):
    pwd = st.sidebar.text_input("Enter Password", type="password")
    if pwd == settings.get('admin_password', 'admin'):
        st.session_state['authenticated'] = True
        st.rerun()
else:
    st.sidebar.success("Authenticated")
    if st.sidebar.button("Logout"):
        st.session_state['authenticated'] = False
        st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Display Toggles")
show_details = st.sidebar.toggle("Show Detailed Stats", value=True)
show_active_only = st.sidebar.toggle("Active Members Only", value=False)

# --- MAIN PAGE: LEADERBOARD (Restored Blue/Gold Layout) ---
st.title("🏃 Bramley Breezers Results")

# Pull from Cache for speed
cache_pb = r.get("cached_pb_leaderboard")
if cache_pb:
    df = pd.read_json(cache_pb)
    
    # Restored BBPB.py filtering logic
    sel_year = st.selectbox("Filter Season", ["All-Time", "2026", "2025", "2024"])
    if sel_year != "All-Time":
        df = df[df['race_date'].astype(str).str.contains(sel_year)]

    distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]
    genders = ["Male", "Female"]

    for dist in distances:
        st.subheader(f"🏆 {dist} Leaderboard")
        cols = st.columns(2)
        for i, gender in enumerate(genders):
            with cols[i]:
                color = "#1E90FF" if gender == "Male" else "#FFD700"
                st.markdown(f"<h4 style='color:{color}'>{gender}</h4>", unsafe_allow_html=True)
                
                sub_df = df[(df['distance'] == dist) & (df['gender'] == gender)]
                # Category logic
                sub_df['Category'] = sub_df.apply(lambda x: get_category(x['dob'], x['race_date'], settings['age_mode']), axis=1)
                
                # Best per category
                leaders = sub_df.sort_values("time_seconds").groupby("Category").first().reset_index()
                
                for _, row in leaders.iterrows():
                    st.markdown(f"""
                    <div style="border-left: 5px solid {color}; padding:10px; margin-bottom:5px; background-color:rgba(255,255,255,0.1); border-radius:5px;">
                        <strong>{row['Category']}:</strong> {row['name']} - {row['time_display']}<br>
                        <small>{row['location']} ({row['race_date']})</small>
                    </div>
                    """, unsafe_allow_html=True)
else:
    st.info("Leaderboard cache is empty. Please refresh in System settings.")
