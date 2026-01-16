import streamlit as st
import json
import pandas as pd
from helpers import get_redis

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.title("📖 Standard PB Race Log")

raw_results = r.lrange("race_results", 0, -1)

if raw_results:
    # Convert to DF for easy viewing
    data_list = []
    for i, res in enumerate(raw_results):
        d = json.loads(res)
        d['redis_index'] = i
        data_list.append(d)
        
    df = pd.DataFrame(data_list)
    
    st.dataframe(
        df[['race_date', 'name', 'distance', 'time_display', 'location']].sort_values('race_date', ascending=False),
        use_container_width=True, hide_index=True
    )
    
    st.divider()
    st.subheader("Delete Record")
    
    # Create a list of options for the dropdown
    opts = df.sort_values('race_date', ascending=False).to_dict('records')
    
    sel = st.selectbox("Select Record to Delete", opts, format_func=lambda x: f"{x['name']} - {x['distance']} ({x['time_display']})")
    
    if st.button("🗑️ Permanently Delete"):
        # Mark the specific index as deleted then clean up
        r.lset("race_results", sel['redis_index'], "DELETED")
        r.lrem("race_results", 1, "DELETED")
        st.success("Deleted.")
        st.rerun()
else:
    st.info("No approved results yet.")
