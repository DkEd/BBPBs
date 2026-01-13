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
    st.error(f"Redis Connection Failed: Check your environment variables.")

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
        else:
            if age < 40: return "Senior"
            return f"V{(age // 10) * 10}"
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

# --- TABS DEFINITION ---
# Only Leaderboard is available to the public.
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Admin", "👁️ View Controller"])

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
        unique_cats = sorted(display_df['Category'].unique(), key=lambda x: (x != 'Senior', x))

        for d in active_dist:
            st.markdown(f"### 🏁 {d} Records - {sel_year}")
            m_col, f_col = st.columns(2)
            for gen, col in [("Male", m_col), ("Female", f_col)]:
                with col:
                    bg, tx = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                    st.markdown(f'<div style="background-color:{bg}; color:{tx}; padding:10px; border-radius:8px 8px 0 0; text-align:center; font-weight:800; border:2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                    sub = display_df[(display_df['distance'] == d) & (display_df['gender'] == gen)]
                    if not sub.empty:
                        leaders = sub.sort_values('time_seconds').groupby('Category').head(1)
                        for cat in unique_cats:
                            row = leaders[leaders['Category'] == cat]
                            if not row.empty:
                                r_data = row.iloc[0]
                                st.markdown(f'''<div style="border:2px solid #003366; border-top:none; padding:12px; background:white; margin-bottom:-2px; display:flex; justify-content:space-between; align-items:center;">
                                    <div><span style="background:#FFD700; color:#003366; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em; margin-right:8px;">{r_data['Category']}</span><b>{r_data['name']}</b><br><small>{r_data['location']} | {r_data['race_date']}</small></div>
                                    <div style="font-weight:800; color:#003366; font-size:1.1em;">{r_data['time_display']}</div></div>''', unsafe_allow_html=True)
                    else: st.markdown('<div style="border:2px solid #003366; border-top:none; padding:10px; text-align:center; color:#999; font-size:0.8em;">No records</div>', unsafe_allow_html=True)
    else: st.info("Welcome to AutoKudos! The leaderboard will appear once results are uploaded.")

# --- PROTECTED TABS ---
# Tab 2 (Activity)
with tab2:
    if is_admin:
        if raw_res:
            st.header("Recent Activity")
            st.dataframe(pd.DataFrame([json.loads(res) for res in raw_res]).sort_values('race_date', ascending=False), use_container_width=True, hide_index=True)
        else: st.info("No activity recorded.")
    else: st.warning("🔒 This tab is restricted to club administrators.")

# Tab 3 (Members)
with tab3:
    if is_admin:
        raw_mem = r.lrange("members", 0, -1)
        if raw_mem:
            st.header("Member Directory")
            st.dataframe(pd.DataFrame([json.loads(m) for m in raw_mem]).sort_values('name'), use_container_width=True, hide_index=True)
        else: st.info("No members registered.")
    else: st.warning("🔒 Member data is private. Please login to view.")

# Tab 4 (Admin)
with tab4:
    if is_admin:
        st.header("🛠️ Admin Controls")
        col_m, col_r = st.columns(2)
        with col_m:
            st.subheader("1. Member Import")
            m_file = st.file_uploader("Upload Members CSV", type="csv")
            if m_file and st.button("🚀 Run Member Import"):
                m_df = pd.read_csv(m_file)
                m_df.columns = [c.lower().strip() for c in m_df.columns]
                existing_raw = r.lrange("members", 0, -1)
                existing_ids = {(json.loads(m)['name'], json.loads(m)['dob']) for m in existing_raw}
                added, skipped = 0, 0
                for _, row in m_df.iterrows():
                    n, db = str(row['name']).strip(), str(row['dob']).strip()
                    if (n, db) not in existing_ids:
                        r.rpush("members", json.dumps({"name": n, "gender": str(row['gender']).strip(), "dob": db}))
                        existing_ids.add((n, db)); added += 1
                    else: skipped += 1
                st.success(f"Added: {added} | Skipped: {skipped}"); st.rerun()

        with col_r:
            st.subheader("2. Results Import")
            r_file = st.file_uploader("Upload Results CSV", type="csv")
            if r_file and st.button("💾 Run Results Import"):
                try:
                    r_df = pd.read_csv(r_file, on_bad_lines='warn')
                    r_df.columns = [c.lower().strip() for c in r_df.columns]
                    m_lookup = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
                    res_raw = r.lrange("race_results", 0, -1)
                    existing_res = {f"{json.loads(res)['name']}|{json.loads(res)['distance']}|{json.loads(res)['time_display']}|{json.loads(res)['race_date']}" for res in res_raw}
                    added, skipped, missing = 0, 0, []
                    for _, row in r_df.iterrows():
                        n, d, t, dt = str(row['name']).strip(), str(row['distance']).strip(), str(row['time_display']).strip(), str(row['race_date']).strip()
                        fingerprint = f"{n}|{d}|{t}|{dt}"
                        if n not in m_lookup: missing.append(n)
                        elif fingerprint in existing_res: skipped += 1
                        else:
                            m = m_lookup[n]
                            entry = {"name": n, "gender": m['gender'], "dob": m['dob'], "distance": d, "time_seconds": time_to_seconds(t), "time_display": t, "location": str(row['location']).strip(), "race_date": dt}
                            r.rpush("race_results", json.dumps(entry))
                            existing_res.add(fingerprint); added += 1
                    if missing: st.warning(f"Skipped unregistered: {', '.join(set(missing))}")
                    st.success(f"Added: {added} | Skipped Duplicates: {skipped}"); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        st.divider()
        if st.button("🗑️ Wipe All Results"): r.delete("race_results"); st.rerun()
        if st.button("👥 Wipe All Members"): r.delete("members"); st.rerun()
    else: st.warning("🔒 Admin Login Required.")

# Tab 5 (View Controller)
with tab5:
    if is_admin:
        st.header("👁️ View Controller")
        stored_vis = r.get("visible_distances")
        default_vis = all_distances if not stored_vis else json.loads(stored_vis)
        st.subheader("Leaderboard Visibility")
        cols = st.columns(len(all_distances))
        visible_list = []
        for i, dist in enumerate(all_distances):
            if cols[i].checkbox(dist, value=(dist in default_vis), key=f"v_{dist}"):
                visible_list.append(dist)
        st.divider()
        stored_mode = r.get("age_mode") or "10Y"
        age_choice = st.radio("Age Grouping:", ["10 Years", "5 Years"], index=0 if stored_mode == "10Y" else 1)
        if st.button("Save View Settings"):
            r.set("visible_distances", json.dumps(visible_list))
            r.set("age_mode", "10Y" if "10" in age_choice else "5Y")
            st.success("Updated!"); st.rerun()
    else: st.warning("🔒 Admin Login Required.")
