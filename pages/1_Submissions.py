import streamlit as st
import json
from helpers import get_redis, rebuild_leaderboard_cache

st.set_page_config(page_title="PB Submissions", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.warning("Please login.")
    st.stop()

st.header("📥 Pending PB Submissions")
pending = r.lrange("pending_results", 0, -1)

if not pending:
    st.info("No pending PBs.")
else:
    for i, p_raw in enumerate(pending):
        p = json.loads(p_raw)
        with st.expander(f"{p['name']} - {p['distance']} ({p['time_display']})"):
            if st.button("✅ Approve", key=f"ap_{i}"):
                r.rpush("race_results", p_raw)
                r.lset("pending_results", i, "WIPE")
                r.lrem("pending_results", 1, "WIPE")
                rebuild_leaderboard_cache(r)
                st.rerun()
            if st.button("❌ Reject", key=f"rj_{i}"):
                r.lset("pending_results", i, "WIPE")
                r.lrem("pending_results", 1, "WIPE")
                st.rerun()
