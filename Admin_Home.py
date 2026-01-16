import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings, get_category

st.set_page_config(page_title="BBPB Admin", layout="wide")
r = get_redis()
settings = get_club_settings()

# Sidebar Logo
if settings['logo_url']:
    st.sidebar.image(settings['logo_url'], width=150)

st.title("🛡️ AutoKudos Master Admin")

# --- PERSISTENT AUTHENTICATION ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

with st.sidebar:
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
        if st.button("Logout"):
            st.session_state['authenticated'] = False
            st.rerun()

# Stop execution if not logged in
if not st.session_state['authenticated']:
    st.warning("Please login via the sidebar to access Admin controls.")
    st.stop()

# --- TOP METRICS ---
c1, c2, c3 = st.columns(3)
c1.metric("Total Records", r.llen("race_results"))
c2.metric("Total Members", r.llen("members"))
c3.metric("Pending Approvals", r.llen("pending_results"))

st.divider()

# --- ADMIN LEADERBOARD VIEW ---
st.subheader("📊 Current Leaderboard (Admin View)")

raw_res = r.lrange("race_results", 0, -1)
if raw_res:
    df = pd.DataFrame([json.loads(res) for res in raw_res])
    df['race_date_dt'] = pd.to_datetime(df['race_date'])
    
    # Season Filter
    years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
    sel_year = st.selectbox("Filter Season:", years)
    
    disp_df = df.copy()
    if sel_year != "All-Time":
        disp_df = disp_df[disp_df['race_date_dt'].dt.year == int(sel_year)]
    
    age_mode = settings['age_mode']
    disp_df['Category'] = disp_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

    # Display Grids by Distance
    for d in ["5k", "10k", "10 Mile", "HM", "Marathon"]:
        with st.expander(f"🏁 {d} Standings"):
            m_col, f_col = st.columns(2)
            
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    st.write(f"**{gen}**")
                    sub = disp_df[(disp_df['distance'] == d) & (disp_df['gender'] == gen)]
                    if not sub.empty:
                        # Get best time per runner per category
                        leaders = sub.sort_values('time_seconds').groupby(['name', 'Category']).head(1)
                        cat_leaders = leaders.sort_values('time_seconds').groupby('Category').head(1)
                        
                        st.dataframe(
                            cat_leaders.sort_values('time_seconds')[['Category', 'name', 'time_display', 'race_date']],
                            hide_index=True,
                            use_container_width=True
                        )
                    else:
                        st.caption("No records.")
else:
    st.info("No records found in the database yet.")
