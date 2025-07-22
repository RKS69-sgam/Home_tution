import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt
import gspread
import json
import base64
import mimetypes
import hashlib
import plotly.express as px
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition")
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
DATE_FORMAT = "%Y-%m-%d"

# === GOOGLE IDs ===
HOMEWORK_FOLDER_ID = "1e83Kseh47VMiKep7DKdOHr9ciwrbMyiO"
NOTEBOOK_FOLDER_ID = "1e9UpIdbkAw6AnUa3xAixIcdih5K9TRAH"
RECEIPT_FOLDER_ID = "1e9se9uNbpjdFGhzzOi1GdhYRcG4ZOmxn"

# === AUTHENTICATION ===
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
try:
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    drive_service = build("drive", "v3", credentials=credentials)
except Exception as e:
    st.error("Error connecting to Google APIs. Please check credentials and sharing permissions.")
    st.stop()

# === GOOGLE SHEETS ===
try:
    STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
    TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Could not open Google Sheets. Ensure all Sheet Keys are correct and shared with the service account: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if hashed_text:
        return make_hashes(password) == hashed_text
    return False

def upload_to_drive(path, folder_id, filename):
    try:
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        media = MediaFileUpload(path, mimetype=mime_type, resumable=True)
        metadata = {"name": filename, "parents": [folder_id]}
        file = drive_service.files().create(body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True).execute()
        return file.get('webViewLink')
    except HttpError as error:
        st.error(f"An error occurred while uploading to Google Drive: {error}")
        return None

def create_answer_docx(student_name, student_class, answers_df):
    doc = Document()
    doc.add_heading('PRK Home Tuition - Submitted Answers', 0)
    doc.add_paragraph(f"**Student:** {student_name}")
    doc.add_paragraph(f"**Class:** {student_class}")
    doc.add_paragraph(f"**Date Generated:** {datetime.now().strftime(DATE_FORMAT)}")
    doc.add_paragraph()
    for (date, subject), group in answers_df.groupby(['Date', 'Subject']):
        doc.add_heading(f"Subject: {subject} (Assignment Date: {date})", level=2)
        for i, row in group.iterrows():
            p = doc.add_paragraph()
            p.add_run('Question: ').bold = True
            p.add_run(row.get('Question', ''))
            p_ans = doc.add_paragraph()
            p_ans.add_run('Your Answer: ').italic = True
            p_ans.add_run(row.get('Answer', ''))
            doc.add_paragraph()
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- FIX: Corrected and robust load_data function ---
def load_data(sheet):
    """
    Loads all data from a Google Sheet and correctly assigns the 
    first row as the header. This is more robust.
    """
    all_values = sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()  # Return empty dataframe if sheet is empty
    
    headers = all_values[0]
    data = all_values[1:]
    df = pd.DataFrame(data, columns=headers)
    return df

def save_students_data(df):
    df_str = df.fillna("").astype(str)
    STUDENT_SHEET.clear()
    STUDENT_SHEET.update([df_str.columns.values.tolist()] + df_str.values.tolist())

def save_teachers_data(df):
    df_str = df.fillna("").astype(str)
    TEACHER_SHEET.clear()
    TEACHER_SHEET.update([df_str.columns.values.tolist()] + df_str.values.tolist())

# === SESSION STATE INITIALIZATION ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""

# === SIDEBAR & HEADER ===
st.sidebar.title("Login / Register")
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

# --- YEH BADLAV KAREN ---
# Use columns to center the logo and title
col1, col2 = st.columns([1, 4]) # Adjust the ratio if needed

with col1:
    st.image("logo.jpg", width=100) # Adjust width as needed

with col2:
    st.title("PRK Home Tuition App")

st.markdown("---")
# -----------------------


# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    role = st.sidebar.radio("Login As:", ["Student", "Teacher", "Register", "Admin", "Principal"])

    if role == "Register":
        st.header("✍️ Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            with st.form("student_registration_form", clear_on_submit=True):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
                pwd = st.text_input("Password", type="password")
                if st.form_submit_button("Register (After Payment)"):
                    if not all([name, gmail, cls, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df = load_data(STUDENT_SHEET)
                        if not df.empty and gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            hashed_password = make_hashes(pwd)
                            till_date = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime(DATE_FORMAT)
                            new_row = {"Sr. No.": len(df) + 1, "Student Name": name, "Gmail ID": gmail, "Class": cls, "Password": hashed_password, "Subscription Date": "", "Subscribed Till": till_date, "Payment Confirmed": "No", "Answer Sheet ID": ""}
                            df_new = pd.DataFrame([new_row])
                            df = pd.concat([df, df_new], ignore_index=True)
                            save_students_data(df)
                            st.success("Registration successful! Waiting for payment confirmation.")
                            st.balloons()
            st.subheader("Payment Details")
            st.code(f"UPI ID: {UPI_ID}", language="text")
        
        elif registration_type == "Teacher":
            with st.form("teacher_registration_form", clear_on_submit=True):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                pwd = st.text_input("Password", type="password")
                if st.form_submit_button("Register Teacher"):
                    if not all([name, gmail, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df_teachers = load_data(TEACHER_SHEET)
                        if not df_teachers.empty and gmail in df_teachers["Gmail ID"].values:
                            st.error("This Gmail is already registered as a teacher.")
                        else:
                            hashed_password = make_hashes(pwd)
                            new_row = {"Sr. No.": len(df_teachers) + 1, "Teacher Name": name, "Gmail ID": gmail, "Password": hashed_password, "Confirmed": "No"}
                            df_new = pd.DataFrame([new_row])
                            df_teachers = pd.concat([df_teachers, df_new], ignore_index=True)
                            save_teachers_data(df_teachers)
                            st.success("Teacher registered! Please wait for admin confirmation.")
                            st.balloons()
    else:
        st.header(f"🔑 {role} Login")
        with st.form(f"{role}_login_form"):
            login_gmail = st.text_input("Gmail ID").lower().strip()
            login_pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                sheet_to_check = TEACHER_SHEET if role in ["Admin", "Principal", "Teacher"] else STUDENT_SHEET
                name_col = "Teacher Name" if role in ["Admin", "Principal", "Teacher"] else "Student Name"

                df_users = load_data(sheet_to_check)
                if not df_users.empty:
                    user_data = df_users[df_users["Gmail ID"] == login_gmail]

                    if not user_data.empty:
                        user_row = user_data.iloc[0]
                        if check_hashes(login_pwd, user_row.get("Password")):
                            can_login = False
                            if role == "Student":
                                if user_row.get("Payment Confirmed") == "Yes" and datetime.today() <= pd.to_datetime(user_row.get("Subscribed Till")):
                                    can_login = True
                                else:
                                    st.error("Subscription expired or not confirmed.")
                            elif role == "Teacher":
                                if user_row.get("Confirmed") == "Yes":
                                    can_login = True
                                else:
                                    st.error("Registration is pending admin confirmation.")
                            elif role in ["Admin", "Principal"]:
                                can_login = True

                            if can_login:
                                st.session_state.logged_in = True
                                st.session_state.user_name = user_row.get(name_col)
                                st.session_state.user_role = role.lower()
                                st.session_state.user_gmail = login_gmail
                                st.rerun()
                        else:
                            st.error("Invalid Gmail ID or Password.")
                    else:
                        st.error("Invalid Gmail ID or Password.")
                else:
                    st.error("User database is empty or could not be loaded.")

# === LOGGED-IN USER PANELS ===
if st.session_state.logged_in:
    current_role = st.session_state.user_role

    if current_role == "admin":
        st.header("👑 Admin Panel")
        tab1, tab2 = st.tabs(["Student Management", "Teacher Management"])

        with tab1:
            st.subheader("Manage Student Registrations")
            df_students = load_data(STUDENT_SHEET)
            st.markdown("#### Pending Payment Confirmations")
            unconfirmed_students = df_students[df_students.get("Payment Confirmed") != "Yes"]
            if unconfirmed_students.empty:
                st.info("No pending student payments.")
            else:
                for i, row in unconfirmed_students.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Name:** {row.get('Student Name')} | **Gmail:** {row.get('Gmail ID')}")
                    with col2:
                        if st.button("✅ Confirm Payment", key=f"confirm_student_{row.get('Gmail ID')}", use_container_width=True):
                            df_students.loc[i, "Subscription Date"] = datetime.today().strftime(DATE_FORMAT)
                            df_students.loc[i, "Subscribed Till"] = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime(DATE_FORMAT)
                            df_students.loc[i, "Payment Confirmed"] = "Yes"
                            save_students_data(df_students)
                            st.success(f"Payment confirmed for {row.get('Student Name')}.")
                            st.rerun()
            st.markdown("---")
            st.markdown("#### Confirmed Students")
            confirmed_students = df_students[df_students.get("Payment Confirmed") == "Yes"]
            st.dataframe(confirmed_students)

        with tab2:
            st.subheader("Manage Teacher Registrations")
            df_teachers = load_data(TEACHER_SHEET)
            st.markdown("#### Pending Teacher Confirmations")
            unconfirmed_teachers = df_teachers[df_teachers.get("Confirmed") != "Yes"]
            if unconfirmed_teachers.empty:
                st.info("No pending teacher confirmations.")
            else:
                for i, row in unconfirmed_teachers.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Name:** {row.get('Teacher Name')} | **Gmail:** {row.get('Gmail ID')}")
                    with col2:
                        if st.button("✅ Confirm Teacher", key=f"confirm_teacher_{row.get('Gmail ID')}", use_container_width=True):
                            df_teachers.loc[i, "Confirmed"] = "Yes"
                            save_teachers_data(df_teachers)
                            st.success(f"Teacher {row.get('Teacher Name')} confirmed.")
                            st.rerun()
            st.markdown("---")
            st.markdown("#### Confirmed Teachers")
            confirmed_teachers = df_teachers[df_teachers.get("Confirmed") == "Yes"]
            st.dataframe(confirmed_teachers)

    elif current_role == "teacher":
        st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")
        
        df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
        
        st.subheader("Today's Submitted Homework")
        today_str = datetime.today().strftime(DATE_FORMAT)
        todays_homework = df_homework[(df_homework.get('Uploaded By') == st.session_state.user_name) & (df_homework.get('Date') == today_str)]
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
                if st.session_state.context_set and st.button("Create Another Homework (Reset)"):
                    del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                    st.rerun()

        with grade_tab:
            st.subheader("Grade Student Answers")
            df_all_answers = load_data(MASTER_ANSWER_SHEET)
            if 'Question' not in df_all_answers.columns:
                st.error("The 'Question' column is missing from MASTER_ANSWER_SHEET. Please check the header.")
            else:
                my_questions_df = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]
                my_questions_list = my_questions_df['Question'].tolist()
                answers_to_my_questions = df_all_answers[df_all_answers['Question'].isin(my_questions_list)]
                if answers_to_my_questions.empty:
                    st.info("No answers have been submitted for your questions yet.")
                else:
                    students_with_answers_gmail = answers_to_my_questions['Student Gmail'].unique().tolist()
                    df_students = load_data(STUDENT_SHEET)
                    gradable_students = df_students[df_students['Gmail ID'].isin(students_with_answers_gmail)]
                    selected_student_name = st.selectbox("Select a Student to Grade", gradable_students['Student Name'].tolist())
                    if selected_student_name:
                        student_gmail = gradable_students[gradable_students['Student Name'] == selected_student_name].iloc[0]['Gmail ID']
                        student_answers_df = answers_to_my_questions[answers_to_my_questions['Student Gmail'] == student_gmail]
                        st.markdown("##### Student Growth Chart")
                        if not student_answers_df.empty and 'Marks' in student_answers_df.columns and pd.to_numeric(student_answers_df['Marks'], errors='coerce').notna().any():
                            student_answers_df['Marks'] = pd.to_numeric(student_answers_df['Marks'], errors='coerce')
                            marks_by_subject = student_answers_df.groupby('Subject')['Marks'].mean().reset_index()
                            fig = px.bar(marks_by_subject, x='Subject', y='Marks', title=f'Average Marks for {selected_student_name}', text='Marks')
                            fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Growth chart will appear once answers are graded.")
                        st.markdown("---")
                        for i, row in student_answers_df.sort_values(by='Date', ascending=False).iterrows():
                            st.markdown(f"**Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                            st.write(f"**Question:** {row.get('Question')}")
                            st.info(f"**Answer:** {row.get('Answer')}")
                            marks_value = str(row.get('Marks', '')).strip()
                            if marks_value.isdigit():
                                st.success(f"**Graded: {marks_value} Marks**")
                            else:
                                with st.form(key=f"grade_form_{i}"):
                                    marks = st.number_input("Marks", min_value=0, max_value=100, value=0, key=f"marks_{i}")
                                    if st.form_submit_button("Save Marks"):
                                        cell_row = i + 2
                                        marks_col = 6
                                        MASTER_ANSWER_SHEET.update_cell(cell_row, marks_col, marks)
                                        st.success(f"Marks saved!")
                                        st.rerun()
                            st.markdown("---")

        with report_tab:
            st.subheader("My Reports")
            st.markdown("#### Homework Creation Report")
            my_homework_report = df_homework[df_homework.get('Uploaded By') == st.session_state.user_name]
            if my_homework_report.empty:
                st.info("You have not created any homework assignments yet.")
            else:
                st.markdown("##### Filter by Date")
                col1, col2 = st.columns(2)
                default_start_date = datetime.today() - timedelta(days=7)
                with col1:
                    start_date = st.date_input("Start Date", default_start_date)
                with col2:
                    end_date = st.date_input("End Date", datetime.today())
                my_homework_report['Date'] = pd.to_datetime(my_homework_report['Date']).dt.date
                filtered_report = my_homework_report[(my_homework_report['Date'] >= start_date) & (my_homework_report['Date'] <= end_date)]
                if filtered_report.empty:
                    st.warning("No homework found in the selected date range.")
                else:
                    st.markdown("---")
                    report_summary = filtered_report.groupby(['Class', 'Subject']).size().reset_index(name='Total Questions')
                    st.dataframe(report_summary)
                    fig_report = px.bar(report_summary, x='Class', y='Total Questions', color='Subject', title='Your Homework Contributions')
                    st.plotly_chart(fig_report, use_container_width=True)
            st.markdown("---")
            st.markdown("#### Answer Grading Report")
            if 'answers_to_my_questions' in locals() and not answers_to_my_questions.empty:
                graded_answers = answers_to_my_questions[pd.to_numeric(answers_to_my_questions.get('Marks', ''), errors='coerce').notna()]
                if graded_answers.empty:
                    st.info("You have not graded any answers yet.")
                else:
                    df_students_report = load_data(STUDENT_SHEET)[['Student Name', 'Gmail ID']]
                    grading_summary = graded_answers.groupby('Student Gmail').size().reset_index(name='Answers Graded')
                    grading_summary = pd.merge(grading_summary, df_students_report, left_on='Student Gmail', right_on='Gmail ID', how='left')
                    st.write("Total answers you have graded per student:")
                    st.dataframe(grading_summary[['Student Name', 'Answers Graded']])
            else:
                st.info("No answers have been submitted for your questions yet.")

    elif current_role == "student":
        st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")
        df_students = load_data(STUDENT_SHEET)
        user_info_row = df_students[df_students["Gmail ID"] == st.session_state.user_gmail]
        if not user_info_row.empty:
            user_info = user_info_row.iloc[0]
            student_class = user_info.get("Class")
            st.subheader(f"Your Class: {student_class}")
            st.markdown("---")
            
            df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
            df_all_answers = load_data(MASTER_ANSWER_SHEET)
            homework_for_class = df_homework[df_homework.get("Class") == student_class]
            student_answers = df_all_answers[df_all_answers.get('Student Gmail') == st.session_state.user_gmail]

            if not student_answers.empty and 'Marks' in student_answers.columns and pd.to_numeric(student_answers['Marks'], errors='coerce').notna().any():
                st.header("Your Growth Chart")
                student_answers['Marks'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
                marks_by_subject = student_answers.groupby('Subject')['Marks'].mean().reset_index()
                fig = px.bar(marks_by_subject, x='Subject', y='Marks', title='Your Average Marks by Subject', text='Marks')
                fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.header("Your Homework Assignments")
            if homework_for_class.empty:
                st.info("No homework has been assigned for your class yet.")
            else:
                for subject, group in homework_for_class.sort_values(by='Date', ascending=False).groupby('Subject'):
                    with st.expander(f"📚 Subject: {subject}", expanded=True):
                        for date, assignment_df in group.groupby('Date'):
                            st.markdown(f"**Assignment Date: {date}**")
                            for i, row in enumerate(assignment_df.itertuples()):
                                is_answered = not student_answers[(student_answers.get('Date') == date) & (student_answers.get('Question') == row.Question)].empty
                                st.write(f"**Q{i+1}:** {row.Question}")
                                if is_answered:
                                    saved_answer = student_answers[(student_answers.get('Date') == date) & (student_answers.get('Question') == row.Question)].iloc[0].get('Answer')
                                    st.success(f"**Your Saved Answer:** {saved_answer}")
                                else:
                                    with st.form(key=f"answer_form_{row.Index}"):
                                        answer_text = st.text_area("Your Answer:", key=f"answer_text_{row.Index}")
                                        if st.form_submit_button("Save Answer") and answer_text:
                                            MASTER_ANSWER_SHEET.append_row([st.session_state.user_gmail, date, subject, row.Question, answer_text, ""], value_input_option='USER_ENTERED')
                                            st.success(f"Answer for Q{i+1} saved!")
                                            st.rerun()
                            st.markdown("---")
        else:
            st.error("Could not find your student record.")

    elif current_role == "principal":
        st.header("🏛️ Principal Dashboard")
        st.subheader("📊 Homework Upload Analytics")
        df_homework_analytics = load_data(HOMEWORK_QUESTIONS_SHEET)
        if not df_homework_analytics.empty:
            df_homework_analytics["Date"] = pd.to_datetime(df_homework_analytics["Date"], errors='coerce').dt.date
            st.dataframe(df_homework_analytics)
            fig1 = px.bar(df_homework_analytics, x="Uploaded By", y=None, color="Subject", title="Uploads per Teacher")
            st.plotly_chart(fig1, use_container_width=True)
            trend = df_homework_analytics.groupby("Date").size().reset_index(name="Count")
            fig2 = px.line(trend, x="Date", y="Count", title="Upload Trend Over Time", markers=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No homework data available for analysis.")
