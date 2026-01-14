import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

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
    return r.get("club_logo_url") or "https://scontent-lhr6-2.xx.fbcdn.net/v/t39.30808-6/613136946_122094772515215234_2783950400659519915_n.jpg"

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
with col_title: st.markdown('<h1 style="color: #003366; margin-top: 10px;">AutoKudos Admin Portal</h1>', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown('<h2 style="color: #003366;">🔐 Admin Login</h2>', unsafe_allow_html=True)
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == get_admin_password())
    if st.button("🔄 Refresh Data", use_container_width=True): st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Approvals & Bulk", "👁️ Settings"])
all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: LEADERBOARDS ---
with tab1:
    raw_res = r.lrange("race_results", 0, -1)
    members_list = [json.loads(m) for m in r.lrange("members", 0, -1)]
    active_members = [m['name'] for m in members_list if m.get('status', 'Active') == 'Active']
    
    # Summary Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", len(raw_res))
    c2.metric("Active Members", len(active_members))
    c3.metric("Former Members", len(members_list) - len(active_members))
    
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        df['time_display'] = df['time_display'].apply(format_time_string)
        
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("📅 Season Select:", years)
        
        display_df = df.copy()
        if sel_year != "All-Time":
            display_df = display_df[display_df['race_date_dt'].dt.year == int(sel_year)]
            
        stored_vis = r.get("visible_distances")
        active_dist = json.loads(stored_vis) if stored_vis else all_distances
        age_mode = r.get("age_mode") or "10Y"
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
                            # Ghosting check: Gray out name if not active
                            name_style = "color:#003366;" if r_data['name'] in active_members else "color:#999; font-style:italic;"
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:12px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center;">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em; margin-right:8px;">{r_data['Category']}</span><b style="{name_style}">{r_data['name']}</b><br><small>{r_data['location']} | {r_data['race_date']}</small></div>
                                <div style="font-weight:800; color:#003366; font-size:1.1em;">{r_data['time_display']}</div></div>''', unsafe_allow_html=True)
                    else: st.markdown('<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; color:#999; font-size:0.8em;">No records</div>', unsafe_allow_html=True)

# --- PROTECTED ADMIN CONTENT ---
if is_admin:
    with tab2: # ACTIVITY
        st.subheader("⏱️ Manual Deletion")
        if raw_res:
            res_list = sorted([json.loads(res) for res in raw_res], key=lambda x: x['race_date'], reverse=True)
            for i, item in enumerate(res_list):
                c1, c2 = st.columns([5, 1])
                c1.write(f"**{item['name']}** - {item['distance']} ({item['time_display']})")
                if c2.button("🗑️", key=f"del_{i}"):
                    r.lrem("race_results", 1, json.dumps(item)); st.rerun()

    with tab3: # MEMBERS & HEALTH CHECK
        st.subheader("🛡️ Data Health Audit")
        raw_mem = r.lrange("members", 0, -1)
        members_data = [json.loads(m) for m in raw_mem]
        
        # Health Logic
        missing_dob = [m['name'] for m in members_data if not m.get('dob') or m['dob'] == ""]
        future_races = [json.loads(res) for res in r.lrange("race_results", 0, -1) if datetime.strptime(json.loads(res)['race_date'], '%Y-%m-%d').date() > date.today()]
        
        if missing_dob or future_races:
            if missing_dob: st.error(f"⚠️ Missing DOB for: {', '.join(missing_dob)}")
            if future_races: st.warning(f"🕒 Found {len(future_races)} races with future dates! Check Activity Log.")
        else:
            st.success("✅ Database Health: Excellent. All members have DOBs and dates are valid.")

        st.divider()
        st.subheader("👤 Member Management")
        if members_data:
            m_df = pd.DataFrame(members_data)
            # Add Status Toggle
            for i, row in m_df.iterrows():
                col_name, col_stat = st.columns([3, 1])
                status = row.get('status', 'Active')
                col_name.write(f"**{row['name']}** ({row['gender']}) - {row['dob']}")
                if col_stat.button("Mark as " + ("Left" if status == 'Active' else "Active"), key=f"stat_{i}"):
                    new_status = "Left" if status == 'Active' else "Active"
                    r.lrem("members", 1, json.dumps(row))
                    row['status'] = new_status
                    r.rpush("members", json.dumps(row)); st.rerun()

    with tab4: # APPROVALS, BULK, EXPORT
        st.header("🛠️ Admin Console")
        
        # EXPORT SECTION
        st.subheader("📥 Data Export (Excel Friendly)")
        e1, e2 = st.columns(2)
        if raw_res:
            res_csv = pd.DataFrame([json.loads(res) for res in raw_res]).to_csv(index=False)
            e1.download_button("Download All Results (CSV)", res_csv, "bbpb_results.csv", "text/csv")
        if members_data:
            mem_csv = pd.DataFrame(members_data).to_csv(index=False)
            e2.download_button("Download Members List (CSV)", mem_csv, "club_members.csv", "text/csv")

        st.divider()
        st.subheader("📋 Pending Approvals")
        pending_raw = r.lrange("pending_results", 0, -1)
        member_names = sorted([m['name'] for m in members_data])

        if pending_raw:
            for i, p_json in enumerate(pending_raw):
                p = json.loads(p_json)
                with st.expander(f"Review: {p['name']} - {p['race_date']}"):
                    matched_member = next((m for m in members_data if m['name'] == p['name']), None)
                    if not matched_member:
                        st.error("Name not matched.")
                        corrected = st.selectbox("Assign to:", ["-- Select --"] + member_names, key=f"corr_{i}")
                        matched_member = next((m for m in members_data if m['name'] == corrected), None)
                    
                    if matched_member:
                        if is_duplicate(matched_member['name'], p['race_date']): st.warning("Duplicate Detected.")
                        if st.button("✅ Approve", key=f"app_{i}"):
                            entry = {"name": matched_member['name'], "gender": matched_member['gender'], "dob": matched_member['dob'], "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']), "time_display": format_time_string(p['time_display']), "location": p['location'], "race_date": p['race_date']}
                            r.rpush("race_results", json.dumps(entry)); r.lrem("pending_results", 1, p_json); st.rerun()
                    if st.button("❌ Reject", key=f"rej_{i}"): r.lrem("pending_results", 1, p_json); st.rerun()

        st.divider()
        st.subheader("🚀 Bulk Import")
        col_m, col_r = st.columns(2)
        with col_m:
            m_file = st.file_uploader("Upload Members CSV (name,gender,dob)", type="csv")
            if m_file and st.button("Process Members"):
                for _, row in pd.read_csv(m_file).iterrows():
                    r.rpush("members", json.dumps({"name": str(row['name']).strip(), "gender": str(row['gender']).strip(), "dob": str(row['dob']).strip(), "status": "Active"}))
                st.success("Members Added!"); st.rerun()
        with col_r:
            r_file = st.file_uploader("Upload Results CSV", type="csv")
            if r_file and st.button("Process Results"):
                m_lookup = {m['name']: m for m in members_data}
                added = 0
                for _, row in pd.read_csv(r_file).iterrows():
                    n, d_str = str(row['name']).strip(), str(row['race_date']).strip()
                    if n in m_lookup and not is_duplicate(n, d_str):
                        m = m_lookup[n]
                        entry = {"name": n, "gender": m['gender'], "dob": m['dob'], "distance": str(row['distance']).strip(), "time_seconds": time_to_seconds(str(row['time_display'])), "time_display": format_time_string(str(row['time_display'])), "location": str(row['location']).strip(), "race_date": d_str}
                        r.rpush("race_results", json.dumps(entry)); added += 1
                st.success(f"Added {added} results!"); st.rerun()

    with tab5: # SETTINGS
        st.header("👁️ Global Settings")
        stored_vis = r.get("visible_distances")
        default_vis = all_distances if not stored_vis else json.loads(stored_vis)
        visible_list = [d for d in all_distances if st.checkbox(d, value=(d in default_vis), key=f"vc_{d}")]
        stored_mode = r.get("age_mode") or "10Y"
        age_choice = st.radio("Age Grouping:", ["10 Years", "5 Years"], index=0 if stored_mode == "10Y" else 1)
        if st.button("Save Global View Settings"):
            r.set("visible_distances", json.dumps(visible_list))
            r.set("age_mode", "10Y" if "10" in age_choice else "5Y"); st.success("Saved!")
        st.divider()
        if st.button("🗑️ Wipe All Results Database"):
            if st.checkbox("Verify results wipe?"): r.delete("race_results"); st.rerun()
else:
    for t in [tab2, tab3, tab4, tab5]:
        with t: st.warning("🔒 Enter password in sidebar to unlock Admin Tools.")
