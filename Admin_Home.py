import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_category

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()

# --- AUTHENTICATION PERSISTENCE ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def local_get_logo():
    stored = r.get("club_logo_url")
    return stored if (stored and str(stored).startswith("http")) else "https://cdn-icons-png.flaticon.com/512/55/55281.png"

with st.sidebar:
    st.image(local_get_logo(), width=150)
    if not st.session_state['authenticated']:
        admin_pwd = r.get("admin_password") or "admin123"
        pwd_input = st.text_input("Admin Password", type="password")
        if pwd_input == admin_pwd:
            st.session_state['authenticated'] = True
            st.rerun()
    else:
        st.success("Admin Authenticated ✅")
        if st.button("Logout"):
            st.session_state['authenticated'] = False
            st.rerun()
        st.divider()
        st.metric("Total PBs", r.llen("race_results"))
        st.metric("Pending PBs", r.llen("pending_results"))

# --- SIDEBAR PAGE HIDER ---
if not st.session_state['authenticated']:
    st.markdown("<style>[data-testid='stSidebarNav'] ul li:nth-child(n+2) { display: none; }</style>", unsafe_allow_html=True)
    st.warning("Please enter password in sidebar to access management tools.")

st.title("🛡️ BBPB-Admin Dashboard")

raw_res = r.lrange("race_results", 0, -1)
df = pd.DataFrame([json.loads(res) for res in raw_res]) if raw_res else pd.DataFrame()

tabs = st.tabs(["🏆 PB Leaderboard", "🏅 Championship Standings", "🔍 Runner History Lookup"])

with tabs[0]: # Leaderboard Match
    if not df.empty:
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        raw_mem = r.lrange("members", 0, -1)
        members_data = [json.loads(m) for m in raw_mem]
        active_names = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']
        
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("Season:", years)
        disp_df = df.copy()
        if sel_year != "All-Time": disp_df = disp_df[disp_df['race_date_dt'].dt.year == int(sel_year)]
        
        age_mode = r.get("age_mode") or "10Y"
        disp_df['Category'] = disp_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

        for d in ["5k", "10k", "10 Mile", "HM", "Marathon"]:
            st.markdown(f"### 🏁 {d}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg, tc = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                    st.markdown(f'<div style="background:{bg}; color:{tc}; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    sub = disp_df[(disp_df['distance'] == d) & (disp_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, row in leaders.sort_values('Category').iterrows():
                            op = "1.0" if row['name'] in active_names else "0.5"
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{op};"><div><span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">{row['Category']}</span><b style="color:black;">{row['name']}</b><br><small style="color:#666;">{row['location']} • {row['race_date']}</small></div><div style="font-weight:bold; color:#003366;">{row['time_display']}</div></div>''', unsafe_allow_html=True)

with tabs[1]: # Championship Standings
    final_raw = r.lrange("champ_results_final", 0, -1)
    if final_raw:
        c_df = pd.DataFrame([json.loads(x) for x in final_raw])
        c_df = c_df.sort_values(['name', 'points'], ascending=[True, False])
        c_df['rank'] = c_df.groupby('name').cumcount() + 1
        league = c_df[c_df['rank'] <= 6].groupby('name')['points'].sum().reset_index()
        counts = c_df.groupby('name').size().reset_index(name='Races')
        league = league.merge(counts, on='name')
        st.dataframe(league.sort_values('points', ascending=False), use_container_width=True, hide_index=True)
    else: st.info("No points approved yet.")

with tabs[2]: # Runner History Lookup
    if not df.empty:
        search_n = st.selectbox("Select Runner to View PB History", [""] + sorted(df['name'].unique().tolist()))
        if search_n:
            st.subheader(f"History for {search_n}")
            st.dataframe(df[df['name'] == search_n].sort_values('race_date', ascending=False), use_container_width=True, hide_index=True)
