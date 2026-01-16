import streamlit as st
import json
from helpers import get_redis

r = get_redis()
if not st.session_state.get('authenticated'): st.stop()

st.header("👤 Member Management")

# --- SECTION 1: ADD NEW MEMBER (Concise Row) ---
with st.expander("➕ Add New Member", expanded=False):
    with st.form("add_member", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        new_name = c1.text_input("Full Name")
        new_dob = c2.date_input("DOB", value=None, min_value=None, max_value=None)
        new_gen = c3.selectbox("Gender", ["Female", "Male"])
        submit = c4.form_submit_button("Add Member")
        
        if submit and new_name and new_dob:
            m_data = {
                "name": new_name, 
                "dob": str(new_dob), 
                "gender": new_gen, 
                "status": "Active"
            }
            r.rpush("members", json.dumps(m_data))
            st.success(f"Added {new_name}")
            st.rerun()

st.divider()

# --- SECTION 2: EDIT / SEARCH MEMBERS ---
raw_mems = r.lrange("members", 0, -1)
mems = [json.loads(m) for m in raw_mems]
mems = sorted(mems, key=lambda x: x['name'])

search = st.text_input("🔍 Search Members", "").lower()

for i, m in enumerate(mems):
    if search and search not in m['name'].lower():
        continue
        
    # Small, concise row using an expander for editing
    status_color = "🟢" if m.get('status') == "Active" else "🔴"
    with st.expander(f"{status_color} {m['name']} ({m['gender']})"):
        with st.form(f"edit_{i}"):
            c1, c2, c3 = st.columns(3)
            
            # Editable fields
            edit_name = c1.text_input("Name", m['name'])
            edit_dob = c2.text_input("DOB (YYYY-MM-DD)", m['dob'])
            edit_gen = c3.selectbox("Gender", ["Female", "Male"], index=0 if m['gender']=="Female" else 1)
            
            c4, c5, c6 = st.columns(3)
            edit_stat = c4.selectbox("Status", ["Active", "Left"], index=0 if m.get('status', 'Active')=="Active" else 1)
            
            # Save Logic
            if c5.form_submit_button("💾 Save Changes"):
                updated_m = {
                    "name": edit_name,
                    "dob": edit_dob,
                    "gender": edit_gen,
                    "status": edit_stat
                }
                # Replace in Redis
                r.lset("members", i, json.dumps(updated_m))
                st.success("Updated!")
                st.rerun()
            
            # Delete Logic
            if c6.form_submit_button("🗑️ Delete Member"):
                r.lrem("members", 1, json.dumps(m))
                st.warning(f"Deleted {m['name']}")
                st.rerun()
