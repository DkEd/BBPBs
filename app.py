import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="AutoKudos Admin", layout="wide")

redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    st.error("Redis Connection Failed. Check environment variables.")

# --- 2. HELPERS (Full Logic) ---
def format_time_string(t_str):
    try:
        parts = str(t_str).strip().split(':')
        if len(parts) == 2: 
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3: 
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return str(t_str)
    except:
        return str(t_str)

def time_to_seconds(t_str):
    try:
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: 
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: 
            return parts[0] * 60 + parts[1]
        return 999999
    except:
        return 999999

def get_club_logo():
    stored = r.get("club_logo_url")
    if stored and stored.startswith("http"): 
        return stored
    return "https://cdn-icons-png.flaticon.com/512/55/55281.png"

def get_category(dob_str, race_date_str, mode="10Y"):
    try:
        dob = datetime.strptime(str(dob_str), '%Y-%m-%d')
        race_date = datetime.strptime(str(race_date_str), '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        threshold = 35 if mode == "5Y" else 40
        step = 5 if mode == "5Y" else 10
        if age < threshold: return "Senior"
        return f"V{(age // step) * step}"
    except:
        return "Unknown"

def is_duplicate_pb(name, race_date):
    current_results = r.lrange("race_results", 0, -1)
    for res_json in current_results:
        res = json.loads(res_json)
        if str(res.get('name', '')).strip() == str(name).strip() and str(res.get('race_date', '')).strip() == str(race_date).strip():
            return True
    return False

# --- 3. SIDEBAR & VISIBILITY ---
with st.sidebar:
    st.image(get_club_logo(), width=150)
    st.markdown("### 🔒 Admin Access")
    pwd_input = st.text_input("Password", type="password")
    admin_pwd = r.get("admin_password") or "admin123"
    is_admin = (pwd_input == admin_pwd)
    
    if is_admin:
        st.divider()
        st.markdown("### 👁️ Public Visibility")
        current_vis = r.get("show_champ_tab") == "True"
        champ_toggle = st.toggle("Show Champ Tab on BBPB", value=current_vis)
        if st.button("Save Tab Visibility"):
            r.set("show_champ_tab", str(champ_toggle))
            st.rerun()
    
    st.divider()
    raw_mem = r.lrange("members", 0, -1)
    members_data = [json.loads(m) for m in raw_mem]
    if st.button("🔄 Force Refresh Data"): 
        st.rerun()

# --- 4. MAIN NAVIGATION ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏆 Leaderboard", "📥 Submissions", "📋 Race Log", "👥 Members", "🏅 Championship", "⚙️ System"
])

