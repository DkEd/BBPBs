import streamlit as st
import json
import pandas as pd
from helpers import get_redis, get_club_settings, rebuild_leaderboard_cache

r = get_redis()
settings = get_club_settings()
st.header("⚙️ System Management")
t = st.tabs(["Settings", "Bulk Upload", "Backup"])

with t[0]:
    with st.form("set"):
        mode = st.selectbox("Age Mode", ["5 Year", "10 Year"], index=0 if settings['age_mode']=="5 Year" else 1)
        logo = st.text_input("Logo URL", settings['logo_url'])
        if st.form_submit_button("Save"):
            r.set("club_settings", json.dumps({"age_mode": mode, "logo_url": logo, "admin_password": settings['admin_password']}))
            rebuild_leaderboard_cache(r)
            st.success("Updated")

with t[1]: # Bulk Upload
    f = st.file_uploader("Upload CSV", type="csv")
    if f and st.button("Process Members"):
        df = pd.read_csv(f)
        for _, row in df.iterrows():
            r.rpush("members", json.dumps(row.to_dict()))
        st.success("Imported")

with t[2]: # Backup
    raw_r = r.lrange("race_results", 0, -1)
    if raw_r:
        df_r = pd.DataFrame([json.loads(x) for x in raw_r])
        st.download_button("Download Races", df_r.to_csv(index=False), "races.csv")
