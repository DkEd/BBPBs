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
    st.error("Redis Connection Failed. Please check your environment variables.")

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
        return 999999
    except: return 999999

def get_club_logo():
    stored = r.get("club_logo_url")
    if stored and stored.startswith("http"): return stored
    return "https://cdn-icons-png.flaticon.com/512/55/55281.png"

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
        if str(res.get('name', '')).strip() == str(name).strip() and str(res.get('race_date', '')).strip() == str(race_date).strip():
            return True
    return False

def run_database_deduplication():
    raw_res = r.lrange("race_results", 0, -1)
    if not raw_res: return 0, 0
    unique_entries = {}
    for res_json in raw_res:
        data = json.loads(res_json)
        key = (data['name'], data['race_date'])
        new_time = data.get('time_seconds') if data.get('time_seconds') is not None else 999999
        if key not in unique_entries:
            unique_entries[key] = res_json
        else:
            existing_data = json.loads(unique_entries[key])
            existing_time = existing_data.get('time_seconds') if existing_data.get('time_seconds') is not None else 999999
            if new_time < existing_time:
                unique_entries[key] = res_json
    r.delete("race_results")
    for final_json in unique_entries.values():
        r.rpush("race_results", final_json)
    return len(raw_res), len(unique_entries)

# --- SIDEBAR & AUTH ---
with st.sidebar:
    st.image(get_club_logo(), width=150)
    st.markdown("### 🔒 Admin Access")
    pwd_input = st.text_input("Password", type="password")
    admin_pwd = r.get("admin_password") or "admin123"
    is_admin = (pwd_input == admin_pwd)
    
    st.divider()
    raw_mem = r.lrange("members", 0, -1)
    members_data = [json.loads(m) for m in raw_mem]
    missing_dob = [m['name'] for m in members_data if not m.get('dob')]
    
    if missing_dob:
        st.error(f"⚠️ {len(missing_dob)} Members missing DOB")
    else:
        st.success("✅ Data Health: Excellent")
    
    if st.button("🔄 Force Refresh"): st.rerun()

