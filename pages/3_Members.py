import streamlit as st
import json
import pandas as pd
from helpers import get_redis

st.set_page_config(page_title="Members", layout="wide")
r = get_redis()

if not st.session_state.get('authenticated'):
    st.error("Please login on the Home page."); st.stop()

st.header("👥 Member Management")
t1, t2 = st.tabs(["Add Member", "Manage Members"])

with t1:
    with st.form("add"):
        name = st.text_input("Name")
        gender = st.selectbox("Gender", ["Male", "Female"])
        dob = st.date_input("DOB")
        if st.form_submit_button("Add"):
            r.rpush("members", json.dumps({"name": name, "gender": gender, "dob": str(dob)}))
            st.success("Added.")

with t2:
    mems = r.lrange("members", 0, -1)
    if mems:
        df = pd.DataFrame([json.loads(m) for m in mems])
        st.dataframe(df, use_container_width=True)
        name_del = st.selectbox("Delete Member", df['name'].tolist())
        if st.button("Delete"):
            for m in mems:
                if json.loads(m)['name'] == name_del:
                    r.lrem("members", 1, m)
                    st.success("Removed."); st.rerun()
