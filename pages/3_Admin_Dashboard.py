import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import base64
import firebase_admin
from firebase_admin import credentials, firestore

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Admin Dashboard")
DATE_FORMAT = "%d-%m-%Y"
SUBSCRIPTION_PLANS = {
    "₹1000 for 6 months (Advance)": 182,
    "₹2000 for 1 year (Advance)": 365,
    "₹200 for 30 days (Normal)": 30
}

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

@st.cache_data(ttl=60)
def load_collection(_collection_name):
    """Loads all documents from a Firestore collection into a Pandas DataFrame."""
    try:
        db = connect_to_firestore()
        if db is None: return pd.DataFrame()
        
        collection_ref = db.collection(_collection_name).stream()
        data = []
        for doc in collection_ref:
            doc_data = doc.to_dict()
            doc_data['doc_id'] = doc.id # Also get the document ID for updates
            data.append(doc_data)
            
        if not data: return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to load data from collection '{_collection_name}': {e}")
        return pd.DataFrame()

# === SHEET IDs (Firestore Collection Names) ===
USERS_COLLECTION = "users"
ANNOUNCEMENTS_COLLECTION = "announcements"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "admin":
    st.error("You must be logged in as an Admin to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === ADMIN DASHBOARD UI ===
st.header("👑 Admin Panel")

# --- Display Public Announcement ---
try:
    announcements_df = load_collection(ANNOUNCEMENTS_COLLECTION)
    if not announcements_df.empty:
        today_str = datetime.today().strftime(DATE_FORMAT)
        todays_announcement = announcements_df[announcements_df.get('Date') == today_str]
        if not todays_announcement.empty:
            latest_message = todays_announcement['Message'].iloc[0]
            st.info(f"📢 **Public Announcement:** {latest_message}")
except Exception:
    pass

# Load all user data from Firestore
df_users = load_collection(USERS_COLLECTION)

# Display user counts
total_students = len(df_users[df_users['Role'] == 'Student']) if not df_users.empty else 0
total_teachers = len(df_users[df_users['Role'] == 'Teacher']) if not df_users.empty else 0

col1, col2 = st.columns(2)
col1.metric("Total Registered Students", total_students)
col2.metric("Total Registered Teachers", total_teachers)

st.markdown("---")

tab1, tab2 = st.tabs(["Student Management", "Teacher Management"])

with tab1:
    st.subheader("Manage Student Registrations")
    if df_users.empty:
        st.info("No users found.")
    else:
        df_students = df_users[df_users['Role'] == 'Student']
        
        st.markdown("#### Pending Payment Confirmations")
        unconfirmed_students = df_students[df_students.get("Payment Confirmed") != "Yes"]
        
        if unconfirmed_students.empty:
            st.info("No pending student payments.")
        else:
            for index, row in unconfirmed_students.iterrows():
                st.write(f"**Name:** {row.get('User Name')} | **Plan:** {row.get('Subscription Plan')}")
                if st.button(f"✅ Confirm Payment for {row.get('User Name')}", key=f"confirm_student_{row.get('doc_id')}"):
                    plan_days = SUBSCRIPTION_PLANS.get(row.get("Subscription Plan"), 30)
                    today = datetime.today()
                    till_date = (today + timedelta(days=plan_days)).strftime(DATE_FORMAT)
                    
                    # Update the document in Firestore
                    db = connect_to_firestore()
                    user_ref = db.collection('users').document(row.get('doc_id'))
                    user_ref.update({
                        'Subscription Date': today.strftime(DATE_FORMAT),
                        'Subscribed Till': till_date,
                        'Payment Confirmed': 'Yes'
                    })
                    st.success(f"Payment confirmed for {row.get('User Name')}.")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### Confirmed Students")
        confirmed_students = df_students[df_students.get("Payment Confirmed") == "Yes"]
        st.dataframe(confirmed_students)

with tab2:
    st.subheader("Manage Teacher Registrations")
    if df_users.empty:
        st.info("No users found.")
    else:
        df_teachers = df_users[df_users['Role'].isin(['Teacher', 'Principal'])]

        st.markdown("#### Pending Teacher Confirmations")
        unconfirmed_teachers = df_teachers[df_teachers.get("Confirmed") != "Yes"]
        
        if unconfirmed_teachers.empty:
            st.info("No pending teacher confirmations.")
        else:
            for index, row in unconfirmed_teachers.iterrows():
                st.write(f"**Name:** {row.get('User Name')} | **Gmail:** {row.get('Gmail ID')}")
                if st.button(f"✅ Confirm Staff: {row.get('User Name')}", key=f"confirm_teacher_{row.get('doc_id')}"):
                    db = connect_to_firestore()
                    user_ref = db.collection('users').document(row.get('doc_id'))
                    user_ref.update({'Confirmed': 'Yes'})
                    st.success(f"Staff member {row.get('User Name')} confirmed.")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### Confirmed Teachers & Principals")
        confirmed_teachers = df_teachers[df_teachers.get("Confirmed") == "Yes"]
        st.dataframe(confirmed_teachers)
