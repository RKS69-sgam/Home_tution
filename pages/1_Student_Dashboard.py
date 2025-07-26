import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTION TO LOAD & CLEAN DATA ===
@st.cache_data(ttl=60)
def load_data(sheet):
    all_values = sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)  # Clean headers
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY: STUDENT ACCESS ONLY ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "student":
    st.error("You must be logged in as a Student to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR: LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === PAGE HEADER ===
st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")

# === LOAD DATA ===
df_all_users = load_data(ALL_USERS_SHEET)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_all_answers = load_data(MASTER_ANSWER_SHEET)

# === GET CURRENT STUDENT INFO ===
user_info_row = df_all_users[df_all_users["Gmail ID"] == st.session_state.user_gmail]

if user_info_row.empty:
    st.error("❌ Could not find your student record.")
    st.stop()

user_info = user_info_row.iloc[0]
student_class = user_info.get("Class")
st.subheader(f"Your Class: {student_class}")
st.markdown("---")

# === CHECK IF 'Student Gmail' COLUMN EXISTS IN ANSWERS ===
if "Student Gmail" not in df_all_answers.columns:
    st.error("❌ 'Student Gmail' column not found in the answer sheet.")
    st.write("Available columns:", df_all_answers.columns.tolist())
    st.stop()

# === FILTER STUDENT ANSWERS ===
student_answers = df_all_answers[df_all_answers["Student Gmail"] == st.session_state.user_gmail].copy()
homework_for_class = df_homework[df_homework.get("Class") == student_class]

# === TABS ===
pending_tab, revision_tab, leaderboard_tab = st.tabs(["Pending Homework", "Revision Zone", "Class Leaderboard"])

# === PENDING HOMEWORK TAB ===
with pending_tab:
    st.subheader("Pending Questions")
    pending_questions_list = []

    for _, hw_row in homework_for_class.iterrows():
        answer_row = student_answers[
            (student_answers['Question'] == hw_row.get('Question')) &
            (student_answers['Date'] == hw_row.get('Date'))
        ]
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
            matching_answer = student_answers[
                (student_answers['Question'] == row.get('Question')) &
                (student_answers['Date'] == row.get('Date'))
            ]
            if not matching_answer.empty and matching_answer.iloc[0].get('Remarks'):
                st.warning(f"**Teacher's Remark:** {matching_answer.iloc[0].get('Remarks')}")
                st.markdown("Please correct your answer and resubmit.")
            with st.form(key=f"pending_form_{i}"):
                answer_text = st.text_area(
                    "Your Answer:",
                    key=f"pending_text_{i}",
                    value=matching_answer.iloc[0].get('Answer', '') if not matching_answer.empty else ""
                )
                if st.form_submit_button("Submit Answer"):
                    if answer_text.strip():
                        # TODO: Add logic to update/append the sheet
                        st.success("✅ Answer submitted!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Answer cannot be empty.")
            st.markdown("---")

# === REVISION ZONE TAB ===
with revision_tab:
    st.subheader("Previously Graded Answers (Revision Zone)")
    student_answers['Marks_Numeric'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
    graded_answers = student_answers.dropna(subset=['Marks_Numeric'])
    if graded_answers.empty:
        st.info("You have no graded answers to review yet.")
    else:
        for _, row in graded_answers.sort_values(by='Date', ascending=False).iterrows():
            st.markdown(f"**Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
            st.write(f"**Question:** {row.get('Question')}")
            st.info(f"**Your Answer:** {row.get('Answer')}")
            grade_value = int(row.get('Marks_Numeric'))
            grade_text = GRADE_MAP_REVERSE.get(grade_value, "N/A")
            st.success(f"**Grade:** {grade_text} ({grade_value}/5)")
            remarks = row.get('Remarks', '').strip()
            if remarks:
                st.warning(f"**Teacher's Remark:** {remarks}")
            st.markdown("---")

# === CLASS LEADERBOARD TAB ===
with leaderboard_tab:
    st.subheader(f"Class Leaderboard ({student_class})")
    df_students_class = df_all_users[df_all_users['Class'] == student_class]
    class_gmail_list = df_students_class['Gmail ID'].tolist()
    class_answers = df_all_answers[df_all_answers['Student Gmail'].isin(class_gmail_list)].copy()
    if class_answers.empty:
        st.info("The leaderboard will appear once answers have been graded for your class.")
    else:
        class_answers['Marks'] = pd.to_numeric(class_answers['Marks'], errors='coerce')
        graded_class_answers = class_answers.dropna(subset=['Marks'])
        if graded_class_answers.empty:
            st.info("The leaderboard will appear once answers have been graded for your class.")
        else:
            leaderboard_df = graded_class_answers.groupby('Student Gmail')['Marks'].mean().reset_index()
            leaderboard_df = pd.merge(
                leaderboard_df,
                df_students_class[['User Name', 'Gmail ID']],
                left_on='Student Gmail',
                right_on='Gmail ID',
                how='left'
            )
            leaderboard_df['Rank'] = leaderboard_df['Marks'].rank(method='dense', ascending=False).astype(int)
            leaderboard_df = leaderboard_df.sort_values(by='Rank')
            leaderboard_df['Marks'] = leaderboard_df['Marks'].round(2)
            st.markdown("##### 🏆 Top 3 Performers")
            st.dataframe(leaderboard_df.head(3)[['Rank', 'User Name', 'Marks']])
            st.markdown("---")
            my_rank_row = leaderboard_df[leaderboard_df['Student Gmail'] == st.session_state.user_gmail]
            if not my_rank_row.empty:
                my_rank = my_rank_row.iloc[0]['Rank']
                my_avg_marks = my_rank_row.iloc[0]['Marks']
                st.success(f"**Your Current Rank:** {my_rank} (Avg. Score: **{my_avg_marks}**)")
            else:
                st.warning("Your rank will appear once your answers are graded.")