import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- CONFIG & CONNECTION ---
st.set_page_config(page_title="AutoKudos Leaderboard", layout="wide")

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    st.error(f"Redis Connection Failed: Check environment variables.")

# --- HELPER FUNCTIONS ---
def get_admin_password():
    stored_pwd = r.get("admin_password")
    return stored_pwd if stored_pwd else "admin123"

def get_club_logo():
    stored_logo = r.get("club_logo_url")
    default_logo = "https://scontent-lhr6-2.xx.fbcdn.net/v/t39.30808-6/613136946_122094772515215234_2783950400659519915_n.jpg?_nc_cat=105&ccb=1-7&oh=00_AfquWT54_DxkPrvTyRnSk2y3a3tBuCxJBvkLCS8rd7ANlg&oe=696A8E3D"
    return stored_logo if stored_logo else default_logo

def get_category(dob_str, race_date_str, mode="10Y"):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        if mode == "5Y":
            if age < 35: return "Senior"
            return f"V{(age // 5) * 5}"
        return f"V{(age // 10) * 10}" if age >= 40 else "Senior"
    except: return "Unknown"

def time_to_seconds(t_str):
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return None

# --- UI HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(get_club_logo(), width=120)
with col_title:
    st.markdown('<h1 style="color: #003366; margin-top: 10px;">AutoKudos Leaderboard</h1>', unsafe_allow_html=True)

# --- ADMIN LOGIN ---
with st.sidebar:
    st.markdown('<h2 style="color: #003366;">🔐 Admin Login</h2>', unsafe_allow_html=True)
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == get_admin_password())

# --- TABS ---
# New Tab 2: Submission (Public)
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏆 Leaderboards", "📤 Submit Result", "⏱️ Activity", "👤 Members", "🛠️ Admin", "👁️ View Controller"])

all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: PUBLIC LEADERBOARDS ---
with tab1:
    stored_vis = r.get("visible_distances")
    active_dist = json.loads(stored_vis) if stored_vis else all_distances
    age_mode = r.get("age_mode") or "10Y"
    raw_res = r.lrange("race_results", 0, -1)
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("📅 Select Season:", years)
        display_df = df.copy()
        if sel_year != "All-Time":
            display_df = display_df[display_df['race_date_dt'].dt.year == int(sel_year)]
        display_df['Category'] = display_df.apply(lambda x: get_category(x['dob'], x['race_date'], mode=age_mode), axis=1)
        
        for d in active_dist:
            st.markdown(f"### 🏁 {d} Records")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg, tx = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                    st.markdown(f'<div style="background-color:{bg}; color:{tx}; padding:10px; border-radius:8px 8px 0 0; text-align:center; font-weight:800; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    sub = display_df[(display_df['distance'] == d) & (display_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, r_data in leaders.sort_values('Category').iterrows():
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:12px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center;">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em; margin-right:8px;">{r_data['Category']}</span><b>{r_data['name']}</b><br><small>{r_data['location']} | {r_data['race_date']}</small></div>
                                <div style="font-weight:800; color:#003366; font-size:1.1em;">{r_data['time_display']}</div></div>''', unsafe_allow_html=True)
                    else: st.markdown('<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; color:#999; font-size:0.8em;">No records</div>', unsafe_allow_html=True)
    else: st.info("Welcome to AutoKudos! The leaderboard will appear once results are uploaded.")

# --- TAB 2: PUBLIC SUBMISSION ---
with tab2:
    st.header("📤 Submit Your Race Result")
    st.write("Fill in your details below. Results will be verified by an admin before appearing on the leaderboard.")
    
    with st.form("submission_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            sub_name = st.text_input("Full Name (as registered with club)")
            sub_dist = st.selectbox("Distance", all_distances)
            sub_loc = st.text_input("Race Location (e.g. Abbey Dash)")
        with col2:
            sub_date = st.date_input("Race Date", value=date.today())
            sub_time = st.text_input("Time (HH:MM:SS or MM:SS)")
        
        submitted = st.form_submit_button("Submit for Approval")
        
        if submitted:
            if sub_name and sub_time and sub_loc:
                pending_entry = {
                    "name": sub_name.strip(),
                    "distance": sub_dist,
                    "location": sub_loc.strip(),
                    "race_date": str(sub_date),
                    "time_display": sub_time.strip(),
                    "submitted_at": str(datetime.now())
                }
                r.rpush("pending_results", json.dumps(pending_entry))
                st.success("✅ Thank you! Your result has been sent to the admin for approval.")
            else:
                st.error("Please fill in all fields.")

# --- PROTECTED TABS ---
with tab3: # Activity
    if is_admin:
        if raw_res:
            st.dataframe(pd.DataFrame([json.loads(res) for res in raw_res]).sort_values('race_date', ascending=False), use_container_width=True, hide_index=True)
    else: st.warning("🔒 Admin login required.")

with tab4: # Members
    if is_admin:
        raw_mem = r.lrange("members", 0, -1)
        if raw_mem:
            st.dataframe(pd.DataFrame([json.loads(m) for m in raw_mem]).sort_values('name'), use_container_width=True, hide_index=True)
    else: st.warning("🔒 Admin login required.")

with tab5: # Admin & Approvals
    if is_admin:
        st.header("🛠️ Admin & Approvals")
        
        # --- APPROVAL SECTION ---
        st.subheader("📋 Pending Approvals")
        pending_raw = r.lrange("pending_results", 0, -1)
        if pending_raw:
            m_raw = r.lrange("members", 0, -1)
            m_lookup = {json.loads(m)['name']: json.loads(m) for m in m_raw}
            
            for i, p_json in enumerate(pending_raw):
                p = json.loads(p_json)
                with st.expander(f"Review: {p['name']} - {p['distance']} ({p['time_display']})"):
                    st.write(f"**Location:** {p['location']} | **Date:** {p['race_date']}")
                    
                    if p['name'] not in m_lookup:
                        st.error("⚠️ Member name not found in database! They must be registered first.")
                    
                    c1, c2, _ = st.columns([1, 1, 4])
                    if c1.button("✅ Approve", key=f"app_{i}"):
                        if p['name'] in m_lookup:
                            m = m_lookup[p['name']]
                            final_entry = {
                                "name": p['name'], "gender": m['gender'], "dob": m['dob'],
                                "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']),
                                "time_display": p['time_display'], "location": p['location'], "race_date": p['race_date']
                            }
                            r.rpush("race_results", json.dumps(final_entry))
                            r.lrem("pending_results", 1, p_json)
                            st.success("Result Approved!")
                            st.rerun()
                    if c2.button("❌ Reject", key=f"rej_{i}"):
                        r.lrem("pending_results", 1, p_json)
                        st.warning("Result Rejected.")
                        st.rerun()
        else:
            st.info("No pending results to review.")
            
        st.divider()
        # (Standard CSV Import logic remains here...)
        st.subheader("Bulk Import")
        # [Insert your previous CSV Import code here if needed]

with tab6: # View Controller
    if is_admin:
        st.header("👁️ View Controller")
        # [Insert your previous View Controller code here]
    else: st.warning("🔒 Admin login required.")
