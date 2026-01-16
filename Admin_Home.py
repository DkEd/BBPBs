import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_category

st.set_page_config(page_title="AutoKudos Admin", layout="wide")
r = get_redis()

# --- LOGO & AUTH ---
def local_get_logo():
    stored = r.get("club_logo_url")
    return stored if (stored and str(stored).startswith("http")) else "https://cdn-icons-png.flaticon.com/512/55/55281.png"

with st.sidebar:
    st.image(local_get_logo(), width=150)
    admin_pwd = r.get("admin_password") or "admin123"
    pwd_input = st.text_input("Admin Password", type="password")
    is_auth = (pwd_input == admin_pwd)
    st.session_state['authenticated'] = is_auth
    
    if is_auth:
        st.success("Admin Authenticated")
        st.divider()
        st.metric("Total Records", r.llen("race_results"))
        st.metric("Total Members", r.llen("members"))
        st.metric("Pending PBs", r.llen("pending_results"))

# --- SIDEBAR PAGE LOCK ---
if not st.session_state['authenticated']:
    st.markdown("""
        <style>
        [data-testid="stSidebarNav"] ul li:nth-child(n+2) { display: none; }
        </style>
    """, unsafe_allow_html=True)

# --- MAIN UI ---
st.title("🏃 Bramley Breezers Leaderboard (Admin View)")

raw_res = r.lrange("race_results", 0, -1)
raw_mem = r.lrange("members", 0, -1)
members_data = [json.loads(m) for m in raw_mem]
active_names = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']

if raw_res:
    df = pd.DataFrame([json.loads(res) for res in raw_res])
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    
    # Filter by Season (Matches BBPB)
    years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
    sel_year = st.selectbox("Select Season:", years)
    
    disp_df = df.copy()
    if sel_year != "All-Time":
        disp_df = disp_df[disp_df['race_date_dt'].dt.year == int(sel_year)]
    
    age_mode = r.get("age_mode") or "10Y"
    disp_df['Category'] = disp_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

    # Leaderboard Display (EXACT MATCH TO BBPB)
    for d in ["5k", "10k", "10 Mile", "HM", "Marathon"]:
        st.markdown(f"### 🏁 {d}")
        m_col, f_col = st.columns(2)
        for gen, col in [("Male", m_col), ("Female", f_col)]:
            with col:
                # Same Branding Colors
                bg, tc = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                st.markdown(f'<div style="background:{bg}; color:{tc}; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                
                sub = disp_df[(disp_df['distance'] == d) & (disp_df['gender'] == gen)]
                if not sub.empty:
                    leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                    for _, row in leaders.sort_values('Category').iterrows():
                        op = "1.0" if row['name'] in active_names else "0.5"
                        # Identical HTML structure to BBPB
                        st.markdown(f'''
                            <div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{op};">
                                <div>
                                    <span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">{row['Category']}</span>
                                    <b style="color: black;">{row['name']}</b><br>
                                    <small style="color: #666;">{row['location']} • {row['race_date']}</small>
                                </div>
                                <div style="font-weight:bold; color:#003366; font-size:1.1em;">{row['time_display']}</div>
                            </div>''', unsafe_allow_html=True)
else:
    st.info("No records found in database.")
