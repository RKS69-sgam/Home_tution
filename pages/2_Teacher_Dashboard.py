import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
import base64

from google.oauth2.service_account import Credentials

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
    df.columns = df.columns.str.strip()  # Clean column names
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === DASHBOARD ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

df_users = load_data(ALL_USERS_SHEET)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)

# 🔍 DEBUG BLOCK FOR df_answers
df_answers = load_data(MASTER_ANSWER_SHEET)
st.write("📋 Columns found in Master Answer Sheet:", df_answers.columns.tolist())
if "Subject" not in df_answers.columns:
    st.warning("⚠️ 'Subject' column not found in the answer sheet.")
    st.stop()

# === CREATE TABS ===
create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

with create_tab:
    st.subheader("Create Homework")
    subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST"])
    class_selected = st.selectbox("Class", ["6th", "7th", "8th", "9th"])
    date_selected = st.date_input("Date", value=datetime.today())
    num_questions = st.number_input("No. of Questions", min_value=1, max_value=10, step=1)

    questions = []
    for i in range(num_questions):
        q = st.text_input(f"Question {i+1}", key=f"q{i}")
        questions.append(q)

    if st.button("Submit Homework"):
        if all(q.strip() for q in questions):
            rows = [[class_selected, date_selected.strftime(DATE_FORMAT), st.session_state.user_name, subject, q] for q in questions]
            HOMEWORK_QUESTIONS_SHEET.append_rows(rows)
            st.success("✅ Homework submitted successfully!")
        else:
            st.warning("⚠️ Please fill all questions before submitting.")

with grade_tab:
    st.subheader("Grade Student Answers")
    subject_filter = st.selectbox("Select Subject", df_answers["Subject"].unique())
    class_filter = st.selectbox("Select Class", df_users["Class"].unique())

    ungraded = df_answers[(df_answers["Subject"] == subject_filter) & (df_answers["Marks"] == "")]
    if ungraded.empty:
        st.info("🎉 No ungraded answers found.")
    else:
        for i, row in ungraded.iterrows():
            st.markdown(f"**Student:** {row['Student Gmail']} | **Date:** {row['Date']} | **Question:** {row['Question']}")
            st.info(f"Answer: {row['Answer']}")
            with st.form(key=f"grade_form_{i}"):
                marks = st.selectbox("Marks", list(GRADE_MAP.keys()), key=f"m{i}")
                remarks = st.text_area("Remarks", key=f"r{i}")
                if st.form_submit_button("Submit Grade"):
                    row_id = row["Row ID"]
                    MASTER_ANSWER_SHEET.update(f"F{row_id}", str(GRADE_MAP[marks]))
                    MASTER_ANSWER_SHEET.update(f"G{row_id}", remarks)
                    st.success("✅ Grade submitted!")
                    st.rerun()

with report_tab:
    st.subheader("My Reports")
    if "Uploaded By" in df_homework.columns:
        my_homework = df_homework[df_homework["Uploaded By"] == st.session_state.user_name]
        st.write(f"📘 Total Homework Uploaded: {len(my_homework)}")
        for q in my_homework["Question"]:
            st.markdown(f"- {q}")
    else:
        st.warning("⚠️ 'Uploaded By' column not found in homework sheet.")