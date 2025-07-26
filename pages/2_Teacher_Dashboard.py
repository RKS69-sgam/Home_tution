import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}

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

# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(_sheet):
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === TEACHER DASHBOARD UI ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

df_users = load_data(ALL_USERS_SHEET)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_answers = load_data(MASTER_ANSWER_SHEET)

teacher_info = df_users[(df_users['Role'] == 'Teacher') & (df_users['User Name'] == st.session_state.user_name)]
if not teacher_info.empty and teacher_info.iloc[0].get("Instructions"):
    st.warning(f"**Instruction from Principal:** {teacher_info.iloc[0].get('Instructions')}")

create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

with create_tab:
    st.subheader("Create a New Homework Assignment")
    if 'context_set' not in st.session_state:
        st.session_state.context_set = False
    if not st.session_state.context_set:
        with st.form("context_form"):
            subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance"])
            class_selected = st.selectbox("Class", ["6th", "7th", "8th", "9th", "10th"])
            date_selected = st.date_input("Date", datetime.now().date())
            submitted = st.form_submit_button("Set Context")
            if submitted:
                st.session_state.context = {
                    "subject": subject,
                    "class": class_selected,
                    "date": date_selected,
                    "uploaded_by": st.session_state.user_name
                }
                st.session_state.questions_list = []
                st.session_state.context_set = True
                st.success("Context set! Now add your questions.")
                st.rerun()

    if st.session_state.context_set:
        st.markdown("#### Add Homework Questions")
        new_question = st.text_input("Enter Question:")
        if st.button("Add Question"):
            if new_question.strip():
                st.session_state.questions_list.append(new_question.strip())
                st.success("Question added!")
                st.rerun()
        if st.session_state.questions_list:
            st.markdown("##### Questions Added:")
            for q in st.session_state.questions_list:
                st.write(f"- {q}")
            if st.button("Submit Homework"):
                ctx = st.session_state.context
                rows_to_add = [[ctx['class'], ctx['date'].strftime(DATE_FORMAT), ctx['uploaded_by'], ctx['subject'], q]
                               for q in st.session_state.questions_list]
                try:
                    HOMEWORK_QUESTIONS_SHEET.append_rows(rows_to_add, value_input_option="USER_ENTERED")
                    st.success("Homework successfully added!")
                except Exception as e:
                    st.error(f"Failed to upload: {e}")
                st.session_state.context_set = False
                st.rerun()

with grade_tab:
    st.subheader("Grade Student Answers")
    selected_class = st.selectbox("Select Class", ["6th", "7th", "8th", "9th", "10th"], key="grading_class")
    selected_subject = st.selectbox("Select Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance"], key="grading_subject")
    today = datetime.today().strftime(DATE_FORMAT)
    answers_to_grade = df_answers[
        (df_answers['Subject'] == selected_subject) &
        (df_answers['Date'] == today) &
        (df_answers['Marks'].isna())
    ]
    if answers_to_grade.empty:
        st.info("No ungraded answers found for selected filters.")
    else:
        for i, row in answers_to_grade.iterrows():
            st.markdown(f"**Student:** {row.get('Student Gmail')} | **Question:** {row.get('Question')}")
            st.info(f"**Answer:** {row.get('Answer')}")
            with st.form(f"grading_form_{i}"):
                marks = st.selectbox("Grade", list(GRADE_MAP.keys()), key=f"grade_select_{i}")
                remark = st.text_area("Remarks (optional)", key=f"remark_input_{i}")
                if st.form_submit_button("Submit Grade"):
                    MASTER_ANSWER_SHEET.update(f"F{row['Row ID']}", str(GRADE_MAP[marks]))  # Marks column (F)
                    MASTER_ANSWER_SHEET.update(f"G{row['Row ID']}", remark)  # Remarks column (G)
                    st.success("Grade submitted!")
                    st.rerun()

with report_tab:
    st.subheader("My Uploaded Questions")
    if "Uploaded By" in df_homework.columns:
        my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]['Question'].tolist()
    else:
        st.warning("⚠️ 'Uploaded By' column not found in homework sheet.")
        my_questions = []

    if my_questions:
        st.markdown("##### You have uploaded the following questions:")
        for q in my_questions:
            st.write(f"- {q}")
    else:
        st.info("No homework uploaded yet.")