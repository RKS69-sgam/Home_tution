import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import hashlib

from google.oauth2.service_account import Credentials

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

# === UTILITY FUNCTIONS ===
@st.cache_resource
def connect_to_gsheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
        credentials_dict = json.loads(decoded_creds)
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google APIs: {e}")
        return None

@st.cache_data(ttl=30)
def load_data(sheet_id):
    try:
        client = connect_to_gsheets()
        if client is None: return pd.DataFrame()
        sheet = client.open_by_key(sheet_id).sheet1
        all_values = sheet.get_all_values()
        if not all_values: return pd.DataFrame()
        return pd.DataFrame(all_values[1:], columns=all_values[0])
    except Exception as e:
        st.error(f"Failed to load data for sheet ID {sheet_id}: {e}")
        return pd.DataFrame()

def save_data(df, sheet_id):
    try:
        client = connect_to_gsheets()
        sheet = client.open_by_key(sheet_id).sheet1
        df_to_save = df.drop(columns=['Row ID'], errors='ignore')
        df_str = df_to_save.fillna("").astype(str)
        sheet.clear()
        sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"Failed to save data: {e}")
        return False

def find_user(gmail):
    df_users = load_data(ALL_USERS_SHEET_ID)
    if not df_users.empty and 'Gmail ID' in df_users.columns:
        user_data = df_users[df_users['Gmail ID'] == gmail]
        if not user_data.empty:
            return user_data.iloc[0]
    return None

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

# === SHEET IDs ===
ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"

# === SESSION STATE ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""
    st.session_state.page_state = "login"
    # This code is inside the show_login_page() function

    col1, col2 = st.columns(2)
    with col1:
        if st.button("New User? Register Here", use_container_width=True):
            st.session_state.page_state = "register"
            st.rerun()
    with col2:
        if st.button("Forgot Password?", use_container_width=True):
            st.session_state.page_state = "forgot_password"
            st.rerun()

# --- Hide sidebar page navigation when not logged in ---
if not st.session_state.logged_in:
    st.markdown("<style> [data-testid='stSidebarNav'] {display: none;} </style>", unsafe_allow_html=True)

# === PAGE DEFINITIONS ===
def show_login_page():
    st.header("Login to Your Dashboard")
    with st.form("unified_login_form"):
        login_gmail = st.text_input("Username (Your Gmail ID)").lower().strip()
        login_pwd = st.text_input("PIN (Your Password)", type="password")
        if st.form_submit_button("Login", use_container_width=True):
            load_data.clear()
            user_data = find_user(login_gmail)
            if user_data is not None and check_hashes(login_pwd, user_data.get("Password")):
                role = user_data.get("Role", "").lower()
                can_login = False
                if role == "student":
                    if user_data.get("Payment Confirmed") == "Yes" and datetime.today().date() <= pd.to_datetime(user_data.get("Subscribed Till")).date():
                        can_login = True
                    else: st.error("Subscription expired or not confirmed.")
                elif role in ["teacher", "admin", "principal"]:
                    if user_data.get("Confirmed") == "Yes":
                        can_login = True
                    else: st.error("Registration is pending admin confirmation.")
                if can_login:
                    st.session_state.logged_in = True
                    st.session_state.user_name = user_data.get("User Name")
                    st.session_state.user_role = role
                    st.session_state.user_gmail = login_gmail
                    st.rerun()
            else:
                st.error("Incorrect PIN or Gmail.")

