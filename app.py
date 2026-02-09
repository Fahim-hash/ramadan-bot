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
    # ttl=0 ensures we always get the latest data from Google Drive
    return conn.read(worksheet="Users", ttl=0)

def get_entry_data():
    return conn.read(worksheet="Entries", ttl=0)

def initialize_user_entries(username):
    """Creates 30 days of empty tasks for a new user"""
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
        "password": str(row['password']) # Use hashed passwords for production
    }

# New version of Authenticate
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
            # 1. Update Users Sheet
            new_user_row = pd.DataFrame([{"username": new_user, "name": new_name, "password": new_pass}])
            updated_users = pd.concat([users_df, new_user_row], ignore_index=True)
            conn.update(worksheet="Users", data=updated_users)
            
            # 2. Create 30 days of tasks for them
            new_entries = initialize_user_entries(new_user)
            existing_entries = get_entry_data()
            final_entries = pd.concat([existing_entries, new_entries], ignore_index=True)
            conn.update(worksheet="Entries", data=final_entries)
            
            st.success("রেজিস্ট্রেশন সফল! লগইন করুন।")

# --- LOGIN LOGIC ---
# The login method no longer returns 3 values in recent versions
authenticator.login(location='main')

if st.session_state["authentication_status"]:
    authenticator.logout('Logout', 'sidebar')
    
    # Access user info from session state
    curr_name = st.session_state["name"]
    curr_username = st.session_state["username"]
    
    st.title(f"🌙 আসসালামু আলাইকুম, {curr_name}!")
    
    # 1. LOAD AND FILTER DATA
    entries_df = get_entry_data()
    # Filter for the logged in user
    user_entries = entries_df[entries_df['username'] == curr_username].copy()
    
    if user_entries.empty:
        st.warning("আপনার কোন ডাটা পাওয়া যায়নি। এডমিনকে যোগাযোগ করুন।")
    else:
        # 2. CREATE THE GRID (Dates as columns)
        grid_df = user_entries.pivot_table(
            index=['category', 'task'], 
            columns='date', 
            values='status', 
            aggfunc='first'
        ).reset_index()

        st.subheader("আপনার ৩০ দিনের আমলনামা")
        
        # 3. INTERACTIVE DATA EDITOR
        edited_grid = st.data_editor(
            grid_df,
            column_config={
                date: st.column_config.CheckboxColumn(date[8:10], help=date) 
                for date in grid_df.columns if '-' in str(date)
            },
            disabled=["category", "task"],
            hide_index=True
        )

        # 4. SAVE BACK TO GOOGLE DRIVE
        if st.button("Save Changes"):
            # Transform back to 'Flat' format (Melt)
            updated_user_entries = edited_grid.melt(
                id_vars=['category', 'task'], 
                var_name='date', 
                value_name='status'
            )
            updated_user_entries['username'] = curr_username
            
            # Merge with other users' data so we don't overwrite them
            other_users_entries = entries_df[entries_df['username'] != curr_username]
            final_save_df = pd.concat([other_users_entries, updated_user_entries], ignore_index=True)
            
            conn.update(worksheet="Entries", data=final_save_df)
            st.success("আপনার প্রগতি Google Drive এ সেভ করা হয়েছে!")

elif st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.info('অনুগ্রহ করে লগইন করুন।')
