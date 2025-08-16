import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import base64
import hashlib
import firebase_admin
from firebase_admin import credentials, firestore

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition - Login")
DATE_FORMAT = "%d-%m-%Y"
SUBSCRIPTION_PLANS = {
    "₹1000 for 6 months (With Advance Classes)": 182,
    "₹2000 for 1 year (With Advance Classes)": 365,
    "₹200 for 30 days (Subjects Homework Only)": 30
}
UPI_ID = "9685840429@pnb"
SECURITY_QUESTIONS = ["What is your mother's maiden name?", "What was the name of your first pet?", "What city were you born in?"]

# === UTILITY FUNCTIONS for FIREBASE ===

@st.cache_resource
def connect_to_firestore():
    """Establishes a connection to Google Firestore and caches it."""
    try:
        if not firebase_admin._apps:
            creds_base64 = st.secrets["firebase_service"]["base64_credentials"]
            creds_json_str = base64.b64decode(creds_base64).decode("utf-8")
            creds_dict = json.loads(creds_json_str)
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        st.error(f"Error connecting to Firebase Firestore: {e}")
        return None

def find_user(gmail):
    """Finds a user document in Firestore by their Gmail."""
    db = connect_to_firestore()
    if db is None: return None
    
    # Use the correct field name with underscore
    users_ref = db.collection('users').where('Gmail_ID', '==', gmail).limit(1).stream()
    for user in users_ref:
        user_data = user.to_dict()
        user_data['doc_id'] = user.id # Also return the document ID for updates
        return user_data
    return None

def add_new_user(user_data):
    """Adds a new user document to the 'users' collection."""
    db = connect_to_firestore()
    if db is None: return False
    try:
        # Use the Gmail ID as the unique document ID to prevent duplicates
        db.collection('users').document(user_data['Gmail_ID']).set(user_data)
        return True
    except Exception as e:
        st.error(f"Failed to save registration data: {e}")
        return False

def update_user_password(doc_id, new_password_hash):
    """Updates the password for a specific user document."""
    db = connect_to_firestore()
    if db is None: return False
    try:
        user_ref = db.collection('users').document(doc_id)
        user_ref.update({'Password': new_password_hash})
        return True
    except Exception as e:
        st.error(f"Failed to update password: {e}")
        return False

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

# === SESSION STATE ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""
    st.session_state.page_state = "login"

# === MAIN APP ROUTER ===

if st.session_state.logged_in:
    # --- LOGGED-IN VIEW ---
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
    else:
        st.error("Invalid role detected. Logging out.")
        st.session_state.clear()
        st.rerun()

else:
    # --- LOGIN / REGISTRATION VIEW ---
    st.sidebar.title("Login / New Registration")
    st.markdown("<style> [data-testid='stSidebarNav'] {display: none;} </style>", unsafe_allow_html=True)

    st.image("Ganesh_logo.png", use_container_width=True)
    st.markdown(f"""<div style="text-align: center;"><h2>EPS High-tech Homework System 📈</h2></div>""", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.image("PRK_logo.jpg", use_container_width=True)
    with col2:
        st.image("Excellent_logo.jpg", use_container_width=True)
    st.markdown("---")
    
    option = st.sidebar.radio("Select an option:", ["Login", "New Registration", "Forgot Password"])

    if option == "Login":
        st.header("Login to Your Dashboard")
        with st.form("unified_login_form"):
            login_gmail = st.text_input("Username (Your Gmail ID)").lower().strip()
            login_pwd = st.text_input("PIN (Your Password)", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                user_data = find_user(login_gmail)
                if user_data and check_hashes(login_pwd, user_data.get("Password")):
                    role = user_data.get("Role", "").lower()
                    can_login = False
                    if role == "student":
                        if user_data.get("Payment_Confirmed") == "Yes" and datetime.today().date() <= pd.to_datetime(user_data.get("Subscribed_Till")).date():
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
                        st.session_state.user_name = user_data.get("User_Name")
                        st.session_state.user_role = role
                        st.session_state.user_gmail = login_gmail
                        st.rerun()
                else:
                    st.error("Incorrect PIN or Gmail.")

    elif option == "New Registration":
        st.header("✍️ New Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        # Move plan selection outside the form for dynamic updates
        if registration_type == "Student":
            plan = st.selectbox("Choose Subscription Plan", list(SUBSCRIPTION_PLANS.keys()))
        
        with st.form("registration_form", clear_on_submit=True):
            name = st.text_input("Full Name")
            gmail = st.text_input("Gmail ID").lower().strip()
            pwd = st.text_input("Create Password", type="password")
            confirm_pwd = st.text_input("Confirm Password", type="password")
            security_q = st.selectbox("Choose a Security Question", SECURITY_QUESTIONS)
            security_a = st.text_input("Your Security Answer").lower().strip()
            
            if registration_type == "Student":
                st.subheader("Student Details")
                father_name = st.text_input("Father's Name")
                cls = st.selectbox("Class", [f"{i}th" for i in range(5,13)])
                parent_phonepe = st.text_input("Parent's PhonePe Number")
            
            if st.form_submit_button(f"Register as {registration_type}"):
                if pwd != confirm_pwd:
                    st.error("Passwords do not match.")
                elif find_user(gmail):
                    st.error("This Gmail is already registered.")
                else:
                    new_user_data = {
                        "User_Name": name, "Gmail_ID": gmail, "Password": make_hashes(pwd),
                        "Role": registration_type, "Security_Question": security_q, "Security_Answer": security_a
                    }
                    if registration_type == "Student":
                        new_user_data.update({
                            "Father_Name": father_name, "Class": cls, "Parent_PhonePe": parent_phonepe,
                            "Subscription_Plan": plan, "Payment_Confirmed": "No",
                            "Subscription_Date": "", "Subscribed_Till": ""
                        })
                    else:
                        new_user_data.update({"Confirmed": "No"})
                    
                    if add_new_user(new_user_data):
                        st.success(f"{registration_type} registered successfully! Please wait for confirmation.")

        if registration_type == "Student" and 'plan' in locals():
            st.info(f"Please pay {plan.split(' ')[0]} to the UPI ID: **{UPI_ID}**")
            st.image("Qr logo.jpg", width=250, caption="Scan QR code to pay")
            whatsapp_link = "https://wa.me/919685840429"
            st.success(f"After payment, send a screenshot with student's name and class to our [Official WhatsApp Support]({whatsapp_link}). Your account will be activated within 24 hours.")

    elif option == "Forgot Password":
        st.header("🔑 Reset Your Password")
        with st.form("forgot_password_form", clear_on_submit=True):
            gmail_to_reset = st.text_input("Enter your registered Gmail ID").lower().strip()
            user_data = find_user(gmail_to_reset)
            if user_data:
                st.info(f"Security Question: **{user_data.get('Security_Question')}**")
            
            security_answer = st.text_input("Your Security Answer").lower().strip()
            new_password = st.text_input("Enter new password", type="password")
            confirm_password = st.text_input("Confirm new password", type="password")
            
            if st.form_submit_button("Reset Password"):
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif user_data and security_answer == user_data.get("Security_Answer"):
                    if update_user_password(user_data['doc_id'], make_hashes(new_password)):
                        st.success("Password updated successfully! You can now log in.")
                else:
                    st.error("Invalid Gmail or incorrect security answer.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)
