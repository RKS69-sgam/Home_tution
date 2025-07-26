import streamlit as st
import pandas as pd
import gspread
import json
import base64
from google.oauth2.service_account import Credentials
from datetime import date

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")

# === GOOGLE SHEET AUTHENTICATION ===
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
credentials_dict = json.loads(decoded_creds)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
client = gspread.authorize(credentials)

# === GOOGLE SHEET REFERENCES ===
ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1  # ✅ Correct sheet

# === UTILITY ===
@st.cache_data(ttl=60)
def load_data(sheet):
    data = sheet.get_all_values()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = df.columns.str.strip()
    return df

# === AUTH CHECK ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("Only teachers can access this page.")
    st.stop()

# === SIDEBAR ===
st.sidebar.success(f"Welcome {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === DASHBOARD HEADER ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")
st.markdown("##")

option = st.radio("Choose an action", ["Create Homework", "Grade Answers", "My Reports"])

# === LOAD SHEETS ===
df_users = load_data(ALL_USERS_SHEET)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_answers = load_data(MASTER_ANSWER_SHEET)  # ✅ Correct loading

# === DEBUG CHECK ===
st.write("📋 Columns found in Master Answer Sheet:", df_answers.columns.tolist())
if "Subject" not in df_answers.columns:
    st.warning("⚠️ 'Subject' column not found in the answer sheet.")
    st.stop()

# === MAIN OPTIONS ===
if option == "Create Homework":
    st.subheader("Create a New Homework Assignment")
    subject = st.selectbox("Subject", ["Hindi", "English", "Maths", "Science", "Sanskrit"])
    class_name = st.selectbox("Class", sorted(df_users['Class'].unique()))
    today_date = st.date_input("Date", value=date.today())
    question_text = st.text_area("Enter the Homework Question")

    if st.button("Submit Homework"):
        if question_text.strip():
            row = [str(today_date), class_name, subject, question_text.strip(), st.session_state.user_name]
            HOMEWORK_QUESTIONS_SHEET.append_row(row)
            st.success("✅ Homework uploaded successfully!")
        else:
            st.warning("Question cannot be empty.")

elif option == "Grade Answers":
    st.subheader("Grade Answers")
    selected_class = st.selectbox("Select Class", sorted(df_users['Class'].unique()))
    selected_subject = st.selectbox("Select Subject", df_answers['Subject'].dropna().unique())

    filtered = df_answers[
        (df_answers['Class'] == selected_class) &
        (df_answers['Subject'] == selected_subject)
    ]

    if filtered.empty:
        st.info("No answers to grade.")
    else:
        for i, row in filtered.iterrows():
            st.markdown(f"**Student:** {row.get('Student Gmail')} | **Date:** {row.get('Date')}")
            st.markdown(f"**Question:** {row.get('Question')}")
            st.markdown(f"**Answer:** {row.get('Answer')}")
            with st.form(f"grade_form_{i}"):
                marks = st.slider("Marks (0–5)", 0, 5, int(row.get("Marks") or 0))
                remarks = st.text_area("Remarks", row.get("Remarks", ""))
                if st.form_submit_button("Submit Grade"):
                    MASTER_ANSWER_SHEET.update_cell(i + 2, df_answers.columns.get_loc("Marks") + 1, str(marks))
                    MASTER_ANSWER_SHEET.update_cell(i + 2, df_answers.columns.get_loc("Remarks") + 1, remarks)
                    st.success("Graded successfully.")
                    st.rerun()
            st.markdown("---")

elif option == "My Reports":
    st.subheader("Homework You Uploaded")
    my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]
    st.dataframe(my_questions[['Date', 'Class', 'Subject', 'Question']])