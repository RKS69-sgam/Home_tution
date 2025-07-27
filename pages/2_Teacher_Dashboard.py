import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import plotly.express as px
from google.oauth2.service_account import Credentials

# === PAGE CONFIG ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%Y-%m-%d"

# === GOOGLE SHEET SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)
except Exception as e:
    st.error(f"Google Sheets Connection Error: {e}")
    st.stop()

# === SHEET IDS ===
ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
HOMEWORK_QUESTIONS_SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
MASTER_ANSWER_SHEET_ID = "16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8"

# === UTILITY FUNCTION ===
def load_data_by_key(sheet_id, sheet_index=0):
    sheet = client.open_by_key(sheet_id).get_worksheet(sheet_index)
    all_values = sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df.columns = df.columns.str.strip()
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === AUTH CHECK ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to access this page.")
    st.stop()

# === HEADER ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# --- DEBUGGING CODE START ---
st.warning("RUNNING DEBUG TEST FOR HOMEWORK_QUESTIONS_SHEET")
    
    try:
        df_homework_debug = load_data(HOMEWORK_QUESTIONS_SHEET)
        
        st.write("Columns found in HOMEWORK_QUESTIONS_SHEET:")
        st.write(list(df_homework_debug.columns))
        
        st.write("First 5 rows of data:")
        st.dataframe(df_homework_debug.head())
        
    except Exception as e:
        st.error("An error occurred while reading the sheet:")
        st.exception(e)

    st.stop()
    # --- DEBUGGING CODE END ---

# === LOAD DATA ===
df_homework = load_data_by_key(HOMEWORK_QUESTIONS_SHEET_ID)
df_answers = load_data_by_key(MASTER_ANSWER_SHEET_ID)
df_users = load_data_by_key(ALL_USERS_SHEET_ID)

# === TODAY'S SUBMISSIONS ===
st.subheader("Today's Submitted Homework")
today_str = datetime.today().strftime(DATE_FORMAT)
todays_homework = df_homework[
    (df_homework.get('Uploaded By') == st.session_state.user_name) &
    (df_homework.get('Date') == today_str)
]

if todays_homework.empty:
    st.info("You have not created any homework assignments today.")
else:
    summary = todays_homework.groupby(['Class', 'Subject']).size().reset_index(name='Question Count')
    for _, row in summary.iterrows():
        st.success(f"Class: **{row['Class']}** | Subject: **{row['Subject']}** | Questions: **{row['Question Count']}**")

st.markdown("---")

# === TABS ===
create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

# ---------------- CREATE TAB ----------------
with create_tab:
    st.subheader("Create a New Homework Assignment")

    if 'context_set' not in st.session_state:
        st.session_state.context_set = False

    if not st.session_state.context_set:
        with st.form("context_form"):
            subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK"])
            cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
            date = st.date_input("Date", datetime.today())
            if st.form_submit_button("Start Adding Questions →"):
                st.session_state.context_set = True
                st.session_state.homework_context = {"subject": subject, "class": cls, "date": date}
                st.session_state.questions_list = []
                st.rerun()

    if st.session_state.context_set:
        ctx = st.session_state.homework_context
        st.success(f"Creating homework for: **{ctx['class']} - {ctx['subject']}** (Date: {ctx['date'].strftime(DATE_FORMAT)})")
        with st.form("add_question_form", clear_on_submit=True):
            question_text = st.text_area("Enter a question to add:", height=100)
            if st.form_submit_button("Add Question") and question_text:
                st.session_state.questions_list.append(question_text)

        if st.session_state.questions_list:
            st.write("#### Current Questions:")
            for i, q in enumerate(st.session_state.questions_list):
                st.write(f"{i + 1}. {q}")
            if st.button("Final Submit Homework"):
                sheet = client.open_by_key(HOMEWORK_QUESTIONS_SHEET_ID).sheet1
                rows_to_add = [[ctx['class'], ctx['date'].strftime(DATE_FORMAT), st.session_state.user_name, ctx['subject'], q] for q in st.session_state.questions_list]
                sheet.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                st.success("Homework submitted successfully!")
                st.balloons()
                del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                st.rerun()

        if st.button("Reset Homework Creation"):
            del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
            st.rerun()

# ---------------- GRADE TAB ----------------
with grade_tab:
    st.subheader("Grade Student Answers")

    if 'Remarks' not in df_answers.columns:
        st.error("❌ 'Remarks' column not found in MASTER_ANSWER_SHEET.")
    else:
        if 'Question' not in df_answers.columns or 'Student Gmail' not in df_answers.columns:
            st.warning("❌ Required columns like 'Question' or 'Student Gmail' missing in answer sheet.")
        else:
            my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]['Question'].tolist()
            df_my_answers = df_answers[df_answers['Question'].isin(my_questions)].copy()

            if df_my_answers.empty:
                st.info("No answers submitted for your questions yet.")
            else:
                df_my_answers['Marks'] = pd.to_numeric(df_my_answers['Marks'], errors='coerce')
                ungraded = df_my_answers[df_my_answers['Marks'].isna()]
                if ungraded.empty:
                    st.success("🎉 All answers graded!")
                else:
                    student_gmails = ungraded['Student Gmail'].unique().tolist()
                    gradable_students = df_users[df_users['Gmail ID'].isin(student_gmails)]
                    gradable_students = gradable_students.rename(columns={'User Name': 'Student Name'})

                    selected_student = st.selectbox("Select Student", gradable_students['Student Name'].tolist())
                    if selected_student:
                        selected_gmail = gradable_students[gradable_students['Student Name'] == selected_student].iloc[0]['Gmail ID']
                        student_answers = df_my_answers[df_my_answers['Student Gmail'] == selected_gmail]

                        for i, row in student_answers[student_answers['Marks'].isna()].iterrows():
                            st.markdown(f"**Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                            st.write(f"**Question:** {row.get('Question')}")
                            st.info(f"**Answer:** {row.get('Answer')}")
                            with st.form(f"grade_form_{i}"):
                                marks = st.number_input("Marks", min_value=0, max_value=5, value=0, key=f"marks_{i}")
                                remarks = st.text_area("Remarks", key=f"remarks_{i}")
                                if st.form_submit_button("Save Grade"):
                                    sheet = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
                                    cell_row = i + 2
                                    marks_col = df_answers.columns.get_loc("Marks") + 1
                                    remarks_col = df_answers.columns.get_loc("Remarks") + 1
                                    sheet.update_cell(cell_row, marks_col, marks)
                                    sheet.update_cell(cell_row, remarks_col, remarks)
                                    st.success("Saved!")
                                    st.rerun()

# ---------------- REPORT TAB ----------------
with report_tab:
    st.subheader("My Reports")
    df_homework['Date_dt'] = pd.to_datetime(df_homework['Date'], errors='coerce')
    teacher_homework = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]

    if teacher_homework.empty:
        st.info("No homework created yet.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.today() - timedelta(days=7))
        with col2:
            end_date = st.date_input("End Date", datetime.today())
        filtered = teacher_homework[
            (teacher_homework['Date_dt'] >= pd.to_datetime(start_date)) &
            (teacher_homework['Date_dt'] <= pd.to_datetime(end_date))
        ]
        if filtered.empty:
            st.warning("No homework found in selected range.")
        else:
            summary = filtered.groupby(['Class', 'Subject']).size().reset_index(name='Total')
            st.dataframe(summary)
            fig = px.bar(summary, x='Class', y='Total', color='Subject', title='Homework Summary')
            st.plotly_chart(fig, use_container_width=True)
