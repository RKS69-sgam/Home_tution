import streamlit as st
import pandas as pd
import gspread
import base64
import json
from datetime import date
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide", page_title="Teacher Dashboard")

# === GOOGLE SHEET AUTH ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    STUDENT_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
    HOMEWORK_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === LOAD DATA ===
def load_df(sheet):
    values = sheet.get_all_values()
    if not values:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    df.columns = df.columns.str.strip()
    return df

df_students = load_df(STUDENT_SHEET)
df_homework = load_df(HOMEWORK_SHEET)
df_answers = load_df(ANSWER_SHEET)

# === TEACHER LOGIN CHECK ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher.")
    st.stop()

st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# === TABS ===
tabs = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

# === CREATE HOMEWORK ===
with tabs[0]:
    st.subheader("Create a New Homework Assignment")
    ctx = {}
    ctx['subject'] = st.selectbox("Subject", options=["Hindi", "English", "Maths", "Science", "SST"])
    ctx['class'] = st.selectbox("Class", options=["6th", "7th", "8th", "9th"])
    ctx['date'] = st.date_input("Date", value=date.today())
    ctx['num_questions'] = st.number_input("Number of Questions", min_value=1, max_value=10, step=1)

    st.markdown("### ✍️ Enter Questions")
    if "questions_list" not in st.session_state:
        st.session_state.questions_list = [""] * ctx['num_questions']

    for i in range(ctx['num_questions']):
        st.session_state.questions_list[i] = st.text_input(f"Question {i+1}", value=st.session_state.questions_list[i])

    if st.button("✅ Submit Homework"):
        if all(q.strip() for q in st.session_state.questions_list):
            rows_to_add = [
                [ctx['class'], ctx['date'].strftime("%Y-%m-%d"), st.session_state.user_name, ctx['subject'], q_text]
                for q_text in st.session_state.questions_list
            ]
            HOMEWORK_SHEET.append_rows(rows_to_add)
            st.success("Homework uploaded successfully!")
        else:
            st.warning("Please fill all questions before submitting.")

# === GRADE ANSWERS ===
with tabs[1]:
    st.subheader("Review and Grade Student Answers")
    student_list = df_answers['Student Gmail'].unique().tolist() if 'Student Gmail' in df_answers.columns else []

    selected_student = st.selectbox("Select Student", options=student_list)
    student_records = df_answers[df_answers['Student Gmail'] == selected_student]

    if not student_records.empty:
        for idx, row in student_records.iterrows():
            st.markdown(f"**Date:** {row['Date']} | **Subject:** {row['Subject']}")
            st.markdown(f"**Question:** {row['Question']}")
            st.info(f"**Student Answer:** {row['Answer']}")
            marks = st.slider("Marks (out of 5)", 0, 5, key=f"marks_{idx}")
            remark = st.text_input("Remarks", key=f"remark_{idx}")
            if st.button("Submit Grade", key=f"grade_{idx}"):
                row_id = idx + 2
                ANSWER_SHEET.update_cell(row_id, df_answers.columns.get_loc("Marks") + 1, marks)
                ANSWER_SHEET.update_cell(row_id, df_answers.columns.get_loc("Remarks") + 1, remark)
                st.success("Grade saved.")

# === MY REPORTS ===
with tabs[2]:
    st.subheader("Your Homework Contributions")
    
    if "Uploaded By" in df_homework.columns:
        my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]['Question'].tolist()
    else:
        st.warning("⚠️ 'Uploaded By' column not found in homework sheet.")
        my_questions = []

    st.write(f"📚 You have contributed {len(my_questions)} questions.")
    for q in my_questions:
        st.markdown(f"- {q}")