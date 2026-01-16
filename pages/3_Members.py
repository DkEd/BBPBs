import streamlit as st
import json
import pandas as pd
from helpers import get_redis

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("👥 Member Management")

tab_list, tab_add, tab_edit = st.tabs(["Member List", "Add New", "Edit/Delete"])

raw_mem = r.lrange("members", 0, -1)
members = [json.loads(m) for m in raw_mem]
df = pd.DataFrame(members)

# --- 1. MEMBER LIST ---
with tab_list:
    if not df.empty:
        st.dataframe(df[['name', 'gender', 'dob', 'status']].sort_values('name'), use_container_width=True, hide_index=True)
    else:
        st.info("No members found.")

# --- 2. ADD NEW ---
with tab_add:
    with st.form("add_member"):
        name = st.text_input("Full Name")
        gen = st.selectbox("Gender", ["Male", "Female", "Non-Binary"])
        dob = st.date_input("Date of Birth", min_value=pd.to_datetime("1940-01-01"))
        if st.form_submit_button("Add Member"):
            if name:
                r.rpush("members", json.dumps({"name": name, "gender": gen, "dob": str(dob), "status": "Active"}))
                st.success(f"Added {name}")
                st.rerun()

# --- 3. EDIT / DELETE / STATUS ---
with tab_edit:
    if not df.empty:
        target_name = st.selectbox("Select Member to Manage", sorted(df['name'].tolist()))
        m_idx = next(i for i, m in enumerate(members) if m['name'] == target_name)
        m_data = members[m_idx]

        with st.form("edit_member"):
            new_name = st.text_input("Name", value=m_data['name'])
            new_gen = st.selectbox("Gender", ["Male", "Female", "Non-Binary"], index=["Male", "Female", "Non-Binary"].index(m_data['gender']))
            new_dob = st.text_input("DOB (YYYY-MM-DD)", value=m_data['dob'])
            new_stat = st.selectbox("Status", ["Active", "Left"], index=0 if m_data.get('status') == "Active" else 1)
            
            c1, c2, _ = st.columns([1,1,2])
            if c1.form_submit_button("💾 Save Changes"):
                updated = {"name": new_name, "gender": new_gen, "dob": new_dob, "status": new_stat}
                r.lset("members", m_idx, json.dumps(updated))
                st.success("Updated!")
                st.rerun()
                
            if c2.form_submit_button("🗑️ Delete"):
                r.lset("members", m_idx, "WIPE")
                r.lrem("members", 1, "WIPE")
                st.warning("Member Deleted.")
                st.rerun()
