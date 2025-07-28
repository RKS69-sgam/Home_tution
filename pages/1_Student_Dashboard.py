import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Student Dashboard")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP_REVERSE = {1: "Needs Improvement", 2: "Average", 3: "Good", 4: "Very Good", 5: "Outstanding"}

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(_sheet):
    """
    Loads all data from a Google Sheet and correctly assigns the first row as the header.
    """
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df.columns = df.columns.str.strip()
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "student":
    st.error("You must be logged in as a Student to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === STUDENT DASHBOARD UI ===
st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")

# Load all necessary data once
df_all_users = load_data(ALL_USERS_SHEET)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_all_answers = load_data(MASTER_ANSWER_SHEET)

user_info_row = df_all_users[df_all_users["Gmail ID"] == st.session_state.user_gmail]

if not user_info_row.empty:
    user_info = user_info_row.iloc[0]
    student_class = user_info.get("Class")
    st.subheader(f"Your Class: {student_class}")
    st.markdown("---")

    # Filter dataframes for the current student
    homework_for_class = df_homework[df_homework.get("Class") == student_class]
    student_answers = df_all_answers[df_all_answers.get('Student Gmail') == st.session_state.user_gmail].copy()

    pending_tab, revision_tab, leaderboard_tab = st.tabs(["Pending Homework", "Revision Zone", "Class Leaderboard"])
    
    with pending_tab:
        st.subheader("Pending Questions")
        pending_questions_list = []
        if 'Question' in homework_for_class.columns:
            for index, hw_row in homework_for_class.iterrows():
                question_text = hw_row.get('Question')
                assignment_date = hw_row.get('Date')
                answer_row = student_answers[(student_answers.get('Question') == question_text) & (student_answers.get('Date') == assignment_date)]
                is_answered = not answer_row.empty
                has_remarks = False
                if is_answered and answer_row.iloc[0].get('Remarks', '').strip():
                    has_remarks = True
                if not is_answered or has_remarks:
                    pending_questions_list.append(hw_row)
            if not pending_questions_list:
                st.success("🎉 Good job! You have no pending homework.")
            else:
                df_pending = pd.DataFrame(pending_questions_list).sort_values(by='Date', ascending=False)
                for i, row in df_pending.iterrows():
                    st.markdown(f"**Assignment Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                    st.write(f"**Question:** {row.get('Question')}")
                    # (Form logic for answering goes here)
        else:
            st.error("Homework sheet is missing the 'Question' column.")

    with revision_tab:
        st.subheader("Previously Graded Answers (Revision Zone)")
        if 'Marks' in student_answers.columns:
            student_answers['Marks_Numeric'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
            graded_answers = student_answers.dropna(subset=['Marks_Numeric'])
            if graded_answers.empty:
                st.info("You have no graded answers to review yet.")
            else:
                for i, row in graded_answers.sort_values(by='Date', ascending=False).iterrows():
                    st.markdown(f"**Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                    # (Display logic for graded answers goes here)
        else:
            st.error("Answer sheet is missing the 'Marks' column.")
    
    with leaderboard_tab:
        st.subheader(f"Class Leaderboard ({student_class})")
        df_students_class = df_all_users[df_all_users['Class'] == student_class]
        class_gmail_list = df_students_class['Gmail ID'].tolist()
        class_answers = df_all_answers[df_all_answers['Student Gmail'].isin(class_gmail_list)].copy()
        if class_answers.empty or 'Marks' not in class_answers.columns:
            st.info("Leaderboard will appear once answers have been graded for your class.")
        else:
            class_answers['Marks'] = pd.to_numeric(class_answers['Marks'], errors='coerce')
            graded_class_answers = class_answers.dropna(subset=['Marks'])
            if graded_class_answers.empty:
                st.info("Leaderboard will appear once answers have been graded for your class.")
            else:
                # (Leaderboard calculation and display logic here)
                pass
else:
    st.error("Could not find your student record.")
