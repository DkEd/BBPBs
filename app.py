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

# --- 2. GLOBAL HELPERS (Fixed & Verified) ---
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
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        return 999999
    except:
        return 999999

def get_club_logo():
    stored = r.get("club_logo_url")
    return stored if (stored and stored.startswith("http")) else "https://cdn-icons-png.flaticon.com/512/55/55281.png"

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

# --- 3. SIDEBAR & VISIBILITY ---
with st.sidebar:
    st.image(get_club_logo(), width=150)
    st.markdown("### 🔒 Admin Access")
    pwd_input = st.text_input("Password", type="password")
    admin_pwd = r.get("admin_password") or "admin123"
    is_admin = (pwd_input == admin_pwd)
    
    if is_admin:
        st.success("Admin Authenticated")
        st.divider()
        st.markdown("### 👁️ Public Visibility")
        current_toggle = r.get("show_champ_tab") == "True"
        champ_visible = st.toggle("Show Champ Tab on BBPB", value=current_toggle)
        if st.button("Save Visibility Settings"):
            r.set("show_champ_tab", str(champ_visible))
            st.success("Settings Updated")

    st.divider()
    raw_mem = r.lrange("members", 0, -1)
    members_data = [json.loads(m) for m in raw_mem]
    if st.button("🔄 Force Refresh Data"): st.rerun()

# --- 4. MAIN TABS ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏆 Leaderboard", "📥 Submissions", "📋 Race Log", "👥 Members", "🏅 Championship", "⚙️ System"
])

