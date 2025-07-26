import streamlit as st
import pandas as pd
import gspread
import json
import base64
from datetime import date
from google.oauth2.service_account import Credentials

# === PAGE CONFIG ===
st.set_page_config(page_title="Teacher Dashboard", layout="wide")

# === GOOGLE AUTHENTICATION ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(base64.b64decode(st.secrets["google_service"]["base64_credentials"]))
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
except Exception as e:
    st.error(f"Google API error: {e}")
    st.stop()

# === UTILITY FUNCTION TO LOAD SHEET DATA ===
@st.cache_data(ttl=60)
def load_data(sheet_key, worksheet_index=0):
    sheet = client.open_by_key(sheet_key)
    worksheet = sheet.get_worksheet(worksheet_index)
    data = worksheet.get_all_values()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = df.columns.str.strip()
    return df

# === SHEET KEYS ===
USERS_SHEET_KEY = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
QUESTIONS_SHEET_KEY = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
ANSWERS_SHEET_KEY = "16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8"

# === SESSION VALIDATION ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("Please login as a teacher to access this page.")
    st.stop()

st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# === LOAD DATA ===
df_users = load_data(USERS_SHEET_KEY)
df_homework = load_data(QUESTIONS_SHEET_KEY)
df_answers = load_data(ANSWERS_SHEET_KEY)

# === DEBUG: Show columns to ensure correct sheet is loaded ===
with st.expander("📋 Columns found in Master Answer Sheet:", expanded=False):
    st.write(df_answers.columns.tolist())

# === DASHBOARD UI ===
action = st.radio("Choose an action", ["Create Homework", "Grade Answers", "My Reports"])

# === CREATE HOMEWORK ===
if action == "Create Homework":
    st.subheader("Create a New Homework Assignment")
    subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "Social Science"])
    class_selected = st.selectbox("Class", sorted(df_users['Class'].dropna().unique()))
    date_selected = st.date_input("Date", date.today())
    question_text = st.text_area("Enter the homework question")

    if st.button("Submit Homework"):
        if question_text.strip():
            new_row = {
                "Class": class_selected,
                "Subject": subject,
                "Date": date_selected.strftime("%Y-%m-%d"),
                "Question": question_text.strip(),
                "Uploaded By": st.session_state.user_name
            }
            sheet = client.open_by_key(QUESTIONS_SHEET_KEY).sheet1
            sheet.append_row(list(new_row.values()))
            st.success("Homework submitted successfully!")
        else:
            st.warning("Please enter a question before submitting.")

# === GRADE ANSWERS ===
elif action == "Grade Answers":
    st.subheader("Review and Grade Student Answers")
    selected_class = st.selectbox("Select Class", sorted(df_users['Class'].dropna().unique()))
    selected_subject = st.selectbox("Select Subject", df_answers['Subject'].dropna().unique())

    df_class_answers = df_answers[
        (df_answers['Class'] == selected_class) &
        (df_answers['Subject'] == selected_subject)
    ]

    if df_class_answers.empty:
        st.info("No answers found for the selected filters.")
    else:
        for i, row in df_class_answers.iterrows():
            st.markdown(f"### 📅 {row.get('Date')} | 👧 {row.get('Student Gmail')}")
            st.write(f"**Q:** {row.get('Question')}")
            st.info(f"**Answer:** {row.get('Answer')}")
            with st.form(key=f"grade_form_{i}"):
                marks = st.slider("Marks (out of 5)", 0, 5, int(row.get("Marks") or 0))
                remarks = st.text_input("Remarks", value=row.get("Remarks", ""))
                if st.form_submit_button("Submit Grade"):
                    worksheet = client.open_by_key(ANSWERS_SHEET_KEY).sheet1
                    row_number = int(i) + 2  # +2 because 0-indexed and header
                    worksheet.update(f"F{row_number}", str(marks))     # Marks
                    worksheet.update(f"G{row_number}", remarks)        # Remarks
                    st.success("Grade updated successfully.")
                    st.rerun()

# === REPORTS ===
elif action == "My Reports":
    st.subheader("My Submitted Homework")
    my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]
    if my_questions.empty:
        st.info("No homework submitted yet.")
    else:
        st.dataframe(my_questions[['Date', 'Class', 'Subject', 'Question']])