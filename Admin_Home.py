import streamlit as st
import pandas as pd
import json
import os
from helpers import get_redis, get_club_settings, get_category

st.set_page_config(page_title="BBPB Admin - Home", layout="wide")

r = get_redis()
settings = get_club_settings()
# Hardcoded as per your requirement
age_mode = "Age on Day"

if settings.get('logo_url'):
    st.sidebar.image(settings['logo_url'], width=150)

st.title("🔐 BBPB Admin Portal")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login_form"):
        password = st.text_input("Admin Password", type="password")
        if st.form_submit_button("Login"):
            if password == os.environ.get("ADMIN_PASSWORD", "admin123"):
                st.session_state.authenticated = True
                st.success("Authenticated!")
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

st.subheader("Current Leaderboard Status")
raw_res = r.lrange("race_results", 0, -1)
if raw_res:
    res_list = [json.loads(x) for x in raw_res]
    disp_df = pd.DataFrame(res_list)
    
    # The line that was causing the error:
    disp_df['Category'] = disp_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)
    
    st.dataframe(disp_df[['name', 'distance', 'time_display', 'Category', 'location']], use_container_width=True)
else:
    st.info("No results in database.")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("Pending PBs", r.llen("pending_results"))
with col2:
    st.metric("Pending Champ Entries", r.llen("champ_pending"))