dist_list = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: LEADERBOARD VIEW ---
with tab1:
    raw_res = r.lrange("race_results", 0, -1)
    active_names = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']
    
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("Select Season:", years)
        
        disp_df = df.copy()
        if sel_year != "All-Time":
            disp_df = disp_df[disp_df['race_date_dt'].dt.year == int(sel_year)]
            
        age_mode = r.get("age_mode") or "10Y"
        disp_df['Category'] = disp_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

        for d in dist_list:
            st.markdown(f"### 🏁 {d}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg = "#003366" if gen == "Male" else "#FFD700"
                    tc = "white" if gen == "Male" else "#003366"
                    st.markdown(f'<div style="background:{bg}; color:{tc}; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    sub = disp_df[(disp_df['distance'] == d) & (disp_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, row in leaders.sort_values('Category').iterrows():
                            opacity = "1.0" if row['name'] in active_names else "0.5"
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">{row['Category']}</span><b>{row['name']}</b><br><small>{row['location']}</small></div>
                                <div style="font-weight:bold; color:#003366;">{row['time_display']}</div></div>''', unsafe_allow_html=True)

if is_admin:
    with tab2: # SUBMISSIONS & MANUAL ADD
        st.subheader("⚡ Quick Manual PB Entry")
        with st.form("manual_add_form"):
            c1, c2, c3 = st.columns(3)
            n = c1.selectbox("Member", sorted([m['name'] for m in members_data]))
            d = c2.selectbox("Distance", dist_list)
            t = c3.text_input("Time (HH:MM:SS)")
            loc = st.text_input("Race Name")
            rd = st.date_input("Race Date")
            if st.form_submit_button("Save Record"):
                matched = next(m for m in members_data if m['name'] == n)
                if not is_duplicate_pb(n, str(rd)):
                    entry = {"name": n, "gender": matched['gender'], "dob": matched['dob'], "distance": d, "time_seconds": time_to_seconds(t), "time_display": format_time_string(t), "location": loc, "race_date": str(rd)}
                    r.rpush("race_results", json.dumps(entry))
                    st.success(f"Saved {n}"); st.rerun()

        st.divider()
        st.subheader("📋 Pending PB Approvals")
        pending = r.lrange("pending_results", 0, -1)
        if not pending:
            st.info("No pending results to review.")
        else:
            for i, p_json in enumerate(pending):
                p = json.loads(p_json)
                with st.expander(f"Review: {p['name']} ({p['distance']})"):
                    matched = next((m for m in members_data if m['name'] == p['name']), None)
                    if matched:
                        if st.button("✅ Approve", key=f"p_app_{i}"):
                            entry = {"name": p['name'], "gender": matched['gender'], "dob": matched['dob'], "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']), "time_display": format_time_string(p['time_display']), "location": p['location'], "race_date": str(p['race_date'])}
                            r.rpush("race_results", json.dumps(entry)); r.lrem("pending_results", 1, p_json); st.rerun()
                    else: st.error("Member not found. Add them to 'Members' tab first.")
                    if st.button("❌ Reject", key=f"p_rej_{i}"):
                        r.lrem("pending_results", 1, p_json); st.rerun()

    with tab3: # RACE LOG
        st.subheader("📋 Manage Records")
        all_results = r.lrange("race_results", 0, -1)
        for idx, val in enumerate(all_results):
            item = json.loads(val)
            st_key = f"edit_state_{idx}"
            with st.container(border=True):
                c1, c2, c3 = st.columns([3,1,1])
                c1.write(f"**{item['name']}** - {item['distance']} - {item['time_display']} ({item['race_date']})")
                if c2.button("📝 Edit", key=f"ebtn_{idx}"): st.session_state[st_key] = True
                if c3.button("🗑️", key=f"dbtn_{idx}"):
                    r.lset("race_results", idx, "WIPE"); r.lrem("race_results", 1, "WIPE"); st.rerun()
                if st.session_state.get(st_key):
                    with st.form(f"edit_f_{idx}"):
                        nt = st.text_input("Time", item['time_display'])
                        nd = st.text_input("Date", item['race_date'])
                        if st.form_submit_button("Confirm"):
                            item['time_display'], item['race_date'] = format_time_string(nt), nd
                            item['time_seconds'] = time_to_seconds(nt)
                            r.lset("race_results", idx, json.dumps(item))
                            st.session_state[st_key] = False; st.rerun()

    with tab4: # MEMBERS
        st.subheader("👥 Member Database")
        for i, m_json in enumerate(r.lrange("members", 0, -1)):
            m = json.loads(m_json)
            m_k = f"m_st_{i}"
            with st.container(border=True):
                c1, c2, c3 = st.columns([3,1,1])
                c1.write(f"**{m['name']}** - {m.get('status', 'Active')}")
                if c2.button("Toggle Status", key=f"mt_{i}"):
                    m['status'] = "Left" if m.get('status', 'Active') == "Active" else "Active"
                    r.lset("members", i, json.dumps(m)); st.rerun()
                if c3.button("Edit", key=f"me_{i}"): st.session_state[m_k] = True
                if st.session_state.get(m_k):
                    with st.form(f"mf_{i}"):
                        un = st.text_input("Name", m['name'])
                        ud = st.text_input("DOB", m.get('dob',''))
                        ug = st.selectbox("Gender", ["Male", "Female"], index=0 if m['gender']=="Male" else 1)
                        if st.form_submit_button("Save"):
                            m.update({"name": un, "dob": ud, "gender": ug})
                            r.lset("members", i, json.dumps(m))
                            st.session_state[m_k] = False; st.rerun()

    with tab5: # CHAMPIONSHIP
        st.subheader("🏅 Championship Admin")
        ced, capp, cstand = st.tabs(["Calendar", "Approvals", "Points"])
        with ced:
            cal = json.loads(r.get("champ_calendar_2026") or "[]")
            if not cal: cal = [{"date": "TBC", "name": "TBC", "distance": "TBC", "terrain": "Road"} for _ in range(15)]
            up_cal = []
            for i, ra in enumerate(cal):
                with st.expander(f"Race {i+1}: {ra['name']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    up_cal.append({"date": c1.text_input("Date", ra['date'], key=f"chd{i}"), "name": c2.text_input("Name", ra['name'], key=f"chn{i}"), "distance": c3.text_input("Dist", ra['distance'], key=f"chdi{i}"), "terrain": c4.selectbox("Type", ["Road", "Trail", "XC"], key=f"cht{i}")})
            if st.button("Save Cal"): r.set("champ_calendar_2026", json.dumps(up_cal)); st.rerun()
        with capp:
            st.subheader("Pending Points")
            c_p = r.lrange("champ_pending", 0, -1)
            for i, cj in enumerate(c_p):
                cp = json.loads(cj)
                st.write(f"**{cp['name']}** - {cp['race_name']}")
                win_t = st.text_input("Winner Time", key=f"cw_{i}")
                if st.button("Approve Points", key=f"ca_{i}"):
                    pts = round((time_to_seconds(win_t) / time_to_seconds(cp['time_display'])) * 100, 1)
                    r.rpush("champ_results_final", json.dumps({"name": cp['name'], "race": cp['race_name'], "points": pts, "date": cp['date']}))
                    r.lrem("champ_pending", 1, cj); st.rerun()

    with tab6: # SYSTEM
        st.subheader("⚙️ Tools")
        mf = st.file_uploader("Upload Members CSV", type="csv")
        if mf and st.button("Import"):
            for _, row in pd.read_csv(mf).iterrows(): r.rpush("members", json.dumps({"name": str(row['name']), "gender": str(row['gender']), "dob": str(row['dob']), "status": "Active"}))
            st.success("Done"); st.rerun()
