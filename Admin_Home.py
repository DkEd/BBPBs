import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_category

st.set_page_config(page_title="AutoKudos Admin", layout="wide")
r = get_redis()

# --- LOGO LOGIC (Moved inside to prevent helper errors) ---
def local_get_logo():
    stored = r.get("club_logo_url")
    return stored if (stored and str(stored).startswith("http")) else "https://cdn-icons-png.flaticon.com/512/55/55281.png"

# --- 1. AUTHENTICATION ---
with st.sidebar:
    st.image(local_get_logo(), width=150)
    admin_pwd = r.get("admin_password") or "admin123"
    pwd_input = st.text_input("Admin Password", type="password")
    is_auth = (pwd_input == admin_pwd)
    st.session_state['authenticated'] = is_auth

# --- 2. SIDEBAR LOCK ---
if not st.session_state['authenticated']:
    # Hide all pages in the sidebar except for Home (Leaderboard)
    st.markdown("""
        <style>
        [data-testid="stSidebarNav"] ul li:nth-child(n+2) { display: none; }
        </style>
    """, unsafe_allow_html=True)
    st.title("🏆 Leaderboard View")
else:
    st.title("🛡️ AutoKudos Dashboard")
    st.success("Admin Access Granted")

# --- 3. LEADERBOARD ---
raw_res = r.lrange("race_results", 0, -1)
raw_mem = r.lrange("members", 0, -1)
members_data = [json.loads(m) for m in raw_mem]
active_names = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']

if raw_res:
    df = pd.DataFrame([json.loads(res) for res in raw_res])
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    age_mode = r.get("age_mode") or "10Y"
    df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

    dist = st.selectbox("Select Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"])
    m_col, f_col = st.columns(2)
    for gen, col in [("Male", m_col), ("Female", f_col)]:
        with col:
            bg, tc = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
            st.markdown(f'<div style="background:{bg}; color:{tc}; padding:8px; border-radius:8px 0 0 0; text-align:center; font-weight:bold;">{gen.upper()}</div>', unsafe_allow_html=True)
            
            sub = df[(df['distance'] == dist) & (df['gender'] == gen)]
            if not sub.empty:
                leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                for _, row in leaders.sort_values('Category').iterrows():
                    # Ghosting for inactive members
                    op = "1.0" if row['name'] in active_names else "0.5"
                    st.markdown(f'''<div style="border:1px solid #ddd; padding:10px; opacity:{op}; display:flex; justify-content:space-between;">
                        <span><b>{row['Category']}</b> {row['name']}</span>
                        <span>{row['time_display']}</span>
                    </div>''', unsafe_allow_html=True)
else:
    st.info("No records found in database.")
