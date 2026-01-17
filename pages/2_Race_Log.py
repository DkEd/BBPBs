import streamlit as st
import json
import pandas as pd
from helpers import get_redis, rebuild_leaderboard_cache

st.set_page_config(page_title="Race Log", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.warning("Please login on the Home page.")
    st.stop()

st.header("📑 Master Race Log")
st.write("View, Edit, or Delete any PB entry in the database.")

raw = r.lrange("race_results", 0, -1)

if raw:
    # Convert Redis data to DataFrame for display
    data = [json.loads(x) for x in raw]
    df = pd.DataFrame(data)
    
    # Show the log
    st.dataframe(df, use_container_width=True)
    
    col1, col2 = st.columns(2)

    with col1:
        with st.expander("📝 Edit an Entry"):
            edit_idx = st.number_input("Enter Index to Edit", 0, len(df)-1, 0, key="edit_idx")
            target = data[edit_idx]
            
            with st.form("edit_form"):
                new_name = st.text_input("Name", target.get('name'))
                new_dist = st.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"], 
                                        index=["5k", "10k", "10 Mile", "HM", "Marathon"].index(target.get('distance', '5k')))
                new_loc = st.text_input("Location", target.get('location'))
                new_date = st.text_input("Date (YYYY-MM-DD)", target.get('race_date'))
                new_time = st.text_input("Time (MM:SS or HH:MM:SS)", target.get('time_display'))
                
                if st.form_submit_button("Save Changes"):
                    # Calculate new seconds
                    parts = list(map(int, new_time.split(':')))
                    new_sec = (parts[0] * 60 + parts[1]) if len(parts) == 2 else (parts[0]*3600 + parts[1]*60 + parts[2])
                    
                    updated_entry = {
                        **target,
                        "name": new_name,
                        "distance": new_dist,
                        "location": new_loc,
                        "race_date": new_date,
                        "time_display": new_time,
                        "time_seconds": new_sec
                    }
                    
                    # Update Redis: Set at index, then rebuild cache
                    r.lset("race_results", int(edit_idx), json.dumps(updated_entry))
                    rebuild_leaderboard_cache(r)
                    st.success("Entry updated and cache rebuilt!")
                    st.rerun()

    with col2:
        with st.expander("🗑️ Delete an Entry"):
            del_idx = st.number_input("Enter Index to Delete", 0, len(df)-1, 0, key="del_idx")
            st.warning(f"Deleting entry for {df.iloc[del_idx]['name']} at {df.iloc[del_idx]['location']}")
            
            if st.button("Confirm Delete"):
                # Standard LREM pattern
                r.lset("race_results", int(del_idx), "WIPE")
                r.lrem("race_results", 1, "WIPE")
                rebuild_leaderboard_cache(r)
                st.success("Entry deleted!")
                st.rerun()
else:
    st.info("No race results found in the database.")
