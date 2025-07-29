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
    "₹550 for 6 months (Advance)": 182,
    "₹1000 for 1 year (Advance)": 365,
    "₹100 for 30 days (Subjects Homework Only)": 30
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
    
    ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
    
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

@st.cache_data(ttl=30)
def load_data(_sheet):
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    return pd.DataFrame(all_values[1:], columns=all_values[0])

def save_data(df, sheet):
    df_to_save = df.drop(columns=['Row ID'], errors='ignore')
    df_str = df_to_save.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())
    load_data.clear()

def find_user(gmail):
    df_users = load_data(ALL_USERS_SHEET)
    if not df_users.empty and 'Gmail ID' in df_users.columns:
        user_data = df_users[df_users['Gmail ID'] == gmail]
        if not user_data.empty:
            return user_data.iloc[0]
    return None

# === SESSION STATE ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""
    st.session_state.page_state = "login"

# --- Hide sidebar page navigation when not logged in ---
if not st.session_state.logged_in:
    st.markdown("<style> [data-testid='stSidebarNav'] {display: none;} </style>", unsafe_allow_html=True)

# === LOGIN / REGISTRATION PAGE ===
if not st.session_state.logged_in:
    st.sidebar.title("Login / New Registration")
    
    st.markdown(f"""<div style="text-align: center;"><h2>EPS High-tech Homework System 📈</h2></div>""", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.image("PRK_logo.jpg", use_container_width=True)
    with col2:
        st.image("Excellent_logo.jpg", use_container_width=True)
    st.markdown("---")
    
    option = st.sidebar.radio("Select an option:", ["Login", "New Registration", "Forgot Password"])

    st.sidebar.markdown("---")
    st.sidebar.markdown(
    """
    <div style='text-align: center; font-size: 12px;'>
    © 2025 PRK Home Tuition.<br>All Rights Reserved.
    </div>
    """,
    unsafe_allow_html=True
    )


    if option == "New Registration":
        st.session_state.page_state = "register"
    elif option == "Login":
        st.session_state.page_state = "login"
    elif option == "Forgot Password":
        st.session_state.page_state = "forgot_password"

    if st.session_state.page_state == "register":
        st.header("✍️ New Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            st.subheader("Student Registration")
            
            # The plan selector is now outside the form to allow dynamic updates
            plan = st.selectbox("Choose Subscription Plan", list(SUBSCRIPTION_PLANS.keys()), key="plan_selector")
            
            with st.form("student_registration_form"):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
                pwd = st.text_input("Password", type="password")
                security_q = st.selectbox("Choose a Security Question", SECURITY_QUESTIONS)
                security_a = st.text_input("Your Security Answer").lower().strip()
                
                submitted = st.form_submit_button("Register (After Payment)")

                if submitted:
                    if not all([name, gmail, cls, pwd, plan, security_q, security_a]):
                        st.warning("Please fill in ALL details.")
                    else:
                        df = load_data(ALL_USERS_SHEET)
                        if not df.empty and gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            new_row = {"User Name": name, "Gmail ID": gmail, "Class": cls, "Password": make_hashes(pwd), "Subscription Plan": plan, "Security Question": security_q, "Security Answer": security_a, "Role": "Student", "Payment Confirmed": "No", "Subscription Date": "", "Subscribed Till": "", "Confirmed": "", "Instructions": "", "Salary Points": ""}
                            df_new = pd.DataFrame([new_row])
                            df = pd.concat([df, df_new], ignore_index=True)
                            save_data(df, ALL_USERS_SHEET)
                            st.success("Registration successful! Waiting for admin confirmation.")

            if plan:
                st.info(f"Please pay {plan.split(' ')[0]} to the UPI ID below.")
                st.code(f"UPI: {UPI_ID}", language="text")

        elif registration_type == "Teacher":
            with st.form("teacher_registration_form", clear_on_submit=True):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                pwd = st.text_input("Password", type="password")
                security_q = st.selectbox("Choose a Security Question", SECURITY_QUESTIONS)
                security_a = st.text_input("Your Security Answer").lower().strip()
                if st.form_submit_button("Register Teacher"):
                    if not all([name, gmail, pwd, security_q, security_a]):
                        st.warning("Please fill in all details.")
                    else:
                        df_teachers = load_data(ALL_USERS_SHEET)
                        if not df_teachers.empty and gmail in df_teachers["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            new_row = {"User Name": name, "Gmail ID": gmail, "Password": make_hashes(pwd), "Security Question": security_q, "Security Answer": security_a, "Role": "Teacher", "Confirmed": "No"}
                            df_new = pd.DataFrame([new_row])
                            df_teachers = pd.concat([df_teachers, df_new], ignore_index=True)
                            save_data(df_teachers, ALL_USERS_SHEET)
                            st.success("Teacher registered! Please wait for admin confirmation.")

    elif st.session_state.page_state == "forgot_password":
        st.header("🔑 Reset Your Password")
        with st.form("forgot_password_form", clear_on_submit=True):
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
                    cell = ALL_USERS_SHEET.find(gmail_to_reset)
                    if cell:
                        header_row = ALL_USERS_SHEET.row_values(1)
                        password_col = header_row.index("Password") + 1
                        ALL_USERS_SHEET.update_cell(cell.row, password_col, make_hashes(new_password))
                        load_data.clear()
                        st.success("Password updated! Please log in.")
                        st.session_state.page_state = "login"
                        st.rerun()

    else: # Login Page
        st.header("Login to Your Dashboard")
        with st.form("unified_login_form"):
            login_gmail = st.text_input("Username (Your Gmail ID)").lower().strip()
            login_pwd = st.text_input("PIN (Your Password)", type="password")
            if st.form_submit_button("Login"):
                load_data.clear()
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
                        st.session_state.user_name = user_data.get("User Name")
                        st.session_state.user_role = role
                        st.session_state.user_gmail = login_gmail
                        st.rerun()
                else:
                    st.error("Incorrect PIN or Gmail.")
        if st.button("Forgot Password?", use_container_width=True):
            st.session_state.page_state = "forgot_password"
            st.rerun()

# If user is logged in, switch to the correct page
else:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    role = st.session_state.user_role
    if role == 'admin':
        st.switch_page("pages/3_Admin_Dashboard.py")
    elif role == 'principal':
        st.switch_page("pages/4_Principal_Dashboard.py")
    elif role == 'teacher':
        st.switch_page("pages/2_Teacher_Dashboard.py")
    elif role == 'student':
        st.switch_page("pages/1_Student_Dashboard.py")
