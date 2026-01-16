import streamlit as st
import json
from helpers import get_redis, format_time_string, time_to_seconds

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("📋 Master Record Log")
results = r.lrange("race_results", 0, -1)
for idx, val in enumerate(results):
    item = json.loads(val)
    with st.container(border=True):
        c1, c2 = st.columns([4,1])
        c1.write(f"**{item['name']}** - {item['distance']} - {item['time_display']} ({item['race_date']})")
        if c2.button("🗑️ Delete", key=f"del_{idx}"):
            r.lset("race_results", idx, "WIPE"); r.lrem("race_results", 1, "WIPE"); st.rerun()
