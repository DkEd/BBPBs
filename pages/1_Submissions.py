import streamlit as st
import json
from helpers import get_redis, format_time_string, time_to_seconds

# Page Config
st.set_page_config(page_title="Submissions", layout="wide")

r = get_redis()

# --- PERSISTENT URL-BASED AUTHENTICATION ---
if st.query_params.get("access") == "granted":
    st.session_state['authenticated'] = True

if not st.session_state.get('authenticated'):
    st.warning("Please login on the Home page to access this section.")
    st.stop()

st.header("📥 Manual Entry & Approvals")
raw_mem = r.lrange("members", 0, -1)
members_data = [json.loads(m) for m in raw_mem]

with st.form("direct_add"):
    c1, c2, c3 = st.columns(3)
    n = c1.selectbox("Member", sorted([m['name'] for m in members_data]))
    d = c2.selectbox("Dist", ["5k", "10k", "10 Mile", "HM", "Marathon"])
    t = c3.text_input("Time (HH:MM:SS)")
    loc = st.text_input("Race Name")
    rd = st.date_input("Date")
    if st.form_submit_button("Add Result"):
        m = next(x for x in members_data if x['name'] == n)
        entry = {"name": n, "gender": m['gender'], "dob": m['dob'], "distance": d, "time_seconds": time_to_seconds(t), "time_display": format_time_string(t), "location": loc, "race_date": str(rd)}
        r.rpush("race_results", json.dumps(entry)); st.success("Added"); st.rerun()

st.divider()
st.subheader("Pending PB Approvals")
pending = r.lrange("pending_results", 0, -1)
for i, p_json in enumerate(pending):
    p = json.loads(p_json)
    with st.expander(f"Review: {p['name']} - {p['distance']}"):
        match = next((m for m in members_data if m['name'] == p['name']), None)
        if match and st.button("✅ Approve", key=f"app_{i}"):
            entry = {"name": p['name'], "gender": match['gender'], "dob": match['dob'], "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']), "time_display": format_time_string(p['time_display']), "location": p['location'], "race_date": p['race_date']}
            r.rpush("race_results", json.dumps(entry)); r.lrem("pending_results", 1, p_json); st.rerun()
        if st.button("❌ Reject", key=f"rej_{i}"):
            r.lrem("pending_results", 1, p_json); st.rerun()
