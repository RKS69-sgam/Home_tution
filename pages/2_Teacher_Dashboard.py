import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}

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
    df.columns = df.columns.str.strip()
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to access this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === TEACHER DASHBOARD UI ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# Load all necessary data once
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_all_answers = load_data(MASTER_ANSWER_SHEET)
df_users = load_data(ALL_USERS_SHEET)

# Display a summary of today's submitted homework
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
    for index, row in summary.iterrows():
        st.success(f"Class: **{row.get('Class')}** | Subject: **{row.get('Subject')}** | Questions: **{row.get('Question Count')}**")

st.markdown("---")

create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

with create_tab:
    st.subheader("Create a New Homework Assignment")
    if 'context_set' not in st.session_state:
        st.session_state.context_set = False
    if not st.session_state.context_set:
        with st.form("context_form"):
            subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
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
                rows_to_add = [[ctx['class'], ctx['date'].strftime(DATE_FORMAT), st.session_state.user_name, ctx['subject'], q_text] for q_text in st.session_state.questions_list]
                HOMEWORK_QUESTIONS_SHEET.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                st.success("Homework submitted successfully!")
                del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                st.rerun()
        if st.session_state.context_set and st.button("Create Another Homework (Reset)"):
            del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
            st.rerun()

with grade_tab:
    st.subheader("Grade Student Answers")
    if 'Question' not in df_all_answers.columns:
        st.error("The 'Question' column is missing from MASTER_ANSWER_SHEET. Please fix the headers.")
    else:
        my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]['Question'].tolist()
        df_my_answers = df_all_answers[df_all_answers['Question'].isin(my_questions)].copy()

        if df_my_answers.empty:
            st.info("No answers submitted for your questions yet.")
        else:
            df_my_answers['Marks'] = pd.to_numeric(df_my_answers['Marks'], errors='coerce')
            ungraded = df_my_answers[df_my_answers['Marks'].isna()]
            if ungraded.empty:
                st.success("🎉 All answers for your questions have been graded!")
            else:
                student_gmails = ungraded['Student Gmail'].unique().tolist()
                df_students = df_users[df_users['Role'] == 'Student']
                gradable_students = df_students[df_students['Gmail ID'].isin(student_gmails)]
                if gradable_students.empty:
                    st.info("No confirmed students have pending answers.")
                else:
                    selected_student = st.selectbox("Select Student", gradable_students['User Name'].tolist())
                    if selected_student:
                        selected_gmail = gradable_students[gradable_students['User Name'] == selected_student].iloc[0]['Gmail ID']
                        student_answers = df_my_answers[df_my_answers['Student Gmail'] == selected_gmail]
                        for i, row in student_answers[student_answers['Marks'].isna()].iterrows():
                            st.markdown(f"**Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                            st.write(f"**Question:** {row.get('Question')}")
                            st.info(f"**Answer:** {row.get('Answer')}")
                            with st.form(f"grade_form_{i}"):
                                grade = st.selectbox("Grade", list(GRADE_MAP.keys()), key=f"grade_{i}")
                                remarks = st.text_area("Remarks", key=f"remarks_{i}")
                                if st.form_submit_button("Save Grade"):
                                    sheet = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
                                    row_id_to_update = row.get('Row ID')
                                    marks_col = df_all_answers.columns.get_loc("Marks") + 1
                                    remarks_col = df_all_answers.columns.get_loc("Remarks") + 1
                                    sheet.update_cell(row_id_to_update, marks_col, GRADE_MAP[grade])
                                    sheet.update_cell(row_id_to_update, remarks_col, remarks)
                                    st.success("Saved!")
                                    st.rerun()
                            st.markdown("---")

with report_tab:
    st.subheader("My Reports")
    teacher_homework = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]
    if teacher_homework.empty:
        st.info("No homework created yet.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.today() - timedelta(days=7))
        with col2:
            end_date = st.date_input("End Date", datetime.today())
        
        teacher_homework['Date_dt'] = pd.to_datetime(teacher_homework['Date'], errors='coerce').dt.date
        filtered = teacher_homework[
            (teacher_homework['Date_dt'] >= start_date) &
            (teacher_homework['Date_dt'] <= end_date)
        ]
        if filtered.empty:
            st.warning("No homework found in selected range.")
        else:
            summary = filtered.groupby(['Class', 'Subject']).size().reset_index(name='Total')
            st.dataframe(summary)
            fig = px.bar(summary, x='Class', y='Total', color='Subject', title='Homework Summary')
            st.plotly_chart(fig, use_container_width=True)
            
    st.markdown("---")
    
    st.subheader("📊 Class-wise Top 3 Students")
    df_students_report = df_users[df_users['Role'] == 'Student']

    if df_all_answers.empty or df_students_report.empty:
        st.info("Leaderboard will be generated once students submit and get graded.")
    else:
        graded_answers = df_all_answers.dropna(subset=['Marks'])
        if graded_answers.empty:
            st.info("The leaderboard is available after answers have been graded.")
        else:
            df_merged = pd.merge(graded_answers, df_students_report, left_on='Student Gmail', right_on='Gmail ID')
            leaderboard_df = df_merged.groupby(['Class', 'User Name'])['Marks'].mean().reset_index()
            top_students_df = leaderboard_df.groupby('Class').apply(lambda x: x.nlargest(3, 'Marks')).reset_index(drop=True)
            top_students_df['Marks'] = top_students_df['Marks'].round(2)
            st.markdown("#### Top Performers Summary")
            st.dataframe(top_students_df)
            
            fig_leaderboard = px.bar(
                top_students_df, 
                x='User Name', 
                y='Marks', 
                color='User Name',
                title='Top 3 Students by Average Marks per Class',
                labels={'Marks': 'Average Marks', 'User Name': 'Student'},
                text='Marks'
            )
            fig_leaderboard.update_traces(textposition='outside')
            st.plotly_chart(fig_leaderboard, use_container_width=True)
