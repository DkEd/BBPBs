import streamlit as st
import json
from helpers import get_redis, rebuild_leaderboard_cache

r = get_redis()
st.header("📥 Pending PB Submissions")

if not st.session_state.get('authenticated'): st.stop()

pending = r.lrange("pending_results", 0, -1)
if not pending:
    st.info("No pending PB results.")
else:
    for i, p_raw in enumerate(pending):
        p = json.loads(p_raw)
        with st.expander(f"{p['name']} - {p['distance']}"):
            if st.button(f"Approve {i}", key=f"app_{i}"):
                r.rpush("race_results", p_raw)
                r.lset("pending_results", i, "WIPE")
                r.lrem("pending_results", 1, "WIPE")
                rebuild_leaderboard_cache(r) # Trigger
                st.rerun()
            if st.button(f"Reject {i}", key=f"rej_{i}"):
                r.lset("pending_results", i, "WIPE")
                r.lrem("pending_results", 1, "WIPE")
                st.rerun()
