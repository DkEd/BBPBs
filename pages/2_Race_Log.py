import streamlit as st
import json
import pandas as pd
from helpers import get_redis, rebuild_leaderboard_cache

r = get_redis()
st.header("📑 Master Race Log")

raw = r.lrange("race_results", 0, -1)
if raw:
    df = pd.DataFrame([json.loads(x) for x in raw])
    idx = st.number_input("Index to Delete", 0, len(df)-1)
    if st.button("🗑️ Delete Entry"):
        r.lset("race_results", idx, "WIPE")
        r.lrem("race_results", 1, "WIPE")
        rebuild_leaderboard_cache(r) # Trigger
        st.rerun()
    st.dataframe(df)
