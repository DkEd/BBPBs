import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime, date

# --- CONFIG & CONNECTION ---
st.set_page_config(page_title="Club Leaderboard", layout="wide")

# Connect to Upstash Redis
redis_url = os.environ.get("REDIS_URL")
try:
    r = redis.from_url(redis_url, decode_responses=True)
except Exception as e:
    st.error(f"Redis Connection Failed: {e}")

# --- HELPER FUNCTIONS ---
def get_admin_password():
    stored_pwd = r.get("admin_password")
    return stored_pwd if stored_pwd else "admin123"

def get_club_logo():
    stored_logo = r.get("club_logo_url")
    default_logo = "https://scontent-lhr6-2.xx.fbcdn.net/v/t39.30808-6/613136946_122094772515215234_2783950400659519915_n.jpg?_nc_cat=105&ccb=1-7&_nc_sid=cc71e4&_nc_ohc=kvHoy9QIOF4Q7kNvwGRAj6K&_nc_oc=Adm0NLaoEHZoixq2SnIjN_KH-Zfwbqu11R1pz8aAV3sMB2Ru2wRsi3H4j7cerOPAUmGOmUh3Q6dC7TWGA82mWYDi&_nc_zt=23&_nc_ht=scontent-lhr6-2.xx&_nc_gid=5GS-5P76DuiR2umpX-xI5w&oh=00_AfquWT54_DxkPrvTyRnSk2y3a3tBuCxJBvkLCS8rd7ANlg&oe=696A8E3D"
    return stored_logo if stored_logo else default_logo

def get_category(dob_str, race_date_str):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d')
        race_date = datetime.strptime(race_date_str, '%Y-%m-%d')
        age = race_date.year - dob.year - ((race_date.month, race_date.day) < (dob.month, dob.day))
        if age < 40: return "Senior"
        if age < 50: return "V40"
        if age < 60: return "V50"
        if age < 70: return "V60"
        return "V70"
    except: return "Unknown"

