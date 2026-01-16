import streamlit as st
import json
from helpers import get_redis

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("📥 Review Standard PBs")

pending = r.lrange("pending_results", 0, -1)

if not pending:
    st.success("No pending standard PBs.")
else:
    for i, item in enumerate(pending):
        data = json.loads(item)
        with st.container(border=True):
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.subheader(f"{data['name']} - {data['distance']}")
                st.write(f"Time: **{data['time_display']}** | Race: {data['location']} ({data['race_date']})")
                if data.get('comment'):
                    st.caption(f"Note: {data['comment']}")
            
            with cols[1]:
                if st.button("✅ Approve", key=f"app_{i}"):
                    # Move to finalized list
                    r.rpush("race_results", item)
                    # Remove from pending
                    r.lrem("pending_results", 1, item)
                    st.rerun()
            
            with cols[2]:
                if st.button("🗑️ Reject", key=f"rej_{i}"):
                    r.lrem("pending_results", 1, item)
                    st.rerun()
