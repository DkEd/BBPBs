import streamlit as st
import pandas as pd
import json
from helpers import get_redis, get_club_settings

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

settings = get_club_settings()

st.header("⚙️ System Tools")

# Age Mode
mode = settings['age_mode']
new_mode = st.radio("Age Mode", ["10Y", "5Y"], index=0 if mode=="10Y" else 1)
if st.button("Save Age Mode"): 
    r.set("age_mode", new_mode)
    st.success("Age Mode Updated")

st.divider()

# Logo URL
new_logo = st.text_input("Logo URL", value=settings['logo_url'])
if st.button("Update Logo"):
    r.set("logo_url", new_logo)
    st.success("Logo Updated")

st.divider()

# Exports
if st.button("Generate PB Backup"):
    df = pd.DataFrame([json.loads(x) for x in r.lrange("race_results", 0, -1)])
    st.download_button("Download CSV", df.to_csv(index=False), "pb_backup.csv")

st.divider()

# Password
new_pwd = st.text_input("New Admin Password", type="password")
if st.button("Update Password"): 
    r.set("admin_password", new_pwd)
    st.success("Updated")

# Championship Visibility
st.divider()
show_champ = st.checkbox("Show Championship Tab on Public Site", value=(settings['show_champ_tab'] == "True"))
if st.button("Update Visibility"):
    r.set("show_champ_tab", str(show_champ))
    st.success("Visibility Updated")
