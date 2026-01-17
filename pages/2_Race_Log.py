import streamlit as st
import json
import pandas as pd
from helpers import get_redis, rebuild_leaderboard_cache

st.set_page_config(page_title="Race Log", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.stop()

st.header("📑 Master Race Log")
raw = r.lrange("race_results", 0, -1)

if raw:
    df = pd.DataFrame([json.loads(x) for x in raw])
    st.dataframe(df)
    
    with st.expander("Danger Zone"):
        idx = st.number_input("Index to delete", 0, len(df)-1, 0)
        if st.button("Delete Entry"):
            r.lset("race_results", int(idx), "WIPE")
            r.lrem("race_results", 1, "WIPE")
            rebuild_leaderboard_cache(r)
            st.rerun()