all_dist = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 1: LEADERBOARD ---
with tab1:
    raw_res = r.lrange("race_results", 0, -1)
    active_names = [m['name'] for m in members_data if m.get('status', 'Active') == 'Active']
    
    if raw_res:
        df = pd.DataFrame([json.loads(res) for res in raw_res])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        years = ["All-Time"] + sorted([str(y) for y in df['race_date_dt'].dt.year.unique()], reverse=True)
        sel_year = st.selectbox("Season Selection:", years)
        
        display_df = df.copy()
        if sel_year != "All-Time":
            display_df = display_df[display_df['race_date_dt'].dt.year == int(sel_year)]
            
        age_mode = r.get("age_mode") or "10Y"
        display_df['Category'] = display_df.apply(lambda x: get_category(x['dob'], x['race_date'], age_mode), axis=1)

        for d in all_dist:
            st.markdown(f"### 🏁 {d}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg, tc = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                    st.markdown(f'<div style="background:{bg}; color:{tc}; padding:8px; border-radius:8px 8px 0 0; text-align:center; font-weight:bold; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    sub = display_df[(display_df['distance'] == d) & (display_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for _, row in leaders.sort_values('Category').iterrows():
                            opacity = "1.0" if row['name'] in active_names else "0.5"
                            st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:10px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                                <div><span style="background:#FFD700; color:#003366; padding:2px 5px; border-radius:3px; font-weight:bold; font-size:0.75em; margin-right:5px;">{row['Category']}</span><b>{row['name']}</b><br><small>{row['location']}</small></div>
                                <div style="font-weight:bold; color:#003366;">{row['time_display']}</div></div>''', unsafe_allow_html=True)

if is_admin:
    with tab2: # SUBMISSIONS
        st.subheader("⚡ Manual Entry & Approvals")
        with st.form("manual_entry"):
            c1, c2, c3 = st.columns(3)
            name_sel = c1.selectbox("Member", sorted([m['name'] for m in members_data]))
            dist_sel = c2.selectbox("Distance", all_dist)
            time_in = c3.text_input("Time (HH:MM:SS)")
            loc_in = st.text_input("Race Name")
            date_in = st.date_input("Race Date")
            if st.form_submit_button("Direct Add"):
                match = next(m for m in members_data if m['name'] == name_sel)
                entry = {"name": name_sel, "gender": match['gender'], "dob": match['dob'], "distance": dist_sel, "time_seconds": time_to_seconds(time_in), "time_display": format_time_string(time_in), "location": loc_in, "race_date": str(date_in)}
                r.rpush("race_results", json.dumps(entry)); st.success("Saved"); st.rerun()

        st.divider()
        st.subheader("📋 Pending PB Approvals")
        pending = r.lrange("pending_results", 0, -1)
        if pending:
            for i, p_json in enumerate(pending):
                p = json.loads(p_json)
                with st.expander(f"Review: {p['name']} - {p['distance']}"):
                    match = next((m for m in members_data if m['name'] == p['name']), None)
                    if match:
                        if st.button("✅ Approve", key=f"app_{i}"):
                            entry = {"name": p['name'], "gender": match['gender'], "dob": match['dob'], "distance": p['distance'], "time_seconds": time_to_seconds(p['time_display']), "time_display": format_time_string(p['time_display']), "location": p['location'], "race_date": p['race_date']}
                            r.rpush("race_results", json.dumps(entry)); r.lrem("pending_results", 1, p_json); st.rerun()
                    if st.button("❌ Reject", key=f"rej_{i}"): r.lrem("pending_results", 1, p_json); st.rerun()

    with tab3: # RACE LOG
        st.subheader("📋 Master Record Management")
        results = r.lrange("race_results", 0, -1)
        for idx, val in enumerate(results):
            item = json.loads(val)
            key_st = f"edit_log_{idx}"
            with st.container(border=True):
                c1, c2, c3 = st.columns([4,1,1])
                c1.write(f"**{item['name']}** | {item['distance']} | {item['time_display']} | {item['race_date']}")
                if c2.button("Edit", key=f"edit_l_{idx}"): st.session_state[key_st] = True
                if c3.button("🗑️", key=f"del_l_{idx}"):
                    r.lset("race_results", idx, "WIPE"); r.lrem("race_results", 1, "WIPE"); st.rerun()
                if st.session_state.get(key_st):
                    with st.form(f"form_l_{idx}"):
                        nt, nd = st.text_input("Time", item['time_display']), st.text_input("Date", item['race_date'])
                        if st.form_submit_button("Update"):
                            item.update({"time_display": format_time_string(nt), "race_date": nd, "time_seconds": time_to_seconds(nt)})
                            r.lset("race_results", idx, json.dumps(item)); st.session_state[key_st] = False; st.rerun()

    with tab4: # MEMBERS
        st.subheader("👥 Members")
        for i, m_json in enumerate(r.lrange("members", 0, -1)):
            m = json.loads(m_json)
            m_st = f"edit_mem_{i}"
            with st.container(border=True):
                c1, c2, c3 = st.columns([3,1,1])
                c1.write(f"**{m['name']}** - {m.get('status', 'Active')}")
                if c2.button("Toggle Status", key=f"tog_m_{i}"):
                    m['status'] = "Left" if m.get('status', 'Active') == "Active" else "Active"
                    r.lset("members", i, json.dumps(m)); st.rerun()
                if c3.button("Edit Details", key=f"edit_m_{i}"): st.session_state[m_st] = True
                if st.session_state.get(m_st):
                    with st.form(f"form_m_{i}"):
                        un, ud, ug = st.text_input("Name", m['name']), st.text_input("DOB", m['dob']), st.selectbox("Gender", ["Male", "Female"], index=0 if m['gender']=="Male" else 1)
                        if st.form_submit_button("Save"):
                            m.update({"name": un, "dob": ud, "gender": ug}); r.lset("members", i, json.dumps(m)); st.session_state[m_st] = False; st.rerun()

    with tab5: # CHAMPIONSHIP
        st.subheader("🏅 Championship")
        c1, c2, c3 = st.tabs(["Point Approvals", "Calendar", "Raw Points Log"])
        with c1:
            c_pend = r.lrange("champ_pending", 0, -1)
            for i, cj in enumerate(c_pend):
                cp = json.loads(cj)
                st.write(f"**{cp['name']}** - {cp['race_name']} ({cp['time_display']})")
                wt = st.text_input("Category Winner Time", key=f"wt_{i}")
                if st.button("Approve & Calc", key=f"c_ap_{i}"):
                    pts = round((time_to_seconds(wt) / time_to_seconds(cp['time_display'])) * 100, 1)
                    r.rpush("champ_results_final", json.dumps({"name": cp['name'], "race": cp['race_name'], "points": pts, "date": cp['date']}))
                    r.lrem("champ_pending", 1, cj); st.rerun()
        with c2:
            cal_raw = r.get("champ_calendar_2026")
            calendar = json.loads(cal_raw) if cal_raw else []
            new_cal = []
            for i in range(15):
                ra = calendar[i] if i < len(calendar) else {"date": "TBC", "name": "TBC", "distance": "TBC", "terrain": "Road"}
                with st.expander(f"Race {i+1}: {ra['name']}"):
                    d, n, dist, terr = st.text_input("Date", ra['date'], key=f"d_{i}"), st.text_input("Name", ra['name'], key=f"n_{i}"), st.text_input("Dist", ra['distance'], key=f"dist_{i}"), st.selectbox("Type", ["Road", "Trail", "Fell", "XC"], key=f"terr_{i}")
                    new_cal.append({"date": d, "name": n, "distance": dist, "terrain": terr})
            if st.button("Save Calendar"): r.set("champ_calendar_2026", json.dumps(new_cal)); st.rerun()
        with c3:
            final_raw = r.lrange("champ_results_final", 0, -1)
            if final_raw: st.dataframe(pd.DataFrame([json.loads(x) for x in final_raw]), use_container_width=True)

    with tab6: # SYSTEM (VERIFIED)
        st.subheader("⚙️ System Tools")
        c_br1, c_br2 = st.columns(2)
        with c_br1:
            logo = st.text_input("Logo URL", r.get("club_logo_url") or "")
            if st.button("Update Logo"): r.set("club_logo_url", logo); st.rerun()
        with c_br2:
            new_pwd = st.text_input("Admin Password", type="password")
            if st.button("Update Password"): r.set("admin_password", new_pwd); st.success("Changed")

        st.divider()
        st.markdown("### 🎂 Age Mode & 💾 Backups")
        cc1, cc2 = st.columns(2)
        with cc1:
            curr_mode = r.get("age_mode") or "10Y"
            new_mode = st.radio("Leaderboard Mode:", ["10Y", "5Y"], index=0 if curr_mode=="10Y" else 1, horizontal=True)
            if st.button("Save Age Mode"): r.set("age_mode", new_mode); st.success("Set")
        with cc2:
            if members_data: st.download_button("📥 Export Members", pd.DataFrame(members_data).to_csv(index=False), "members.csv", "text/csv")
            res_raw = r.lrange("race_results", 0, -1)
            if res_raw: st.download_button("📥 Export Results", pd.DataFrame([json.loads(x) for x in res_raw]).to_csv(index=False), "results.csv", "text/csv")

        st.divider()
        st.markdown("### 📤 Bulk Uploads")
        u1, u2 = st.columns(2)
        with u1:
            mf = st.file_uploader("Members CSV", type="csv")
            if mf and st.button("Import Members"):
                for _, row in pd.read_csv(mf).iterrows(): r.rpush("members", json.dumps({"name": row['name'], "gender": row['gender'], "dob": str(row['dob']), "status": "Active"}))
                st.success("Imported"); st.rerun()
        with u2:
            pf = st.file_uploader("PB CSV", type="csv")
            if pf and st.button("Import PBs"):
                m_look = {m['name']: m for m in members_data}
                for _, row in pd.read_csv(pf).iterrows():
                    if row['name'] in m_look:
                        m = m_look[row['name']]; e = {"name": row['name'], "gender": m['gender'], "dob": m['dob'], "distance": str(row['distance']), "time_seconds": time_to_seconds(row['time_display']), "time_display": format_time_string(row['time_display']), "location": row['location'], "race_date": str(row['race_date'])}
                        r.rpush("race_results", json.dumps(e))
                st.success("Imported"); st.rerun()
else:
    for t in [tab2, tab3, tab4, tab5, tab6]:
        with t: st.warning("🔒 Login in sidebar.")
