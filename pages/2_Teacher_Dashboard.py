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

    ALL_USERS_SHEET = client.open_by_key("1aCnuMxOlsJ3VkleK4wgTvMx2Sp-9pAMH").sheet1  # Now used for students too
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Google Sheets Connection Error: {e}")
    st.stop()

# === UTILITY FUNCTION ===
@st.cache_data(ttl=60)
def load_data(sheet):
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

# === LOAD SHEETS ===
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_answers = load_data(MASTER_ANSWER_SHEET)
df_users = load_data(ALL_USERS_SHEET)

# === TODAY'S SUBMISSIONS SUMMARY ===
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

# === TABS: CREATE / GRADE / REPORT ===
create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

# ------------------ TAB: CREATE HOMEWORK ------------------
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
            st.write("#### Current Questions in this Assignment:")
            for i, q in enumerate(st.session_state.questions_list):
                st.write(f"{i + 1}. {q}")
            if st.button("Final Submit Homework"):
                rows_to_add = [[ctx['class'], ctx['date'].strftime(DATE_FORMAT), st.session_state.user_name, ctx['subject'], q_text] for q_text in st.session_state.questions_list]
                HOMEWORK_QUESTIONS_SHEET.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                st.success("Homework submitted successfully!")
                st.balloons()
                del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                st.rerun()

        if st.button("Reset Homework Creation"):
            del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
            st.rerun()

# ------------------ TAB: GRADE ANSWERS ------------------
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
                st.info("No answers have been submitted for your questions yet.")
            else:
                df_my_answers['Marks'] = pd.to_numeric(df_my_answers['Marks'], errors='coerce')
                ungraded = df_my_answers[df_my_answers['Marks'].isna()]
                if ungraded.empty:
                    st.success("🎉 All submitted answers for your questions have been graded!")
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
                                    cell_row = i + 2
                                    marks_col = df_answers.columns.get_loc("Marks") + 1
                                    remarks_col = df_answers.columns.get_loc("Remarks") + 1
                                    MASTER_ANSWER_SHEET.update_cell(cell_row, marks_col, marks)
                                    MASTER_ANSWER_SHEET.update_cell(cell_row, remarks_col, remarks)
                                    st.success("Grade & remarks saved!")
                                    st.rerun()

# ------------------ TAB: MY REPORTS ------------------
with report_tab:
    st.subheader("My Reports")
    st.markdown("### Homework Report")
    df_homework['Date_dt'] = pd.to_datetime(df_homework['Date'], errors='coerce')
    teacher_homework = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]

    if teacher_homework.empty:
        st.info("No homework records found.")
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
            st.warning("No records in selected date range.")
        else:
            summary = filtered.groupby(['Class', 'Subject']).size().reset_index(name='Total')
            st.dataframe(summary)
            fig = px.bar(summary, x='Class', y='Total', color='Subject', title='Homework Summary')
            st.plotly_chart(fig, use_container_width=True)