import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
import base64
from google.oauth2.service_account import Credentials

# === PAGE CONFIG ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}

# === GOOGLE AUTH ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    # ✅ Correctly assigned Google Sheets
    ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Google API error: {e}")
    st.stop()

# === LOAD DATA ===
@st.cache_data(ttl=60)
def load_data(_sheet):
    values = _sheet.get_all_values()
    if not values:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    df.columns = df.columns.str.strip()
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY CHECK ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher.")
    st.stop()

st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === HEADER ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# === Load all sheets ===
df_users = load_data(ALL_USERS_SHEET)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_answers = load_data(MASTER_ANSWER_SHEET)

# ✅ Debug block with Subject column check
st.write("📋 Columns found in Master Answer Sheet:", df_answers.columns.tolist())
if "Subject" not in df_answers.columns:
    st.warning("⚠️ 'Subject' column not found in the answer sheet.")
    st.stop()

# === Tabs ===
tab1, tab2, tab3 = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

with tab1:
    st.subheader("Create Homework")
    subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST"])
    class_name = st.selectbox("Class", ["6th", "7th", "8th", "9th"])
    date_selected = st.date_input("Date", datetime.today())
    questions = []

    num_qs = st.number_input("Number of Questions", min_value=1, max_value=10, value=1)
    for i in range(num_qs):
        q = st.text_input(f"Question {i+1}", key=f"q_{i}")
        questions.append(q)

    if st.button("Submit Homework"):
        rows = [[class_name, date_selected.strftime(DATE_FORMAT), st.session_state.user_name, subject, q] for q in questions if q.strip()]
        if rows:
            HOMEWORK_QUESTIONS_SHEET.append_rows(rows)
            st.success("Homework uploaded.")
        else:
            st.warning("Enter at least one valid question.")

with tab2:
    st.subheader("Grade Student Answers")
    selected_class = st.selectbox("Select Class", df_users['Class'].unique())
    selected_subject = st.selectbox("Select Subject", ["Hindi", "English", "Math", "Science", "SST"])
    today = datetime.today().strftime(DATE_FORMAT)

    to_grade = df_answers[
        (df_answers['Subject'] == selected_subject) &
        (df_answers['Date'] == today) &
        (df_answers['Marks'] == "")
    ]

    if to_grade.empty:
        st.info("No ungraded answers.")
    else:
        for i, row in to_grade.iterrows():
            st.markdown(f"**Student:** {row['Student Gmail']} | **Question:** {row['Question']}")
            st.info(f"**Answer:** {row['Answer']}")
            with st.form(f"grade_form_{i}"):
                grade = st.selectbox("Grade", list(GRADE_MAP.keys()), key=f"grade_{i}")
                remark = st.text_area("Remarks", key=f"remark_{i}")
                if st.form_submit_button("Submit Grade"):
                    MASTER_ANSWER_SHEET.update(f"F{row['Row ID']}", GRADE_MAP[grade])
                    MASTER_ANSWER_SHEET.update(f"G{row['Row ID']}", remark)
                    st.success("Graded.")
                    st.rerun()

with tab3:
    st.subheader("My Reports")
    if "Uploaded By" in df_homework.columns:
        my_qs = df_homework[df_homework["Uploaded By"] == st.session_state.user_name]['Question'].tolist()
    else:
        st.warning("⚠️ 'Uploaded By' column missing.")
        my_qs = []

    st.write(f"You've uploaded {len(my_qs)} questions.")
    for q in my_qs:
        st.markdown(f"- {q}")