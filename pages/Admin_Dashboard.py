import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import hashlib

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Admin Dashboard")
DATE_FORMAT = "%Y-%m-%d"
SUBSCRIPTION_PLANS = {
    "₹100 for 30 days (Normal)": 30,
    "₹550 for 6 months (Advance)": 182,
    "₹1000 for 1 year (Advance)": 365
}

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
    TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(_sheet):
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    return pd.DataFrame(all_values[1:], columns=all_values[0])

def save_data(df, sheet):
    df_str = df.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "admin":
    st.error("You must be logged in as an Admin to view this page.")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === ADMIN DASHBOARD UI ===
st.header("👑 Admin Panel")

tab1, tab2 = st.tabs(["Student Management", "Teacher Management"])

with tab1:
    st.subheader("Manage Student Registrations")
    df_students = load_data(STUDENT_SHEET)
    
    st.markdown("#### Pending Payment Confirmations")
    unconfirmed_students = df_students[df_students.get("Payment Confirmed") != "Yes"]
    if unconfirmed_students.empty:
        st.info("No pending student payments.")
    else:
        for index, row in unconfirmed_students.iterrows():
            st.write(f"**Name:** {row.get('Student Name')} | **Plan:** {row.get('Subscription Plan')}")
            if st.button(f"✅ Confirm Payment for {row.get('Student Name')}", key=f"confirm_student_{row.get('Gmail ID')}"):
                plan_days = SUBSCRIPTION_PLANS.get(row.get("Subscription Plan"), 30)
                today = datetime.today()
                till_date = (today + timedelta(days=plan_days)).strftime(DATE_FORMAT)
                
                df_students.loc[index, "Subscription Date"] = today.strftime(DATE_FORMAT)
                df_students.loc[index, "Subscribed Till"] = till_date
                df_students.loc[index, "Payment Confirmed"] = "Yes"
                
                save_data(df_students, STUDENT_SHEET)
                st.success(f"Payment confirmed for {row.get('Student Name')}.")
                st.rerun()

    st.markdown("---")
    st.markdown("#### Confirmed Students")
    confirmed_students = df_students[df_students.get("Payment Confirmed") == "Yes"]
    st.dataframe(confirmed_students)

with tab2:
    st.subheader("Manage Teacher Registrations")
    df_teachers = load_data(TEACHER_SHEET)

    st.markdown("#### Pending Teacher Confirmations")
    unconfirmed_teachers = df_teachers[df_teachers.get("Confirmed") != "Yes"]
    if unconfirmed_teachers.empty:
        st.info("No pending teacher confirmations.")
    else:
        for index, row in unconfirmed_teachers.iterrows():
            st.write(f"**Name:** {row.get('Teacher Name')} | **Gmail:** {row.get('Gmail ID')}")
            if st.button(f"✅ Confirm Teacher: {row.get('Teacher Name')}", key=f"confirm_teacher_{row.get('Gmail ID')}"):
                df_teachers.loc[index, "Confirmed"] = "Yes"
                save_data(df_teachers, TEACHER_SHEET)
                st.success(f"Teacher {row.get('Teacher Name')} confirmed.")
                st.rerun()

    st.markdown("---")
    st.markdown("#### Confirmed Teachers")
    confirmed_teachers = df_teachers[df_teachers.get("Confirmed") == "Yes"]
    st.dataframe(confirmed_teachers)
