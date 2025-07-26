import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import hashlib

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition - Login")
DATE_FORMAT = "%Y-%m-%d"
SUBSCRIPTION_PLANS = {
    "₹100 for 30 days (Normal)": 30,
    "₹550 for 6 months (Advance)": 182,
    "₹1000 for 1 year (Advance)": 365
}
UPI_ID = "9685840429@pnb"

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
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

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

def find_user(gmail):
    df_students = load_data(STUDENT_SHEET)
    user_in_students = df_students[df_students['Gmail ID'] == gmail]
    if not user_in_students.empty:
        return user_in_students.iloc[0]

    df_teachers = load_data(TEACHER_SHEET)
    user_in_teachers = df_teachers[df_teachers['Gmail ID'] == gmail]
    if not user_in_teachers.empty:
        return user_in_teachers.iloc[0]

    return None

# === SESSION STATE ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""

# --- Hide sidebar page navigation ---
st.markdown("<style> [data-testid='stSidebarNav'] {display: none;} </style>", unsafe_allow_html=True)

# === LOGIN / REGISTRATION PAGE ===
if not st.session_state.logged_in:
    st.sidebar.title("Login / New Registration")
    # (Your logo code can be placed here)
    st.markdown("---")
    
    option = st.sidebar.radio("Select an option:", ["Login", "New Registration"])

    if option == "New Registration":
        st.header("✍️ New Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            with st.form("student_registration_form", clear_on_submit=True):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
                pwd = st.text_input("Password", type="password")
                plan = st.selectbox("Choose Subscription Plan", list(SUBSCRIPTION_PLANS.keys()))
                st.info(f"Please pay {plan.split(' ')[0]} to the UPI ID below.")
                st.code(f"UPI: {UPI_ID}", language="text")
                if st.form_submit_button("Register (After Payment)"):
                    if not all([name, gmail, cls, pwd, plan]):
                        st.warning("Please fill in all details.")
                    else:
                        df = load_data(STUDENT_SHEET)
                        if not df.empty and gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            new_row = {
                                "Sr. No.": len(df) + 1, "Student Name": name, "Gmail ID": gmail,
                                "Class": cls, "Password": make_hashes(pwd),
                                "Subscription Date": "", "Subscribed Till": "",
                                "Subscription Plan": plan, "Payment Confirmed": "No", "Role": "Student"
                            }
                            df_new = pd.DataFrame([new_row])
                            df = pd.concat([df, df_new], ignore_index=True)
                            save_data(df, STUDENT_SHEET)
                            st.success("Registration successful! Waiting for admin confirmation.")
        
        elif registration_type == "Teacher":
            with st.form("teacher_registration_form", clear_on_submit=True):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                pwd = st.text_input("Password", type="password")
                if st.form_submit_button("Register Teacher"):
                    if not all([name, gmail, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df_teachers = load_data(TEACHER_SHEET)
                        if not df_teachers.empty and gmail in df_teachers["Gmail ID"].values:
                            st.error("This Gmail is already registered as a teacher.")
                        else:
                            new_row = {"Sr. No.": len(df_teachers) + 1, "Teacher Name": name, "Gmail ID": gmail, "Password": make_hashes(pwd), "Confirmed": "No", "Instructions": "", "Role": "Teacher"}
                            df_new = pd.DataFrame([new_row])
                            df_teachers = pd.concat([df_teachers, df_new], ignore_index=True)
                            save_data(df_teachers, TEACHER_SHEET)
                            st.success("Teacher registered! Please wait for admin confirmation.")

    else: # Login Logic
        st.header("Login to Your Dashboard")
        with st.form("unified_login_form"):
            login_gmail = st.text_input("Username (Your Gmail ID)").lower().strip()
            login_pwd = st.text_input("PIN (Your Password)", type="password")
            if st.form_submit_button("Login"):
                user_data = find_user(login_gmail)
                
                if user_data is not None and check_hashes(login_pwd, user_data.get("Password")):
                    role = user_data.get("Role", "").lower()
                    can_login = False
                    if role == "student":
                        if user_data.get("Payment Confirmed") == "Yes" and datetime.today().date() <= pd.to_datetime(user_data.get("Subscribed Till")).date():
                            can_login = True
                        else:
                            st.error("Subscription expired or not confirmed.")
                    elif role in ["teacher", "admin", "principal"]:
                        if user_data.get("Confirmed") == "Yes":
                            can_login = True
                        else:
                            st.error("Registration is pending admin confirmation.")
                    
                    if can_login:
                        st.session_state.logged_in = True
                        st.session_state.user_name = user_data.get("Student Name") or user_data.get("Teacher Name")
                        st.session_state.user_role = role
                        st.session_state.user_gmail = login_gmail
                        st.success("Login Successful! Redirecting...")
                        st.rerun()
                else:
                    st.error("Incorrect PIN or Gmail.")

# If user is logged in, switch to the correct page
else:
    role = st.session_state.user_role
    if role == 'admin':
        st.switch_page("pages/Admin_Dashboard.py")
    elif role == 'principal':
        st.switch_page("pages/Principal_Dashboard.py")
    elif role == 'teacher':
        st.switch_page("pages/Teacher_Dashboard.py")
    elif role == 'student':
        st.switch_page("pages/Student_Dashboard.py")


