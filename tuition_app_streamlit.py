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
SECURITY_QUESTIONS = ["What is your mother's maiden name?", "What was the name of your first pet?", "What city were you born in?"]

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
    st.session_state.page_state = "login"

# --- Hide sidebar page navigation ---
st.markdown("<style> [data-testid='stSidebarNav'] {display: none;} </style>", unsafe_allow_html=True)

# === LOGIN / REGISTRATION PAGE ===
if not st.session_state.logged_in:
    st.sidebar.title("Login / New Registration")
    # (Your logo code can be placed here)
    st.markdown("---")
    
    option = st.sidebar.radio("Select an option:", ["Login", "New Registration"])

    if option == "New Registration":
        st.session_state.page_state = "register"
    elif option == "Login" and st.session_state.page_state != "forgot_password":
        st.session_state.page_state = "login"

    if st.session_state.page_state == "register":
        st.header("✍️ New Registration")
        # (Registration logic here)
    
    elif st.session_state.page_state == "forgot_password":
        st.header("🔑 Reset Your Password")
        with st.form("forgot_password_form"):
            gmail_to_reset = st.text_input("Enter your registered Gmail ID").lower().strip()
            user_data = find_user(gmail_to_reset)
            if user_data is not None:
                st.info(f"Security Question: **{user_data.get('Security Question')}**")
            
            security_answer = st.text_input("Your Security Answer").lower().strip()
            new_password = st.text_input("Enter new password", type="password")
            confirm_password = st.text_input("Confirm new password", type="password")
            
            if st.form_submit_button("Reset Password"):
                if not all([gmail_to_reset, security_answer, new_password, confirm_password]):
                    st.warning("Please fill all fields.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif user_data is None:
                    st.error("This Gmail ID is not registered.")
                elif security_answer != user_data.get("Security Answer"):
                    st.error("Incorrect security answer.")
                else:
                    user_role = user_data.get("Role", "student").lower()
                    sheet_to_update = STUDENT_SHEET if user_role == "student" else TEACHER_SHEET
                    cell = sheet_to_update.find(gmail_to_reset)
                    if cell:
                        password_col = list(load_data(sheet_to_update).columns).index("Password") + 1
                        sheet_to_update.update_cell(cell.row, password_col, make_hashes(new_password))
                        st.success("Password updated! Please log in.")
                        st.session_state.page_state = "login"
                        st.rerun()

    else: # Login Page
        st.header("Login to Your Dashboard")
        with st.form("unified_login_form"):
            login_gmail = st.text_input("Username (Your Gmail ID)").lower().strip()
            login_pwd = st.text_input("PIN (Your Password)", type="password")
            if st.form_submit_button("Login"):
                # (Your existing unified login logic here)
                pass

        if st.button("Forgot Password?"):
            st.session_state.page_state = "forgot_password"
            st.rerun()

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
