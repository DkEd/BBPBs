import streamlit as st
from helpers import get_redis

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("⚙️ System Settings")

# --- 1. DISPLAY SETTINGS ---
st.subheader("Public Display Options")
c1, c2 = st.columns(2)

with c1:
    # PB Leaderboard Toggle
    current_mode = r.get("age_mode") or "10Y"
    new_mode = st.radio("PB Leaderboard Categories", ["10Y", "5Y"], index=0 if current_mode=="10Y" else 1)
    if new_mode != current_mode:
        r.set("age_mode", new_mode)
        st.toast(f"Saved: Leaderboard now uses {new_mode} bands.")

with c2:
    # Championship Visibility
    curr_vis = r.get("show_champ_tab") == "True"
    new_vis = st.toggle("Show Championship Tab on Public Site?", value=curr_vis)
    if new_vis != curr_vis:
        r.set("show_champ_tab", str(new_vis))
        st.toast("Visibility Updated.")

st.divider()

# --- 2. LOGO ---
st.subheader("Club Branding")
curr_logo = r.get("club_logo_url") or ""
new_logo = st.text_input("Club Logo URL", value=curr_logo)
if st.button("Save Logo"):
    r.set("club_logo_url", new_logo)
    st.success("Logo updated.")

st.divider()

# --- 3. DATA EXPORT ---
st.subheader("Backup Data")
st.write("Download your data as CSV files.")

# Helper to make CSV
def make_csv(key):
    data = r.lrange(key, 0, -1)
    if not data: return None
    import pandas as pd
    import json
    return pd.DataFrame([json.loads(x) for x in data]).to_csv(index=False).encode('utf-8')

cols = st.columns(3)
with cols[0]:
    csv = make_csv("members")
    if csv: st.download_button("Download Members", csv, "members.csv", "text/csv")
with cols[1]:
    csv = make_csv("race_results")
    if csv: st.download_button("Download Standard PBs", csv, "pbs.csv", "text/csv")
with cols[2]:
    csv = make_csv("champ_results_final")
    if csv: st.download_button("Download Champ Points", csv, "champ_points.csv", "text/csv")