# --- MAIN TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboard", "📥 Submissions", "📋 Race Log", "👥 Members", "⚙️ System"])
all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: LEADERBOARD ---
with tab1:
    raw_res = r.lrange("race_results", 0, -1)
    active_members = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Results", len(raw_res))
    c2.metric("Active Runners", len(active_members))
    c3.metric("Pending", r.llen("pending_results"))

    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("Season Select:", years)
        
        display_df = df.copy()
        if sel_year != "All-Time":
            display_df = display_df[display_df['race_date_dt'].dt.year == int(sel_year)]
            
        stored_vis = r.get("visible_distances")
        active_dist = json.loads(stored_vis) if stored_vis else all_distances
        age_mode = r.get("age_mode") or "10Y"
        display_df['Category'] = display_df.apply(lambda x: get_category(x['dob'], x['race_date'], mode=age_mode), axis=1)

        for d in active_dist:
            st.markdown(f"### 🏁 {d}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg, tx = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                    st.markdown(f'<div style="background:{bg}; color:{tx}; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    sub = display_df[(display_df['distance'] == d) & (display_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, r_data in leaders.sort_values('Category').iterrows():
                            opacity = "1.0" if r_data['name'] in active_members else "0.5"
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">{r_data['Category']}</span><b>{r_data['name']}</b><br><small>{r_data['location']}</small></div>
                                <div style="font-weight:bold; color:#003366;">{r_data['time_display']}</div></div>''', unsafe_allow_html=True)

# --- PROTECTED ADMIN CONTENT ---
if is_admin:
    with tab2: # SUBMISSIONS
        st.subheader("⚡ Quick Manual Entry")
        with st.form("admin_manual_entry"):
            m_name = st.selectbox("Member Name", sorted([m['name'] for m in members_data]))
            m_dist = st.selectbox("Distance", all_distances)
            m_time = st.text_input("Time (e.g. 45:30)")
            m_loc = st.text_input("Race Name")
            m_date = st.date_input("Race Date", value=date.today())
            if st.form_submit_button("Add to Leaderboard"):
                matched = next((m for m in members_data if m['name'] == m_name), None)
                if matched and not is_duplicate(m_name, str(m_date)):
                    entry = {"name": m_name, "gender": matched['gender'], "dob": matched['dob'], "distance": m_dist, "time_seconds": time_to_seconds(m_time), "time_display": format_time_string(m_time), "location": m_loc, "race_date": str(m_date)}
                    r.rpush("race_results", json.dumps(entry))
                    st.success("Result Added!"); st.rerun()

        st.divider()
        st.subheader("📋 Pending Approvals")
        pending_raw = r.lrange("pending_results", 0, -1)
        for i, p_json in enumerate(pending_raw):
            p = json.loads(p_json)
            with st.expander(f"Review: {p['name']} - {p['distance']}"):
                matched = next((m for m in members_data if m['name'] == p['name']), None)
                if matched:
                    if st.button("✅ Approve", key=f"app_{i}"):
                        entry = {"name": matched['name'], "gender": matched['gender'], "dob": matched['dob'], "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']), "time_display": format_time_string(p['time_display']), "location": p['location'], "race_date": p['race_date']}
                        r.rpush("race_results", json.dumps(entry)); r.lrem("pending_results", 1, p_json); st.rerun()
                if st.button("❌ Reject", key=f"rej_{i}"):
                    r.lrem("pending_results", 1, p_json); st.rerun()

    with tab3: # RACE LOG
        st.subheader("📋 Manage Race History")
        search_q = st.text_input("🔍 Filter by Name")
        if raw_res:
            res_df = pd.DataFrame([json.loads(res) for res in raw_res])
            if search_q: res_df = res_df[res_df['name'].str.contains(search_q, case=False)]
            
            st.download_button("📥 Export to CSV", res_df.to_csv(index=False), "race_history.csv")
            
            for i, row in res_df.iterrows():
                # Fix: State key must be different from button key
                state_key = f"edit_active_{i}"
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.write(f"**{row['name']}** | {row['distance']} | {row['time_display']} | {row['race_date']}")
                    if c2.button("📝 Edit", key=f"btn_re_ed_{i}"): 
                        st.session_state[state_key] = True
                    if c3.button("🗑️", key=f"btn_re_del_{i}"): 
                        r.lrem("race_results", 1, json.dumps(row.to_dict())); st.rerun()
                    
                    if st.session_state.get(state_key):
                        with st.form(f"f_re_ed_{i}"):
                            new_t = st.text_input("New Time", row['time_display'])
                            new_d = st.text_input("New Date", row['race_date'])
                            if st.form_submit_button("Update"):
                                r.lrem("race_results", 1, json.dumps(row.to_dict()))
                                row['time_display'], row['race_date'] = new_t, new_d
                                row['time_seconds'] = time_to_seconds(new_t)
                                r.rpush("race_results", json.dumps(row.to_dict()))
                                st.session_state[state_key] = False
                                st.rerun()

    with tab4: # MEMBERS
        st.subheader("👥 Member Management")
        for i, m in enumerate(members_data):
            # Fix: Unique state key for member editing
            m_state_key = f"m_edit_active_{i}"
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{m['name']}** ({m.get('status', 'Active')})")
                if c2.button("Toggle Status", key=f"btn_m_st_{i}"):
                    r.lrem("members", 1, json.dumps(m))
                    m['status'] = "Left" if m.get('status', 'Active') == "Active" else "Active"
                    r.rpush("members", json.dumps(m)); st.rerun()
                if c3.button("📝 Edit", key=f"btn_m_ed_{i}"): 
                    st.session_state[m_state_key] = True
                
                if st.session_state.get(m_state_key):
                    with st.form(f"f_m_ed_{i}"):
                        new_dob = st.text_input("New DOB (YYYY-MM-DD)", m.get('dob', ''))
                        if st.form_submit_button("Save DOB"):
                            r.lrem("members", 1, json.dumps(m))
                            m['dob'] = new_dob
                            r.rpush("members", json.dumps(m))
                            st.session_state[m_state_key] = False
                            st.rerun()

    with tab5: # SYSTEM
        st.subheader("⚙️ System Tools")
        logo_url = st.text_input("Club Logo URL", r.get("club_logo_url") or "")
        if st.button("Save Branding"): r.set("club_logo_url", logo_url); st.rerun()
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📤 Bulk Results")
            r_file = st.file_uploader("Upload Results CSV", type="csv")
            if r_file and st.button("Bulk Process Results"):
                m_lookup = {m['name']: m for m in members_data}
                for _, row in pd.read_csv(r_file).iterrows():
                    n, dist, rd = str(row['name']).strip(), str(row['distance']).strip(), str(row['race_date']).strip()
                    if dist.lower().replace(" ","") == "10mile": dist = "10 Mile"
                    if n in m_lookup and not is_duplicate(n, rd):
                        m = m_lookup[n]
                        entry = {"name": n, "gender": m['gender'], "dob": m['dob'], "distance": dist, "time_seconds": time_to_seconds(str(row['time_display'])), "time_display": format_time_string(str(row['time_display'])), "location": str(row['location']), "race_date": rd}
                        r.rpush("race_results", json.dumps(entry))
                st.success("Bulk Upload Done!"); st.rerun()
        
        with col2:
            st.markdown("### 👥 Bulk Members")
            m_file = st.file_uploader("Upload Members CSV", type="csv")
            if m_file and st.button("Bulk Process Members"):
                for _, row in pd.read_csv(m_file).iterrows():
                    r.rpush("members", json.dumps({"name": str(row['name']).strip(), "gender": str(row['gender']).strip(), "dob": str(row['dob']).strip(), "status": "Active"}))
                st.success("Members Loaded!"); st.rerun()

        st.divider()
        if st.button("🧹 Run Database Deduplication"):
            old, new = run_database_deduplication()
            st.success(f"Removed {old-new} duplicates."); st.rerun()

        if st.button("🗑️ Wipe All Results"):
            if st.checkbox("Confirm Wipe?"): r.delete("race_results"); st.rerun()
else:
    for t in [tab2, tab3, tab4, tab5]:
        with t: st.warning("🔒 Login in sidebar to manage data.")
