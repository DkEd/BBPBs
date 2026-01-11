import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- CONFIG & CONNECTION ---
st.set_page_config(page_title="Club Leaderboard", layout="wide")

# Change this to your preferred password
ADMIN_PASSWORD = "yourpassword123" 

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except:
    st.error("Redis Connection Failed")

# --- CORE LOGIC ---
def get_category(dob_str, race_date_str):
    dob = datetime.strptime(dob_str, '%Y-%m-%d')
    race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
    age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
    if age < 40: return "Senior"
    if age < 50: return "V40"
    if age < 60: return "V50"
    if age < 70: return "V60"
    return "V70"

def time_to_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return None

# --- SIDEBAR ADMIN ---
with st.sidebar:
    st.title("🔐 Admin Login")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == ADMIN_PASSWORD)
    if is_admin:
        st.success("Admin Access Granted")
    else:
        st.warning("Enter password to manage data")

# --- MAIN UI ---
tab1, tab2, tab3, tab4 = st.tabs(["Leaderboard", "Activity Feed", "Member Management", "Data Cleanup"])

# --- TAB 1: LEADERBOARD ---
with tab1:
    st.title("🏆 Club Records")
    view = st.radio("Filter:", ["All-Time Records", "2026 Season"], horizontal=True)
    raw_results = r.lrange("race_results", 0, -1)
    
    if raw_results:
        df = pd.DataFrame([json.loads(res) for res in raw_results])
        if view == "2026 Season":
            df = df[pd.to_datetime(df['race_date']).dt.year == 2026]
        
        df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date']), axis=1)
        
        for d in ["5k", "10k", "10 Mile", "HM", "Marathon"]:
            st.subheader(f"🏁 {d}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    st.write(f"**{gen}**")
                    subset = df[(df['distance'] == d) & (df['gender'] == gen)]
                    leaders = subset.sort_values('time_seconds').groupby('Category', observed=True).head(1)
                    if not leaders.empty:
                        cat_order = ["Senior", "V40", "V50", "V60", "V70"]
                        leaders['Category'] = pd.Categorical(leaders['Category'], categories=cat_order, ordered=True)
                        res_table = leaders.sort_values('Category')[['Category', 'name', 'time_display', 'location', 'race_date']]
                        res_table.columns = ['Cat', 'Runner', 'Time', 'Where', 'When']
                        st.table(res_table.set_index('Cat'))
                    else: st.info(f"No {gen} records")
    else: st.info("Database is empty.")

# --- TAB 2: ACTIVITY FEED ---
with tab2:
    st.header("Recent Results")
    if raw_results:
        all_df = pd.DataFrame([json.loads(res) for res in raw_results])
        all_df = all_df.sort_values('race_date', ascending=False)
        st.dataframe(all_df[['race_date', 'name', 'distance', 'time_display', 'location']], use_container_width=True, hide_index=True)

# --- TAB 3: MEMBER MANAGEMENT ---
with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.header("Register New Runner")
        if is_admin:
            with st.form("mem_form", clear_on_submit=True):
                n = st.text_input("Name")
                g = st.selectbox("Gender", ["Male", "Female"])
                b = st.date_input("DOB", value=date(1990, 1, 1), min_value=date(1920, 1, 1))
                if st.form_submit_button("Add Member"):
                    r.rpush("members", json.dumps({"name":n, "gender":g, "dob":str(b)}))
                    st.success(f"{n} Registered!")
                    st.rerun()
        else: st.error("Admin Password Required")

    with col2:
        st.header("Log Race Result")
        if is_admin:
            members_raw = r.lrange("members", 0, -1)
            members = [json.loads(m) for m in members_raw]
            if members:
                with st.form("race_form", clear_on_submit=True):
                    n_sel = st.selectbox("Runner", sorted([m['name'] for m in members]))
                    m_info = next(i for i in members if i["name"] == n_sel)
                    dist = st.selectbox("Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"])
                    t_str = st.text_input("Time (HH:MM:SS)")
                    loc = st.text_input("Location")
                    dt = st.date_input("Race Date")
                    if st.form_submit_button("Save Result"):
                        secs = time_to_seconds(t_str)
                        if secs:
                            entry = {"name": n_sel, "gender": m_info['gender'], "dob": m_info['dob'], 
                                     "distance": dist, "time_seconds": secs, "time_display": t_str, 
                                     "location": loc, "race_date": str(dt)}
                            r.rpush("race_results", json.dumps(entry))
                            st.success("Result Saved!")
                            st.rerun()
            else: st.warning("Register members first.")
        else: st.error("Admin Password Required")

# --- TAB 4: DATA CLEANUP (SPECIFIC DELETION) ---
with tab4:
    st.header("Admin Cleanup Tools")
    if is_admin:
        # --- DELETE MEMBER ---
        st.subheader("Remove a Member")
        members_raw = r.lrange("members", 0, -1)
        if members_raw:
            m_list = [json.loads(m) for m in members_raw]
            m_to_del = st.selectbox("Select Member to Remove", [m['name'] for m in m_list])
            if st.button("❌ Permanently Delete Member"):
                # Filter out the selected member and rewrite the list
                new_m_list = [json.dumps(m) for m in m_list if m['name'] != m_to_del]
                r.delete("members")
                if new_m_list:
                    r.rpush("members", *new_m_list)
                st.warning(f"{m_to_del} removed from database.")
                st.rerun()

        st.divider()

        # --- DELETE RESULT ---
        st.subheader("Remove a Specific Race Result")
        if raw_results:
            res_list = [json.loads(res) for res in raw_results]
            # Create a label for the dropdown
            res_labels = [f"{res['race_date']} - {res['name']} ({res['distance']})" for res in res_list]
            res_to_del_label = st.selectbox("Select Result to Remove", res_labels)
            
            if st.button("❌ Permanently Delete Result"):
                # Find index of selected label and remove
                idx = res_labels.index(res_to_del_label)
                res_list.pop(idx)
                r.delete("race_results")
                if res_list:
                    r.rpush("race_results", *[json.dumps(res) for res in res_list])
                st.warning("Result deleted.")
                st.rerun()
    else:
        st.error("Admin Password Required to access Cleanup Tools.")
