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
    "₹1000 for 6 months (With Advance Classes)": 182,
    "₹2000 for 1 year (With Advance Classes)": 365,
    "₹200 for 30 days (Subjects Homework Only)": 30
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
            doc_data['doc_id'] = doc.id
            data.append(doc_data)
            
        if not data: return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to load data from collection '{_collection_name}': {e}")
        return pd.DataFrame()

# === FIRESTORE COLLECTION NAMES ===
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

# Load all user data from Firestore
df_users = load_collection(USERS_COLLECTION)

if df_users.empty:
    st.warning("No users found in the database.")
else:
    # Display user counts
    total_students = len(df_users[df_users['Role'] == 'Student'])
    total_teachers = len(df_users[df_users['Role'] == 'Teacher'])

    col1, col2 = st.columns(2)
    col1.metric("Total Registered Students", total_students)
    col2.metric("Total Registered Teachers", total_teachers)

    st.markdown("---")

    tab1, tab2 = st.tabs(["Student Management", "Staff Management"])

    with tab1:
        st.subheader("Manage Student Registrations")
        df_students = df_users[df_users['Role'] == 'Student']
        
        st.markdown("#### Pending Payment Confirmations")
        unconfirmed_students = df_students[df_students.get("Payment_Confirmed") != "Yes"]
        
        if unconfirmed_students.empty:
            st.info("No pending student payments.")
        else:
            for index, row in unconfirmed_students.iterrows():
                st.write(f"**Name:** {row.get('User_Name')} | **Plan:** {row.get('Subscription_Plan')}")
                if st.button(f"✅ Confirm Payment for {row.get('User_Name')}", key=f"confirm_student_{row.get('doc_id')}"):
                    plan_days = SUBSCRIPTION_PLANS.get(row.get("Subscription_Plan"), 30)
                    today = datetime.today()
                    till_date = (today + timedelta(days=plan_days)).strftime(DATE_FORMAT)
                    
                    # Update the document in Firestore
                    with st.spinner("Activating account..."):
                        db = connect_to_firestore()
                        user_ref = db.collection(USERS_COLLECTION).document(row.get('doc_id'))
                        user_ref.update({
                            'Subscription_Date': today.strftime(DATE_FORMAT),
                            'Subscribed_Till': till_date,
                            'Payment_Confirmed': 'Yes'
                        })
                        st.success(f"Payment confirmed for {row.get('User_Name')}.")
                        st.rerun()

        st.markdown("---")
        st.markdown("#### Confirmed Students")
        confirmed_students = df_students[df_students.get("Payment_Confirmed") == "Yes"]
        st.dataframe(confirmed_students)

    with tab2:
        st.subheader("Manage Staff Registrations")
        df_staff = df_users[df_users['Role'].isin(['Teacher', 'Principal'])]

        st.markdown("#### Pending Confirmations")
        unconfirmed_staff = df_staff[df_staff.get("Confirmed") != "Yes"]
        
        if unconfirmed_staff.empty:
            st.info("No pending staff confirmations.")
        else:
            for index, row in unconfirmed_staff.iterrows():
                st.write(f"**Name:** {row.get('User_Name')} | **Gmail:** {row.get('Gmail_ID')}")
                if st.button(f"✅ Confirm Staff: {row.get('User_Name')}", key=f"confirm_staff_{row.get('doc_id')}"):
                    with st.spinner("Confirming staff member..."):
                        db = connect_to_firestore()
                        user_ref = db.collection(USERS_COLLECTION).document(row.get('doc_id'))
                        user_ref.update({'Confirmed': 'Yes'})
                        st.success(f"Staff member {row.get('User_Name')} confirmed.")
                        st.rerun()

        st.markdown("---")
        st.markdown("#### Confirmed Staff")
        confirmed_staff = df_staff[df_staff.get("Confirmed") == "Yes"]
        st.dataframe(confirmed_staff)

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
