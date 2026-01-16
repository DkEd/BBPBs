import streamlit as st
import json
import pandas as pd
from helpers import get_redis

st.set_page_config(page_title="BBPB-Admin", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("👥 Member Management")

tab_add, tab_list = st.tabs(["Add Member", "Member List"])

with tab_add:
    with st.form("add_mem"):
        name = st.text_input("Full Name")
        gender = st.selectbox("Gender", ["Male", "Female"])
        dob = st.date_input("Date of Birth (Crucial for Age Cats)")
        
        if st.form_submit_button("Add Member"):
            if name:
                entry = {"name": name, "gender": gender, "dob": str(dob)}
                r.rpush("members", json.dumps(entry))
                st.success(f"Added {name}!")
            else:
                st.error("Name required.")

with tab_list:
    raw_mem = r.lrange("members", 0, -1)
    if raw_mem:
        df = pd.DataFrame([json.loads(m) for m in raw_mem])
        
        # Simple Delete Tool
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        st.write("To remove a member:")
        to_del = st.selectbox("Select Member", df['name'].unique())
        if st.button("Remove Member"):
            # Find the raw string that matches this name
            for m_str in raw_mem:
                if json.loads(m_str)['name'] == to_del:
                    r.lrem("members", 1, m_str)
                    st.success(f"Removed {to_del}")
                    st.rerun()
                    break
