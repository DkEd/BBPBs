import streamlit as st
import json
from helpers import get_redis

st.set_page_config(layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page.")
    st.stop()

st.header("👥 Member Management")

raw_mem = r.lrange("members", 0, -1)
for i, m_json in enumerate(raw_mem):
    m = json.loads(m_json)
    with st.container(border=True):
        c1, c2, c3 = st.columns([3,1,1])
        c1.write(f"**{m['name']}** ({m['gender']}) - {m.get('status', 'Active')}")
        if c2.button("Toggle Status", key=f"tog_{i}"):
            m['status'] = "Left" if m.get('status', 'Active') == "Active" else "Active"
            r.lset("members", i, json.dumps(m))
            st.rerun()
        if c3.button("🗑️ Delete", key=f"del_{i}"):
            r.lset("members", i, "WIPE")
            r.lrem("members", 1, "WIPE")
            st.rerun()
