import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import hashlib
import plotly.express as px
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}
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
    drive_service = build("drive", "v3", credentials=credentials)

    STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
    TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
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
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df['Row ID'] = range(2, len(df) + 2)
    return df

def save_data(df, sheet):
    # Drop the 'Row ID' column before saving, as it's generated dynamically
    df_to_save = df.drop(columns=['Row ID'], errors='ignore')
    df_str = df_to_save.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())

def get_image_as_base64(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"
    except FileNotFoundError:
        return None

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

# Header logo
st.sidebar.title("Login / New Registration")
prk_logo_b64 = get_image_as_base64("PRK_logo.jpg")
excellent_logo_b64 = get_image_as_base64("Excellent_logo.jpg")
if prk_logo_b64 and excellent_logo_b64:
    st.markdown(f"""<div style="text-align: center;"><h2>Excellent Public School High-tech Homework System 📈</h2></div>""", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: st.image("PRK_logo.jpg")
    with col2: st.image("Excellent_logo.jpg")
st.markdown("---")

# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    option = st.sidebar.radio("Select an option:", ["Login", "New Registration"])

    if option == "New Registration":
        st.header("✍️ New Registration")
        # (Your full registration logic here)
        
    else: # Login Logic
        st.header("Login to Your Dashboard")
        with st.form("unified_login_form"):
            login_gmail = st.text_input("Username (Your Gmail ID)").lower().strip()
            login_pwd = st.text_input("PIN (Your Password)", type="password")
            if st.form_submit_button("Login"):
                if not login_gmail or not login_pwd:
                    st.warning("Please enter both Gmail and PIN.")
                else:
                    user_data = find_user(login_gmail)
                    
                    if user_data is not None:
                        if check_hashes(login_pwd, user_data.get("Password")):
                            role = user_data.get("Role").lower()
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
                    else:
                        st.error("User not found.")

# === LOGGED-IN MESSAGE & SIDEBAR ===
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    
    st.success("You are logged in!")
    st.info("Please select your dashboard from the sidebar navigation above.")