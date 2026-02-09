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

# --- AUTHENTICATION ---
users_df = get_user_data()
credentials = {"usernames": {}}

for _, row in users_df.iterrows():
    credentials["usernames"][row['username']] = {
        "name": row['name'],
        "password": str(row['password']) # Note: In production, use hashed passwords
    }

authenticator = stauth.Authenticate(credentials, "ramadan_tracker", "auth_key", cookie_expiry_days=30)

# --- MAIN UI ---
tab_login, tab_signup = st.sidebar.tabs(["Login", "Sign Up"])

with tab_signup:
    st.subheader("নতুন অ্যাকাউন্ট")
    new_name = st.text_input("আপনার নাম")
    new_user = st.text_input("ইউজারনেম (Unique)")
    new_pass = st.text_input("পাসওয়ার্ড", type="password")
    
    if st.button("রেজিস্ট্রেশন করুন"):
        if new_user in credentials["usernames"]:
            st.error("এই ইউজারনেমটি ইতিমধ্যে আছে।")
        else:
            # 1. Update Users Sheet
            new_user_row = pd.DataFrame([{"username": new_user, "name": new_name, "password": new_pass}])
            updated_users = pd.concat([users_df, new_user_row], ignore_index=True)
            conn.update(worksheet="Users", data=updated_users)
            
            # 2. Create 30 days of tasks for them
            new_entries = initialize_user_entries(new_user)
            all_entries = pd.concat([get_entry_data(), new_entries], ignore_index=True)
            conn.update(worksheet="Entries", data=all_entries)
            
            st.success("রেজিস্ট্রেশন সফল! এখন লগইন করুন।")

with tab_login:
    name, authentication_status, username = authenticator.login("main")

if authentication_status:
    authenticator.logout('Logout', 'sidebar')
    st.title(f"🌙 আসসালামু আলাইকুম, {name}!")
    
    # LOAD AND FILTER DATA
    entries_df = get_entry_data()
    user_entries = entries_df[entries_df['username'] == username].copy()
    
    # TRANSFORM DATA FOR HORIZONTAL VIEW (Pivoting like Excel)
    # We want tasks as rows and Dates as columns
    grid_df = user_entries.pivot_table(
        index=['category', 'task'], 
        columns='date', 
        values='status', 
        aggfunc='first'
    ).reset_index()

    st.subheader("আপনার ৩০ দিনের আমলনামা (Ramadan 2026)")
    
    # INTERACTIVE GRID
    edited_grid = st.data_editor(
        grid_df,
        column_config={date: st.column_config.CheckboxColumn(date[5:]) for date in grid_df.columns if '-' in date},
        disabled=["category", "task"],
        hide_index=True
    )

    if st.button("Save My Progress"):
        # Reverse Pivot to save back to "Flat" Google Sheet format
        updated_user_entries = edited_grid.melt(
            id_vars=['category', 'task'], 
            var_name='date', 
            value_name='status'
        )
        updated_user_entries['username'] = username
        
        # Merge back with other users' data
        other_users_entries = entries_df[entries_df['username'] != username]
        final_df = pd.concat([other_users_entries, updated_user_entries], ignore_index=True)
        
        conn.update(worksheet="Entries", data=final_df)
        st.success("আপনার প্রগতি সেভ করা হয়েছে!")

elif authentication_status == False:
    st.error('ইউজারনেম অথবা পাসওয়ার্ড ভুল।')
