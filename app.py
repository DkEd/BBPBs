import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- CONFIG & CONNECTION ---
st.set_page_config(page_title="Club Leaderboard", layout="wide")

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except:
    st.error("Redis Connection Failed")

# --- PASSWORD LOGIC (Stored in Redis) ---
def get_admin_password():
    stored_pwd = r.get("admin_password")
    if not stored_pwd:
        # Default password if none exists in Redis yet
        return "admin123"
    return stored_pwd

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
    current_pwd = get_admin_password()
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == current_pwd)
    
    if is_admin:
        st.success("Admin Access Granted")
        st.divider()
        st.subheader("Settings")
        new_pwd = st.text_input("Update Password", type="password")
        if st.button("Save New Password"):
            if new_pwd:
                r.set("admin_password", new_pwd)
                st.success("Password Updated!")
                st.rerun()
    else:
        st.warning("Enter password to manage data")

# --- MAIN UI ---
st.title("🏃‍♂️ Club Records & Leaderboard")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Admin"])

# --- TAB 1: LEADERBOARD (Clean & Professional) ---
with tab1:
    view = st.radio("Displaying:", ["All-Time Records", "2026 Season Only"], horizontal=True)
    raw_results = r.lrange("race_results", 0, -1)
    
    if raw_results:
        df = pd.DataFrame([json.loads(res) for res in raw_results])
        if view == "2026 Season Only":
            df = df[pd.to_datetime(df['race_date']).dt.year == 2026]
        
        df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date']), axis=1)
        cat_order = ["Senior", "V40", "V50", "V60", "V70"]
        
        for d in ["5k", "10k", "10 Mile", "HM", "Marathon"]:
            st.markdown(f"## {d} Club Records")
            m_col, f_col = st.columns(2)
            
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    st.markdown(f"#### {gen}")
                    subset = df[(df['distance'] == d) & (df['gender'] == gen)]
                    leaders = subset.sort_values('time_seconds').groupby('Category', observed=True).head(1)
                    
                    if not leaders.empty:
                        leaders['Category'] = pd.Categorical(leaders['Category'], categories=cat_order, ordered=True)
                        res_table = leaders.sort_values('Category')[['Category', 'name', 'time_display', 'location', 'race_date']]
                        res_table.columns = ['Category', 'Runner', 'Time', 'Location', 'Date']
                        
                        # Apply CSS to make it look modern
                        st.dataframe(res_table.set_index('Category'), use_container_width=True)
                    else:
                        st.caption(f"No {gen} records for {d} yet.")
            st.markdown("---")
    else:
        st.info("The database is currently empty.")

# --- TAB 2: ACTIVITY FEED ---
with tab2:
    st.header("Recent Race Activity")
    if raw_results:
        all_df = pd.DataFrame([json.loads(res) for res in raw_results])
        all_df = all_df.sort_values('race_date', ascending=False)
        st.table(all_df[['race_date', 'name', 'distance', 'time_display', 'location']].head(20))

# --- TAB 3: MEMBER MANAGEMENT ---
with tab3:
    if is_admin:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Add New Member")
            with st.form("mem_form", clear_on_submit=True):
                n = st.text_input("Full Name")
                g = st.selectbox("Gender", ["Male", "Female"])
                b = st.date_input("Date of Birth", value=date(1990, 1, 1), min_value=date(1920, 1, 1))
                if st.form_submit_button("Register Member"):
                    if n:
                        r.rpush("members", json.dumps({"name":n, "gender":g, "dob":str(b)}))
                        st.success(f"{n} added.")
                        st.rerun()
        with col2:
            st.subheader("Member List")
            m_raw = r.lrange("members", 0, -1)
            if m_raw:
                m_list = [json.loads(m) for m in m_raw]
                m_df = pd.DataFrame(m_list).sort_values('name')
                st.dataframe(m_df, use_container_width=True, hide_index=True)
                
                member_to_del = st.selectbox("Select to Delete", m_df['name'])
                if st.button("Delete Selected Member"):
                    new_m = [json.dumps(m) for m in m_list if m['name'] != member_to_del]
                    r.delete("members")
                    if new_m: r.rpush("members", *new_m)
                    st.rerun()
    else:
        st.error("Admin login required to view or edit members.")

# --- TAB 4: DATA CLEANUP & RESULTS ---
with tab4:
    if is_admin:
        st.header("Manage Race Results")
        with st.form("race_form", clear_on_submit=True):
            members = [json.loads(m) for m in r.lrange("members", 0, -1)]
            if members:
                n_sel = st.selectbox("Select Runner", sorted([m['name'] for m in members]))
                m_info = next(i for i in members if i["name"] == n_sel)
                dist = st.selectbox("Race Distance", ["5k", "10k", "10 Mile", "HM", "Marathon"])
                t_str = st.text_input("Time (HH:MM:SS)")
                loc = st.text_input("Race Location")
                dt = st.date_input("Race Date")
                if st.form_submit_button("Submit Result"):
                    secs = time_to_seconds(t_str)
                    if secs:
                        entry = {"name": n_sel, "gender": m_info['gender'], "dob": m_info['dob'], 
                                 "distance": dist, "time_seconds": secs, "time_display": t_str, 
                                 "location": loc, "race_date": str(dt)}
                        r.rpush("race_results", json.dumps(entry))
                        st.success("Result Saved!")
                        st.rerun()
            else: st.warning("Register members first.")
        
        st.divider()
        st.subheader("Delete Specific Results")
        if raw_results:
            res_list = [json.loads(res) for res in raw_results]
            res_labels = [f"{res['race_date']} - {res['name']} ({res['distance']})" for res in res_list]
            res_to_del = st.selectbox("Select Result", res_labels)
            if st.button("Delete Result"):
                idx = res_labels.index(res_to_del)
                res_list.pop(idx)
                r.delete("race_results")
                if res_list: r.rpush("race_results", *[json.dumps(res) for res in res_list])
                st.rerun()
    else:
        st.error("Admin login required to manage race data.")
