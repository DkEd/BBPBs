import streamlit as st
import json
from helpers import get_redis

st.set_page_config(page_title="Submissions", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("📥 Pending Standard PBs")
pending = r.lrange("pending_results", 0, -1)

if not pending:
    st.success("No pending results.")
else:
    for i, item in enumerate(pending):
        data = json.loads(item)
        with st.container(border=True):
            st.subheader(f"{data['name']} - {data['distance']}")
            st.write(f"Time: **{data['time_display']}** | Race: {data['location']} ({data['race_date']})")
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve", key=f"app_{i}"):
                r.rpush("race_results", item)
                r.lrem("pending_results", 1, item)
                st.rerun()
            if c2.button("🗑️ Reject", key=f"rej_{i}"):
                r.lrem("pending_results", 1, item)
                st.rerun()