def show_registration_page():
    st.header("✍️ New Registration")
    registration_type = st.radio("Register as:", ["Student", "Teacher"])
    if registration_type == "Student":
        plan = st.selectbox("Choose Subscription Plan", list(SUBSCRIPTION_PLANS.keys()))
    else:
        plan = None
    
    with st.form("registration_form"):
        name = st.text_input("Full Name")
        gmail = st.text_input("Gmail ID").lower().strip()
        mobile = st.text_input("Mobile Number")
        pwd = st.text_input("Create Password", type="password")
        confirm_pwd = st.text_input("Confirm Password", type="password")
        security_q = st.selectbox("Choose a Security Question", SECURITY_QUESTIONS)
        security_a = st.text_input("Your Security Answer").lower().strip()
        
        if registration_type == "Student":
            st.subheader("Student Details")
            father_name = st.text_input("Father's Name")
            cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
            parent_phonepe = st.text_input("Parent's PhonePe Number")
        
        submitted = st.form_submit_button(f"Register as {registration_type}")
        if submitted:
            if pwd != confirm_pwd:
                st.error("Passwords do not match.")
            else:
                df = load_data(ALL_USERS_SHEET_ID)
                if not df.empty and gmail in df["Gmail ID"].values:
                    st.error("This Gmail is already registered.")
                else:
                    new_row_data = {
                        "User Name": name, "Gmail ID": gmail, "Password": make_hashes(pwd),
                        "Role": registration_type, "Mobile Number": mobile,
                        "Security Question": security_q, "Security Answer": security_a,
                        "Class": cls if registration_type == "Student" else "",
                        "Subscription Plan": plan if registration_type == "Student" else "",
                        "Payment Confirmed": "No" if registration_type == "Student" else "",
                        "Father Name": father_name if registration_type == "Student" else "",
                        "Parent PhonePe": parent_phonepe if registration_type == "Student" else "",
                        "Confirmed": "No" if registration_type == "Teacher" else "",
                    }
                    df_new = pd.DataFrame([new_row_data])
                    df = pd.concat([df, df_new], ignore_index=True)
                    if save_data(df, ALL_USERS_SHEET):
                        st.success(f"{registration_type} registered! Please wait for confirmation.")

    if registration_type == "Student" and plan:
        st.info(f"Please pay {plan.split(' ')[0]} to the UPI ID: **{UPI_ID}**")
        st.image("Qr logo.jpg", width=250, caption="Scan QR code to pay")
        whatsapp_link = "https://wa.me/919685840429"
        st.success(f"After payment, send a screenshot with student's name and class to our [Official WhatsApp Support]({whatsapp_link}). Your account will be activated within 24 hours.")

def show_forgot_password_page():
    st.header("🔑 Reset Your Password")
    with st.form("forgot_password_form", clear_on_submit=True):
        gmail_to_reset = st.text_input("Enter your registered Gmail ID").lower().strip()
        
        # Look up the user to display their security question
        user_data = find_user(gmail_to_reset)
        if user_data is not None:
            st.info(f"Security Question: **{user_data.get('Security Question')}**")
        
        security_answer = st.text_input("Your Security Answer").lower().strip()
        new_password = st.text_input("Enter new password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        
        submitted = st.form_submit_button("Reset Password")

        if submitted:
            if not all([gmail_to_reset, security_answer, new_password, confirm_password]):
                st.warning("Please fill all fields.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif user_data is None:
                st.error("This Gmail ID is not registered.")
            elif security_answer != user_data.get("Security Answer"):
                st.error("Incorrect security answer.")
            else:
                with st.spinner("Updating password..."):
                    # Find the cell and update the password with the new hash
                    client = connect_to_gsheets()
                    sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                    cell = sheet.find(gmail_to_reset)
                    
                    if cell:
                        header_row = sheet.row_values(1)
                        password_col = header_row.index("Password") + 1
                        sheet.update_cell(cell.row, password_col, make_hashes(new_password))
                        
                        load_data.clear() # Clear cache to reflect the change
                        st.success("Password updated! You can now log in with your new password.")
                        st.session_state.page_state = "login"
                        # No st.rerun() needed here as the state will change on the next interaction
                    else:
                        st.error("An unexpected error occurred. Please try again.")

    if st.button("← Back to Login"):
        st.session_state.page_state = "login"
        st.rerun()

# === MAIN APP ROUTING ===
if not st.session_state.logged_in:
    st.sidebar.title("Login / New Registration")
    st.markdown(f"""<div style="text-align: center;"><h2>EPS High-tech Homework System 📈</h2></div>""", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: st.image("PRK_logo.jpg", use_container_width=True)
    with col2: st.image("Excellent_logo.jpg", use_container_width=True)
    st.markdown("---")
    if st.session_state.page_state == "register":
        show_registration_page()
    elif st.session_state.page_state == "forgot_password":
        show_forgot_password_page()
    else:
        show_login_page()
else:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    role = st.session_state.user_role
    page_map = {
        "admin": "pages/3_Admin_Dashboard.py",
        "principal": "pages/4_Principal_Dashboard.py",
        "teacher": "pages/2_Teacher_Dashboard.py",
        "student": "pages/1_Student_Dashboard.py"
    }
    if role in page_map:
        st.switch_page(page_map[role])