def time_to_seconds(t_str):
    try:
        parts = list(map(int, t_str.split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2: return parts[0] * 60 + parts[1]
    except: return None

# --- HEADER & LOGO ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(get_club_logo(), width=120)
with col_title:
    st.markdown('<h1 style="color: #003366; margin-top: 10px;">Club Leaderboard</h1>', unsafe_allow_html=True)

# --- SIDEBAR ADMIN ---
with st.sidebar:
    st.markdown('<h2 style="color: #003366;">🔐 Admin Login</h2>', unsafe_allow_html=True)
    current_pwd = get_admin_password()
    pwd_input = st.text_input("Password", type="password")
    is_admin = (pwd_input == current_pwd)
    
    if is_admin:
        st.success("Admin Access Granted")
        st.divider()
        new_pwd = st.text_input("New Password", type="password")
        if st.button("Save New Password"):
            if new_pwd:
                r.set("admin_password", new_pwd)
                st.success("Updated!")
                st.rerun()

# --- MAIN UI TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Leaderboards", "⏱️ Activity", "👤 Members", "🛠️ Admin", "👁️ View Controller"])

all_distances = ["5k", "10k", "10 Mile", "HM", "Marathon"]

# --- TAB 5: VIEW CONTROLLER ---
with tab5:
    st.header("👁️ Board Visibility Settings")
    st.write("Toggle which distances appear on the public **🏆 Leaderboards** tab.")
    
    # Store settings in Redis so they persist
    stored_visibility = r.get("visible_distances")
    default_visibility = all_distances if not stored_visibility else json.loads(stored_visibility)
    
    visible_list = []
    cols = st.columns(len(all_distances))
    for i, dist in enumerate(all_distances):
        with cols[i]:
            if st.checkbox(dist, value=(dist in default_visibility)):
                visible_list.append(dist)
    
    if st.button("Save Visibility Settings"):
        r.set("visible_distances", json.dumps(visible_list))
        st.success("Leaderboard updated!")
        st.rerun()

    st.divider()
    st.subheader("📋 Master Leaderboard (Full Version)")
    st.caption("This section always shows all recorded distances for admin review.")
    
    raw_results = r.lrange("race_results", 0, -1)
    if raw_results:
        master_df = pd.DataFrame([json.loads(res) for res in raw_results])
        st.dataframe(master_df.sort_values(['distance', 'time_seconds']), use_container_width=True, hide_index=True)

# --- TAB 1: PUBLIC LEADERBOARD ---
with tab1:
    current_year = datetime.now().year
    years = ["All-Time"] + [str(y) for y in range(2023, current_year + 1)]
    col_filter, _ = st.columns([1, 2])
    with col_filter:
        selected_year = st.selectbox("📅 Select Season:", years, index=0)
    
    # Determine which distances to show
    stored_visibility = r.get("visible_distances")
    active_distances = json.loads(stored_visibility) if stored_visibility else all_distances

    raw_results = r.lrange("race_results", 0, -1)
    if raw_results:
        df = pd.DataFrame([json.loads(res) for res in raw_results])
        df['race_date_dt'] = pd.to_datetime(df['race_date'])
        
        if selected_year != "All-Time":
            df = df[df['race_date_dt'].dt.year == int(selected_year)]
        
        if not df.empty:
            df['Category'] = df.apply(lambda x: get_category(x['dob'], x['race_date']), axis=1)
            cat_order = ["Senior", "V40", "V50", "V60", "V70"]
            
            for d in active_distances:
                st.markdown(f"### 🏁 {d} Records - {selected_year}")
                m_col, f_col = st.columns(2)
                for gen, col in [("Male", m_col), ("Female", f_col)]:
                    with col:
                        header_bg, text_color = ("#003366", "white") if gen == "Male" else ("#FFD700", "#003366")
                        st.markdown(f'<div style="background-color: {header_bg}; padding: 10px; border-radius: 8px 8px 0px 0px; color: {text_color}; text-align: center; font-weight: 800; border: 2px solid #003366;">{gen.upper()}</div>', unsafe_allow_html=True)
                        subset = df[(df['distance'] == d) & (df['gender'] == gen)]
                        if not subset.empty:
                            leaders = subset.sort_values('time_seconds').groupby('Category', observed=True).head(1)
                            leaders['Category'] = pd.Categorical(leaders['Category'], categories=cat_order, ordered=True)
                            for _, row in leaders.sort_values('Category').iterrows():
                                st.markdown(f'''<div style="border: 2px solid #003366; border-top: none; padding: 12px; background-color: white; margin-bottom: -2px; display: flex; justify-content: space-between; align-items: center;"><div style="line-height: 1.2;"><span style="background-color: #FFD700; color: #003366; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.75em; margin-right: 8px;">{row['Category']}</span><span style="font-weight: 600; color: #003366; font-size: 1.05em;">{row['name']}</span><br><span style="font-size: 0.75em; color: #666;">{row['location']} | {row['race_date']}</span></div><div style="font-weight: 800; color: #003366; font-size: 1.2em; border-left: 2px solid #FFD700; padding-left: 10px;">{row['time_display']}</div></div>''', unsafe_allow_html=True)
                        else: st.markdown('<div style="border: 2px solid #003366; border-top: none; padding: 10px; text-align: center; color: #999; font-style: italic; font-size: 0.8em;">No records recorded</div>', unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
    else: st.info("Database is empty.")

# --- TAB 2: ACTIVITY ---
with tab2:
    st.header("Recent Race Activity")
    if raw_results:
        all_df = pd.DataFrame([json.loads(res) for res in raw_results]).sort_values('race_date', ascending=False)
        st.dataframe(all_df[['race_date', 'name', 'distance', 'time_display', 'location']], use_container_width=True, hide_index=True)

# --- TAB 3: MEMBERS ---
with tab3:
    if is_admin:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Register Member")
            with st.form("mem_form", clear_on_submit=True):
                n = st.text_input("Full Name")
                g = st.selectbox("Gender", ["Male", "Female"])
                b = st.date_input("DOB", value=date(1990, 1, 1))
                if st.form_submit_button("Save Member"):
                    if n: r.rpush("members", json.dumps({"name":n, "gender":g, "dob":str(b)}))
                    st.rerun()
        with col2:
            st.subheader("Member List")
            m_raw = r.lrange("members", 0, -1)
            if m_raw:
                m_list = [json.loads(m) for m in m_raw]
                st.dataframe(pd.DataFrame(m_list).sort_values('name'), use_container_width=True, hide_index=True)

# --- TAB 4: ADMIN (Wipe/Import) ---
with tab4:
    if is_admin:
        st.header("🛠️ Admin Tools")
        m_file = st.file_uploader("Upload Members CSV", type="csv")
        if m_file and st.button("🚀 Import Members"):
            m_df = pd.read_csv(m_file)
            for _, row in m_df.iterrows():
                r.rpush("members", json.dumps({"name": str(row['name']), "gender": str(row['gender']), "dob": str(row['dob'])}))
            st.success("Imported!")
            
        r_file = st.file_uploader("Upload Results CSV", type="csv")
        if r_file and st.button("💾 Import Results"):
            r_df = pd.read_csv(r_file)
            m_lookup = {json.loads(m)['name']: json.loads(m) for m in r.lrange("members", 0, -1)}
            for _, row in r_df.iterrows():
                if str(row['name']) in m_lookup:
                    m = m_lookup[str(row['name'])]
                    entry = {"name": str(row['name']), "gender": m['gender'], "dob": m['dob'], "distance": str(row['distance']), "time_seconds": time_to_seconds(str(row['time_display'])), "time_display": str(row['time_display']), "location": str(row['location']), "race_date": str(row['race_date'])}
                    r.rpush("race_results", json.dumps(entry))
            st.success("Saved!")
            st.rerun()
            
        if st.button("🗑️ Wipe All Results"):
            r.delete("race_results")
            st.rerun()
    else: st.error("Admin Login Required")
