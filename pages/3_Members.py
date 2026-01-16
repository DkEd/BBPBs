import streamlit as st
import json
from helpers import get_redis

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("👥 Member Management")
raw_mem = r.lrange("members", 0, -1)
for i, m_json in enumerate(raw_mem):
    m = json.loads(m_json)
    with st.container(border=True):
        c1, c2 = st.columns([4,1])
        c1.write(f"**{m['name']}** - {m.get('status', 'Active')}")
        if c2.button("Toggle Status", key=f"tog_{i}"):
            m['status'] = "Left" if m.get('status', 'Active') == "Active" else "Active"
            r.lset("members", i, json.dumps(m)); st.rerun()
