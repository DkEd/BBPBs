import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime

# --- CONFIG & CONNECTION ---
st.set_page_config(page_title="AutoKudos Admin", layout="wide")

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    st.error(f"Redis Connection Failed: {e}")

# --- HELPER FUNCTIONS ---
def format_time_string(t_str):
    try:
        parts = str(t_str).strip().split(':')
        if len(parts) == 2: return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3: return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return t_str
    except: return t_str

def time_to_seconds(t_str):
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return 999999

def get_admin_password():
    return r.get("admin_password") or "admin123"

def get_club_logo():
    return r.get("club_logo_url") or "https://scontent-lhr6-2.xx.fbcdn.net/v/t39.30808-6/613136946_122094772515215234_2783950400659519915_n.jpg?_nc_cat=105&ccb=1-7&oh=00_AfquWT54_DxkPrvTyRnSk2y3a3tBuCxJBvkLCS8rd7ANlg&oe=696A8E3D"

def get_category(dob_str, race_date_str, mode="10Y"):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        threshold = 35 if mode == "5Y" else 40
        step = 5 if mode == "5Y" else 10
        if age < threshold: return "Senior"
        return f"V{(age // step) * step}"
    except: return "Unknown"

def is_duplicate(name, race_date):
    current_results = r.lrange("race_results", 0, -1)
    for res_json in current_results:
        res = json.loads(res_json)
        if res['name'] == name and res['race_date'] == race_date:
            return True
    return False

def run_database_deduplication():
    raw_res = r.lrange("race_results", 0, -1)
    if not raw_res: return 0, 0
    unique_entries = {}
    for res_json in raw_res:
        data = json.loads(res_json)
        key = (data['name'], data['race_date'])
        if key not in unique_entries or data['time_seconds'] < json.loads(unique_entries[key])['time_seconds']:
            unique_entries[key] = res_json
    r.delete("race_results")
    for final_json in unique_entries.values():
        r.rpush("race_results", final_json)
    return len(raw_res), len(unique_entries)

# --- UI HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo: st.image(get_club_logo(), width=120)
with col_title: st.markdown('<h1 style="color: #003366;">AutoKudos Admin Portal</h1>', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == get_admin_password())
    if st.button("🔄 Refresh All Data", use_container_width=True): st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Approvals & Bulk", "👁️ View Controller"])
all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: LEADERBOARDS ---
with tab1:
    raw_res = r.lrange("race_results", 0, -1)
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        df['time_display'] = df['time_display'].apply(format_time_string)
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("📅 Season Select:", years)
        display_df = df.copy()
        if sel_year != "All-Time": display_df = display_df[display_df['race_date_dt'].dt.year == int(sel_year)]
        age_mode = r.get("age_mode") or "10Y"
        display_df['Category'] = display_df.apply(lambda x: get_category(x['dob'], x['race_date'], mode=age_mode), axis=1)
        # (Rendering code omitted for brevity but remains the same as previous)

# --- PROTECTED TABS ---
if is_admin:
    with tab2: # ACTIVITY
        st.subheader("⏱️ Activity Log & Manual Deletion")
        if raw_res:
            res_list = sorted([json.loads(res) for res in raw_res], key=lambda x: x['race_date'], reverse=True)
            for i, item in enumerate(res_list):
                c1, c2 = st.columns([5, 1])
                c1.write(f"**{item['name']}** - {item['distance']} ({item['time_display']}) on {item['race_date']}")
                if c2.button("🗑️", key=f"del_{i}"):
                    r.lrem("race_results", 1, json.dumps(item)); st.rerun()

    with tab3: # MEMBERS
        st.subheader("👤 Member List")
        raw_mem = r.lrange("members", 0, -1)
        if raw_mem:
            m_df = pd.DataFrame([json.loads(m) for m in raw_mem])
            st.dataframe(m_df, use_container_width=True, hide_index=True)

    with tab4: # APPROVALS & BULK
        st.header("🛠️ Approvals & Cleanup")
        if st.button("🧹 Run Database Deduplication"):
            old, new = run_database_deduplication()
            st.success(f"Cleaned! {old-new} duplicates removed.")

        st.subheader("📋 Pending BBPB Submissions")
        pending_raw = r.lrange("pending_results", 0, -1)
        raw_mem = r.lrange("members", 0, -1)
        members_data = [json.loads(m) for m in raw_mem]
        member_names = sorted([m['name'] for m in members_data])

        if pending_raw:
            for i, p_json in enumerate(pending_raw):
                p = json.loads(p_json)
                with st.expander(f"Review: {p['name']} - {p['race_date']}"):
                    # Logic to find exact match
                    matched_member = next((m for m in members_data if m['name'] == p['name']), None)
                    
                    if not matched_member:
                        st.error(f"⚠️ '{p['name']}' not found in database.")
                        corrected_name = st.selectbox("Assign to correct member:", ["-- Select Member --"] + member_names, key=f"corr_{i}")
                        matched_member = next((m for m in members_data if m['name'] == corrected_name), None)
                    else:
                        st.success(f"Match Found: {matched_member['name']}")

                    if matched_member:
                        if is_duplicate(matched_member['name'], p['race_date']):
                            st.warning("🚨 This runner already has an entry for this date.")
                        
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Approve", key=f"app_{i}"):
                            entry = {
                                "name": matched_member['name'], "gender": matched_member['gender'], 
                                "dob": matched_member['dob'], "distance": p['distance'], 
                                "time_seconds": time_to_seconds(p['time_display']), 
                                "time_display": format_time_string(p['time_display']), 
                                "location": p['location'], "race_date": p['race_date']
                            }
                            r.rpush("race_results", json.dumps(entry))
                            r.lrem("pending_results", 1, p_json); st.rerun()
                    
                    if st.button("❌ Reject / Delete", key=f"rej_{i}"):
                        r.lrem("pending_results", 1, p_json); st.rerun()
        
        st.divider()
        st.subheader("🚀 Bulk Import")
        r_file = st.file_uploader("Upload Results CSV", type="csv")
        if r_file and st.button("Process CSV"):
            m_lookup = {m['name']: m for m in members_data}
            r_df = pd.read_csv(r_file)
            added, skipped = 0, 0
            for _, row in r_df.iterrows():
                n, d_str = str(row['name']).strip(), str(row['race_date']).strip()
                if n in m_lookup and not is_duplicate(n, d_str):
                    m = m_lookup[n]
                    entry = {"name": n, "gender": m['gender'], "dob": m['dob'], "distance": str(row['distance']).strip(), "time_seconds": time_to_seconds(str(row['time_display'])), "time_display": format_time_string(str(row['time_display'])), "location": str(row['location']).strip(), "race_date": d_str}
                    r.rpush("race_results", json.dumps(entry)); added += 1
                else: skipped += 1
            st.success(f"Added {added}, Skipped {skipped}"); st.rerun()

    with tab5: # VIEW CONTROLLER
        st.header("👁️ Global Settings")
        stored_vis = r.get("visible_distances")
        default_vis = all_distances if not stored_vis else json.loads(stored_vis)
        visible_list = [d for d in all_distances if st.checkbox(d, value=(d in default_vis), key=f"vc_{d}")]
        if st.button("Save View Settings"):
            r.set("visible_distances", json.dumps(visible_list)); st.success("Saved!")

else:
    for t in [tab2, tab3, tab4, tab5]:
        with t: st.warning("🔒 Enter password in sidebar to access admin tools.")
