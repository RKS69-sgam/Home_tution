import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import json
import base64
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%d-%m-%Y"

# === UTILITY FUNCTIONS for FIREBASE ===
@st.cache_resource
def connect_to_firestore():
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
HOMEWORK_COLLECTION = "homework"
ANSWERS_COLLECTION = "answers"
ANSWER_BANK_COLLECTION = "answer_bank"
ANNOUNCEMENTS_COLLECTION = "announcements"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to access this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === TEACHER DASHBOARD UI ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# --- Load all necessary data from Firestore ---
df_users = load_collection(USERS_COLLECTION)
df_homework = load_collection(HOMEWORK_COLLECTION)
df_live_answers = load_collection(ANSWERS_COLLECTION)
df_answer_bank = load_collection(ANSWER_BANK_COLLECTION)

# --- START DEBUGGING BLOCK ---
st.warning("--- DEBUGGING: Checking Columns ---")
st.write("Columns found in `df_homework` (from 'homework' collection):")
if not df_homework.empty:
    st.write(df_homework.columns.tolist())
else:
    st.write("Homework collection is empty.")
st.markdown("---")
# --- END DEBUGGING BLOCK ---

# --- INSTRUCTION & ANNOUNCEMENT SYSTEMS ---
# (Your instruction and announcement display logic here)
# ...

# --- Top Level Metrics ---
st.markdown("#### Your Overall Performance")
col1, col2, col3 = st.columns(3)

teacher_info_row = df_users[df_users['Gmail_ID'] == st.session_state.user_gmail]
if not teacher_info_row.empty:
    teacher_info = teacher_info_row.iloc[0]
    
    points_str = str(teacher_info.get('Salary_Points', '0')).strip()
    my_points = int(points_str) if points_str.isdigit() else 0
    col1.metric("My Salary Points", my_points)

    # This is the line that was causing the error
    my_questions_count = len(df_homework[df_homework['Uploaded_By'] == st.session_state.user_name]) if not df_homework.empty else 0
    col2.metric("My Total Questions Created", my_questions_count)

    df_all_teachers_rank = df_users[df_users['Role'] == 'Teacher'].copy()
    if not df_all_teachers_rank.empty:
        df_all_teachers_rank['Salary_Points'] = pd.to_numeric(df_all_teachers_rank.get('Salary_Points', 0), errors='coerce').fillna(0)
        df_all_teachers_rank = df_all_teachers_rank.sort_values(by='Salary_Points', ascending=False).reset_index()
        my_rank_row = df_all_teachers_rank[df_all_teachers_rank['Gmail_ID'] == st.session_state.user_gmail]
        my_rank = my_rank_row.index[0] + 1 if not my_rank_row.empty else "N/A"
        col3.metric("My Rank Among Teachers", f"#{my_rank}")

st.markdown("---")

# (The rest of your Teacher Dashboard code for tabs/radio buttons goes here)
# ...

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)

