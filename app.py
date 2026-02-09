import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import streamlit_authenticator as stauth
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Ramadan Tracker 2026", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNCTIONS ---
def get_user_data():
    return conn.read(worksheet="Users", ttl=0)

def get_entry_data():
    df = conn.read(worksheet="Entries", ttl=0)
    # CRITICAL FIX: Convert numeric 0/1 to Boolean True/False
    # This prevents the StreamlitAPIException
    df['status'] = df['status'].astype(bool)
    return df

def initialize_user_entries(username):
    tasks = [
        ("সেহরি ও ফজর", "তাহাজ্জুদ সালাত"), ("সেহরি ও ফজর", "সেহরি গ্রহণ"),
        ("সেহরি ও ফজর", "ফজরের সালাত"), ("সেহরি ও ফজর", "কুরআন তিলাওয়াত"),
        ("যোহরের সময়", "যোহরের সালাত"), ("যোহরের সময়", "জিকির ও দোয়া"),
        ("আসরের সময়", "আসরের সালাত"), ("মাগরিব ও ইফতার", "ইফতার ও দোয়া"),
        ("মাগরিব ও ইফতার", "মাগরিবের সালাত"), ("এশা ও তারাবীহ", "এশার সালাত"),
        ("এশা ও তারাবীহ", "তারাবীহ সালাত"), ("এশা ও তারাবীহ", "বিতর ও তওবা")
    ]
    start_date = datetime(2026, 2, 18)
    new_rows = []
    for i in range(30):
        current_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for cat, task in tasks:
            new_rows.append({
                "username": username, "date": current_date,
                "category": cat, "task": task, "status": False
            })
    return pd.DataFrame(new_rows)

# --- AUTHENTICATION SETUP ---
users_df = get_user_data()
credentials = {"usernames": {}}

for _, row in users_df.iterrows():
    credentials["usernames"][str(row['username'])] = {
        "name": str(row['name']),
        "password": str(row['password'])
    }

authenticator = stauth.Authenticate(
    credentials, 
    "ramadan_tracker_cookie", 
    "abcdef", 
    cookie_expiry_days=30
)

# --- SIDEBAR FOR SIGNUP ---
st.sidebar.title("Ramadan App")
with st.sidebar.expander("Register New User"):
    new_name = st.text_input("আপনার নাম")
    new_user = st.text_input("ইউজারনেম")
    new_pass = st.text_input("পাসওয়ার্ড", type="password")
    
    if st.button("রেজিস্ট্রেশন করুন"):
        if new_user in credentials["usernames"]:
            st.error("ইউজারনেম ইতিমধ্যে আছে।")
        else:
            new_user_row = pd.DataFrame([{"username": new_user, "name": new_name, "password": new_pass}])
            updated_users = pd.concat([users_df, new_user_row], ignore_index=True)
            conn.update(worksheet="Users", data=updated_users)
            
            new_entries = initialize_user_entries(new_user)
            existing_entries = get_entry_data()
            final_entries = pd.concat([existing_entries, new_entries], ignore_index=True)
            conn.update(worksheet="Entries", data=final_entries)
            st.success("রেজিস্ট্রেশন সফল! এখন লগইন করুন।")

# --- LOGIN LOGIC ---
authenticator.login(location='main')

if st.session_state["authentication_status"]:
    authenticator.logout('Logout', 'sidebar')
    curr_name = st.session_state["name"]
    curr_username = st.session_state["username"]
    
    st.title(f"🌙 আসসালামু আলাইকুম, {curr_name}!")
    
    # 1. LOAD AND FILTER DATA
    entries_df = get_entry_data()
    user_entries = entries_df[entries_df['username'] == curr_username].copy()
    
    if user_entries.empty:
        st.warning("আপনার কোন ডাটা পাওয়া যায়নি।")
    else:
        # 2. CREATE THE GRID (Pivoting)
        grid_df = user_entries.pivot_table(
            index=['category', 'task'], 
            columns='date', 
            values='status', 
            aggfunc='first'
        ).reset_index()

        st.subheader("আপনার ৩০ দিনের আমলনামা")
        
        # 3. INTERACTIVE DATA EDITOR
        # Ensure all dynamic date columns are also treated as bool
        col_config = {
            "category": "বিভাগ",
            "task": "আমল"
        }
        for col in grid_df.columns:
            if '-' in str(col):
                col_config[col] = st.column_config.CheckboxColumn(str(col)[8:10])

        edited_grid = st.data_editor(
            grid_df,
            column_config=col_config,
            disabled=["category", "task"],
            hide_index=True
        )

        # 4. SAVE BACK TO GOOGLE DRIVE
        if st.button("Save Changes"):
            updated_user_entries = edited_grid.melt(
                id_vars=['category', 'task'], 
                var_name='date', 
                value_name='status'
            )
            updated_user_entries['username'] = curr_username
            
            # Convert status back to integer for clean saving in Google Sheets
            updated_user_entries['status'] = updated_user_entries['status'].astype(int)
            
            other_users_entries = entries_df[entries_df['username'] != curr_username]
            other_users_entries['status'] = other_users_entries['status'].astype(int)
            
            final_save_df = pd.concat([other_users_entries, updated_user_entries], ignore_index=True)
            
            conn.update(worksheet="Entries", data=final_save_df)
            st.success("আপনার প্রগতি সেভ করা হয়েছে!")

elif st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.info('অনুগ্রহ করে লগইন করুন।')
