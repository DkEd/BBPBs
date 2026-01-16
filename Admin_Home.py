import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings, get_category

st.set_page_config(page_title="BBPB Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

if settings['logo_url']:
    st.sidebar.image(settings['logo_url'], width=150)

st.title("🏃 Bramley Breezers Results & Championship")

# --- 1. PUBLIC VIEW LEADERBOARD (Restored exact app.py layout) ---
raw_res = r.lrange("race_results", 0, -1)
raw_mem = r.lrange("members", 0, -1)
members_data = [json.loads(m) for m in raw_mem]
active_names = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']

if raw_res:
    df = pd.DataFrame([json.loads(res) for res in raw_res])
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    
    years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
    sel_year = st.selectbox("View Season:", years, key="admin_year_filter")
    
    disp_df = df.copy()
    if sel_year != "All-Time":
        disp_df = disp_df[disp_df['race_date_dt'].dt.year == int(sel_year)]
        
    age_mode = settings['age_mode']
    disp_df['Category'] = disp_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

    for d in ["5k", "10k", "10 Mile", "HM", "Marathon"]:
        st.markdown(f"### 🏁 {d}")
        m_col, f_col = st.columns(2)
        
        for gen, col in [("Male", m_col), ("Female", f_col)]:
            with col:
                # Restoration of your specific color scheme
                bg, tc = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                st.markdown(f'''
                    <div style="background:{bg}; color:{tc}; padding:8px; border-radius:8px 8px 0 0; 
                    text-align:center; font-weight:bold; border:2px solid #003366;">
                        {gen.upper()}
                    </div>''', unsafe_allow_html=True)
                
                sub = disp_df[(disp_df['distance'] == d) & (disp_df['gender'] == gen)]
                if not sub.empty:
                    # Logic: Fastest per Category
                    leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                    for _, row in leaders.sort_values('Category').iterrows():
                        # Restoration of the 50% opacity for members who have left
                        opacity = "1.0" if row['name'] in active_names else "0.5"
                        st.markdown(f'''
                            <div style="border:2px solid #003366; border-top:none; padding:10px; background:white; 
                                        margin-bottom:-2px; display:flex; justify-content:space-between; 
                                        align-items:center; opacity:{opacity};">
                                <div>
                                    <span style="background:#FFD700; color:#003366; padding:2px 5px; 
                                          border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">
                                        {row['Category']}
                                    </span>
                                    <b>{row['name']}</b><br>
                                    <small>{row['location']} ({row['race_date']})</small>
                                </div>
                                <div style="font-weight:bold; color:#003366; font-size:1.1em;">
                                    {row['time_display']}
                                </div>
                            </div>''', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; color:#666;">No records</div>', unsafe_allow_html=True)

else:
    st.info("No records found in the database yet.")

st.divider()

# --- 2. ADMIN SECTION (Password Protected & Persistent) ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

with st.sidebar:
    st.header("🛡️ Admin Access")
    if not st.session_state['authenticated']:
        pwd = st.text_input("Enter Admin Password", type="password")
        if st.button("Login"):
            if pwd == settings['admin_password']:
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error("Incorrect Password")
    else:
        st.success("🔓 Authenticated")
        # Quick Metrics for Admin
        st.metric("Pending PBs", r.llen("pending_results"))
        st.metric("Champ Pending", r.llen("champ_pending"))
        if st.button("Logout"):
            st.session_state['authenticated'] = False
            st.rerun()

if st.session_state['authenticated']:
    st.success("Admin mode active. Use the sidebar to navigate to management pages.")
