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
DATE_FORMAT = "%d-%m-%Y"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}

# === UTILITY FUNCTIONS ===
@st.cache_resource
def connect_to_gsheets():
    """Establishes a connection to Google Sheets and caches it."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
        credentials_dict = json.loads(decoded_creds)
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google APIs: {e}")
        return None

@st.cache_data(ttl=60)
def load_data(sheet_id):
    """Opens a sheet by its ID and loads the data. This works correctly with Streamlit's cache."""
    try:
        client = connect_to_gsheets()
        if client is None: return pd.DataFrame()
        sheet = client.open_by_key(sheet_id).sheet1
        all_values = sheet.get_all_values()
        if not all_values: return pd.DataFrame()
        df = pd.DataFrame(all_values[1:], columns=all_values[0])
        df.columns = df.columns.str.strip()
        df['Row ID'] = range(2, len(df) + 2)
        return df
    except Exception as e:
        st.error(f"Failed to load data for sheet ID {sheet_id}: {e}")
        return pd.DataFrame()

# === SHEET IDs ===
ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
HOMEWORK_QUESTIONS_SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
MASTER_ANSWER_SHEET_ID = "1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0"
ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to access this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === TEACHER DASHBOARD UI ===
st.image("PRK_logo.jpg", use_container_width=True)
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# --- INSTRUCTION & REPLY SYSTEM ---
df_users_live = load_data(ALL_USERS_SHEET_ID)
user_info_row = df_users_live[df_users_live['Gmail ID'] == st.session_state.user_gmail]
if not user_info_row.empty:
    user_info = user_info_row.iloc[0]
    instruction = user_info.get('Instruction', '').strip()
    reply = user_info.get('Instruction_Reply', '').strip()
    status = user_info.get('Instruction_Status', '')

    if status == 'Sent' and instruction and not reply:
        st.warning(f"**New Instruction from Principal:** {instruction}")
        with st.form(key="reply_form"):
            reply_text = st.text_area("Your Reply:")
            if st.form_submit_button("Send Reply"):
                if reply_text:
                    with st.spinner("Sending reply..."):
                        row_id = int(user_info.get('Row ID'))
                        reply_col = list(df_users_live.columns).index('Instruction_Reply') + 1
                        status_col = list(df_users_live.columns).index('Instruction_Status') + 1
                        client = connect_to_gsheets()
                        sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                        sheet.update_cell(row_id, reply_col, reply_text)
                        sheet.update_cell(row_id, status_col, "Replied")
                        st.success("Your reply has been sent.")
                        load_data.clear()
                        st.rerun()
                else:
                    st.warning("Reply cannot be empty.")
        st.markdown("---")

# Load all necessary data once
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET_ID)
df_all_answers = load_data(MASTER_ANSWER_SHEET_ID)
df_users = load_data(ALL_USERS_SHEET_ID)

# Display a summary of today's submitted homework
st.subheader("Today's Submitted Homework")
today_str = datetime.today().strftime(DATE_FORMAT)
todays_homework = df_homework[(df_homework.get('Uploaded By') == st.session_state.user_name) & (df_homework.get('Date') == today_str)]
if todays_homework.empty:
    st.info("You have not created any homework assignments today.")
else:
    summary = todays_homework.groupby(['Class', 'Subject']).size().reset_index(name='Question Count')
    for index, row in summary.iterrows():
        button_label = f"View -> Class: {row.get('Class')} | Subject: {row.get('Subject')} | Questions: {row.get('Question Count')}"
        if st.button(button_label, key=f"summary_{index}"):
            st.session_state.selected_assignment = {'Class': row.get('Class'), 'Subject': row.get('Subject'), 'Date': today_str}
            st.rerun()

# Display questions if an assignment is selected from the summary
if 'selected_assignment' in st.session_state:
    st.markdown("---")
    st.subheader("Viewing Questions for Selected Assignment")
    selected = st.session_state.selected_assignment
    st.info(f"Class: **{selected['Class']}** | Subject: **{selected['Subject']}** | Date: **{selected['Date']}**")
    selected_questions = df_homework[(df_homework['Class'] == selected['Class']) & (df_homework['Subject'] == selected['Subject']) & (df_homework['Date'] == selected['Date'])]
    for i, row in enumerate(selected_questions.itertuples()):
        st.write(f"{i + 1}. {row.Question}")
    if st.button("Back to Main View"):
        del st.session_state.selected_assignment
        st.rerun()

st.markdown("---")

create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

with create_tab:
    st.subheader("Create a New Homework Assignment")
    if 'context_set' not in st.session_state:
        st.session_state.context_set = False
    if not st.session_state.context_set:
        with st.form("context_form"):
            subject = st.selectbox("Subject", ["Hindi","Sanskrit","English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
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
                client = connect_to_gsheets()
                sheet = client.open_by_key(HOMEWORK_QUESTIONS_SHEET_ID).sheet1
                rows_to_add = [[ctx['class'], ctx['date'].strftime(DATE_FORMAT), st.session_state.user_name, ctx['subject'], q] for q in st.session_state.questions_list]
                sheet.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                load_data.clear()
                st.success("Homework submitted successfully!")
                del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                st.rerun()
        if st.session_state.context_set and st.button("Create Another Homework (Reset)"):
            del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
            st.rerun()

with grade_tab:
    st.subheader("Grade Student Answers")
    my_questions = df_homework[df_homework.get('Uploaded By') == st.session_state.user_name]['Question'].tolist()
    answers_to_my_questions = df_all_answers[df_all_answers['Question'].isin(my_questions)].copy()
    answers_to_my_questions['Marks'] = pd.to_numeric(answers_to_my_questions.get('Marks'), errors='coerce')
    ungraded = answers_to_my_questions[answers_to_my_questions['Marks'].isna()]

    if ungraded.empty:
        st.success("🎉 All answers for your questions have been graded!")
    else:
        student_gmails = ungraded['Student Gmail'].unique().tolist()
        df_students = df_users[df_users['Role'] == 'Student']
        gradable_students = df_students[df_students['Gmail ID'].isin(student_gmails)]
        if gradable_students.empty:
            st.info("No confirmed students have pending answers for your questions.")
        else:
            selected_student = st.selectbox("Select Student", gradable_students['User Name'].tolist())
            if selected_student:
                selected_gmail = gradable_students[gradable_students['User Name'] == selected_student].iloc[0]['Gmail ID']
                student_answers_df = ungraded[ungraded['Student Gmail'] == selected_gmail]
                st.markdown(f"#### Grading answers for: **{selected_student}**")
                for i, row in student_answers_df.sort_values(by='Date', ascending=False).iterrows():
                    st.write(f"**Question:** {row.get('Question')}")
                    st.info(f"**Answer:** {row.get('Answer')}")
                    with st.form(f"grade_form_{i}"):
                        grade = st.selectbox("Grade", list(GRADE_MAP.keys()), key=f"grade_{i}")
                        remarks = ""
                        if grade in ["Needs Improvement", "Average"]:
                            remarks = st.text_area("Remarks/Feedback (Required)", key=f"remarks_{i}")
                        if st.form_submit_button("Save Grade"):
                            if grade in ["Needs Improvement", "Average"] and not remarks.strip():
                                st.warning("Remarks are required for this grade.")
                            else:
                                with st.spinner("Saving..."):
                                    client = connect_to_gsheets()
                                    sheet = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
                                    row_id_to_update = int(row.get('Row ID'))
                                    marks_col = list(df_all_answers.columns).index("Marks") + 1
                                    remarks_col = list(df_all_answers.columns).index("Remarks") + 1
                                    sheet.update_cell(row_id_to_update, marks_col, GRADE_MAP[grade])
                                    sheet.update_cell(row_id_to_update, remarks_col, remarks)
                                    load_data.clear()
                                    st.success("Saved!")
                                    st.rerun()
                    st.markdown("---")

with report_tab:
    st.subheader("My Reports")
    
    # Report 1: Homework Creation Report
    st.markdown("#### Homework Creation Report")
    teacher_homework = df_homework[df_homework.get('Uploaded By') == st.session_state.user_name]
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
    
    # Report 2: Top Teachers Leaderboard
    st.subheader("🏆 Top Teachers Leaderboard")
    df_all_teachers = df_users[df_users['Role'] == 'Teacher'].copy()
    df_all_teachers['Salary Points'] = pd.to_numeric(df_all_teachers.get('Salary Points', 0), errors='coerce').fillna(0)
    if df_all_teachers.empty:
        st.info("The teacher leaderboard will appear here once teachers start grading.")
    else:
        ranked_teachers = df_all_teachers.sort_values(by='Salary Points', ascending=False)
        ranked_teachers['Rank'] = range(1, len(ranked_teachers) + 1)
        st.dataframe(ranked_teachers[['Rank', 'User Name', 'Salary Points']])
        fig_leaderboard = px.bar(
            ranked_teachers.head(10), x='User Name', y='Salary Points',
            title='Top Teachers by Performance Points',
            labels={'Salary Points': 'Total Points Earned', 'User Name': 'Teacher'}, text='Salary Points'
        )
        fig_leaderboard.update_traces(textposition='outside')
        st.plotly_chart(fig_leaderboard, use_container_width=True)

    st.markdown("---")

    # --- Top 3 Students Report ---
    st.subheader("🥇 Class-wise Top 3 Students")
    df_students_report = df_users[df_users['Role'] == 'Student']
    if df_all_answers.empty or df_students_report.empty:
        st.info("Leaderboard will be generated once students are graded.")
    else:
        df_all_answers['Marks'] = pd.to_numeric(df_all_answers.get('Marks'), errors='coerce')
        graded_answers = df_all_answers.dropna(subset=['Marks'])
        if graded_answers.empty:
            st.info("The leaderboard is available after answers have been graded.")
        else:
            df_merged = pd.merge(graded_answers, df_students_report, left_on='Student Gmail', right_on='Gmail ID')
            leaderboard_df = df_merged.groupby(['Class', 'User Name'])['Marks'].mean().reset_index()
            
            # --- FIX: Create the 'Rank' column before displaying it ---
            leaderboard_df['Rank'] = leaderboard_df.groupby('Class')['Marks'].rank(method='dense', ascending=False).astype(int)
            leaderboard_df = leaderboard_df.sort_values(by=['Class', 'Rank'])
            
            top_students_df = leaderboard_df.groupby('Class').head(3).reset_index(drop=True)
            top_students_df['Marks'] = top_students_df['Marks'].round(2)
            
            st.markdown("#### Top Performers Summary")
            st.dataframe(top_students_df[['Rank', 'User Name', 'Class', 'Marks']])

