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
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition")
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
# --- IMPROVEMENT: Centralized date format ---
DATE_FORMAT = "%Y-%m-%d"

# === GOOGLE DRIVE FOLDER IDs ===
HOMEWORK_FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe"
NOTEBOOK_FOLDER_ID = "1diGm7ukz__yVze4JlH3F-oJ7GBsPJkHy"
RECEIPT_FOLDER_ID = "1dlDauaPLZ-FQGzS2rIIyMnVjmUiBIAfr"

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
    st.error("Error connecting to Google APIs. Please check your credentials and sharing permissions.")
    st.stop()

# === GOOGLE SHEETS ===
try:
    STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
    TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    
    # --- FIX: Use a single Master Answer Sheet ---
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1

except gspread.exceptions.SpreadsheetNotFound:
    st.error("One or more Google Sheets were not found. Please check the Sheet Keys.")
    st.stop()
except HttpError as e:
    st.error(f"An error occurred accessing Google Sheets. Ensure they are shared with the service account: {e}")
    st.stop()




# === UTILITY FUNCTIONS ===
def make_hashes(password):
    """Hashes the password for security."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    """Checks if the provided password matches the stored hash."""
    if hashed_text:
        return make_hashes(password) == hashed_text
    return False

def upload_to_drive(path, folder_id, filename):
    """Uploads a file to Google Drive and returns its shareable link."""
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
    except Exception as e:
        st.error(f"An unexpected error occurred during upload: {e}")
        return None

def create_receipt(student_name, gmail, cls, subs_date, till_date):
    """Creates a payment receipt and uploads it to Drive."""
    doc = Document()
    title = doc.add_paragraph("PRK Home Tuition\nAdvance Classes\n\nReceipt")
    title.alignment = 1
    title.runs[0].bold = True
    title.runs[0].font.size = Pt(16)
    doc.add_paragraph(f"Name: {student_name}")
    doc.add_paragraph(f"Class: {cls}")
    doc.add_paragraph(f"Gmail: {gmail}")
    doc.add_paragraph(f"Subscription Date: {subs_date}")
    doc.add_paragraph(f"Valid Till: {till_date}")
    path = f"/tmp/receipt_{student_name}.docx"
    doc.save(path)
    return upload_to_drive(path, RECEIPT_FOLDER_ID, f"Receipt_{student_name}.docx")

def load_data(sheet):
    """Loads data from the specified Google Sheet."""
    return pd.DataFrame(sheet.get_all_records())

def save_students_data(df):
    """Saves the students DataFrame to the Google Sheet."""
    df_str = df.fillna("").astype(str)
    STUDENT_SHEET.clear()
    STUDENT_SHEET.update([df_str.columns.values.tolist()] + df_str.values.tolist())

def save_teachers_data(df):
    """Saves the teachers DataFrame to the Google Sheet."""
    df_str = df.fillna("").astype(str)
    TEACHER_SHEET.clear()
    TEACHER_SHEET.update([df_str.columns.values.tolist()] + df_str.values.tolist())

# === SESSION STATE INITIALIZATION ===
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.logged_in = False

# === SIDEBAR & HEADER ===
st.sidebar.title("Login / Register")
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("🏫 PRK Home Tuition App")
st.markdown("---")

# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    role = st.sidebar.radio("Login As:", ["Student", "Teacher", "Register", "Admin", "Principal"])

    if role == "Register":
        st.header("✍️ Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            st.subheader("Student Registration")
            with st.form("student_registration_form"):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
                pwd = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Register (After Payment)")

                if submitted:
                    if not all([name, gmail, cls, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df = load_data(STUDENT_SHEET)
                        if gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            hashed_password = make_hashes(pwd)
                            till_date = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime(DATE_FORMAT)
                            new_row = {
                                "Sr. No.": len(df) + 1, "Student Name": name, "Gmail ID": gmail,
                                "Class": cls, "Password": hashed_password,
                                "Subscription Date": "", "Subscribed Till": till_date,
                                "Payment Confirmed": "No"
                            }
                            df_new = pd.DataFrame([new_row])
                            df = pd.concat([df, df_new], ignore_index=True)
                            save_students_data(df)
                            st.success("Registration successful! Waiting for payment confirmation by admin.")
                            st.balloons()
            st.subheader("Payment Details")
            st.code(f"UPI ID: {UPI_ID}", language="text")

        elif registration_type == "Teacher":
            st.subheader("Teacher Registration")
            with st.form("teacher_registration_form"):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                pwd = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Register Teacher")
                
                if submitted:
                    if not all([name, gmail, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df_teachers = load_data(TEACHER_SHEET)
                        if gmail in df_teachers["Gmail ID"].values:
                            st.error("This Gmail is already registered as a teacher.")
                        else:
                            hashed_password = make_hashes(pwd)
                            new_row = {
                                "Sr. No.": len(df_teachers) + 1,
                                "Teacher Name": name,
                                "Gmail ID": gmail,
                                "Password": hashed_password,
                                "Confirmed": "No"
                            }
                            df_new = pd.DataFrame([new_row])
                            df_teachers = pd.concat([df_teachers, df_new], ignore_index=True)
                            save_teachers_data(df_teachers)
                            st.success("Teacher registered successfully! Please wait for admin confirmation.")
                            st.balloons()
    else:
        st.header(f"🔑 {role} Login")
        with st.form(f"{role}_login_form"):
            login_gmail = st.text_input("Gmail ID").lower().strip()
            login_pwd = st.text_input("Password", type="password")
            login_submitted = st.form_submit_button("Login")

            if login_submitted:
                if role in ["Admin", "Principal", "Teacher"]:
                    sheet_to_check = TEACHER_SHEET
                    name_col = "Teacher Name"
                else:
                    sheet_to_check = STUDENT_SHEET
                    name_col = "Student Name"

                df_users = load_data(sheet_to_check)
                user_data = df_users[df_users["Gmail ID"] == login_gmail]

                if not user_data.empty:
                    user_row = user_data.iloc[0]
                    hashed_pwd_from_sheet = user_row["Password"]

                    if check_hashes(login_pwd, hashed_pwd_from_sheet):
                        can_login = False
                        if role == "Student":
                            # --- FIX: Use .get() to prevent crash if column doesn't exist ---
                            if user_row.get("Payment Confirmed") == "Yes" and datetime.today() <= pd.to_datetime(user_row.get("Subscribed Till")):
                                can_login = True
                            else:
                                st.error("Your subscription has expired or is not yet confirmed.")
                        elif role == "Teacher":
                            # --- FIX: Use .get() to prevent crash if column doesn't exist ---
                            if user_row.get("Confirmed") == "Yes":
                                can_login = True
                            else:
                                st.error("Your registration is pending confirmation from the admin.")
                        elif role in ["Admin", "Principal"]:
                            can_login = True

                        if can_login:
                            st.session_state.logged_in = True
                            st.session_state.user_name = user_row[name_col]
                            st.session_state.user_role = role.lower()
                            st.rerun()
                    else:
                        st.error("Invalid Gmail ID or Password.")
                else:
                    st.error("Invalid Gmail ID or Password.")

# === LOGGED-IN USER PANELS ===
if st.session_state.logged_in:
    current_role = st.session_state.user_role.lower()

    if current_role == "admin":
        st.header("👑 Admin Panel")
        tab1, tab2 = st.tabs(["Student Management", "Teacher Management"])

        with tab1:
            st.subheader("Manage Student Registrations")
            df_students = load_data(STUDENT_SHEET)
            st.markdown("#### Pending Payment Confirmations")
            unconfirmed_students = df_students[df_students.get("Payment Confirmed") != "Yes"]

            if unconfirmed_students.empty:
                st.info("No pending student payments to confirm.")
            else:
                for i, row in unconfirmed_students.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Name:** {row['Student Name']} | **Gmail:** {row['Gmail ID']}")
                    with col2:
                        if st.button("✅ Confirm Payment", key=f"confirm_student_{row['Gmail ID']}", use_container_width=True):
                            df_students.loc[i, "Subscription Date"] = datetime.today().strftime(DATE_FORMAT)
                            df_students.loc[i, "Subscribed Till"] = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime(DATE_FORMAT)
                            df_students.loc[i, "Payment Confirmed"] = "Yes"
                            save_students_data(df_students)
                            st.success(f"Payment confirmed for {row['Student Name']}.")
                            st.rerun()

            st.markdown("---")
            st.markdown("#### Confirmed Students")
            confirmed_students = df_students[df_students.get("Payment Confirmed") == "Yes"]
            st.dataframe(confirmed_students)

        with tab2:
            st.subheader("Manage Teacher Registrations")
            # (Your teacher management code will go here)
            df_teachers = load_data(TEACHER_SHEET)
            st.dataframe(df_teachers)

    
elif current_role == "teacher":
    st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")
    
    # Display a summary of today's submitted homework
    st.subheader("Today's Submitted Homework")
    today_str = datetime.today().strftime(DATE_FORMAT)
    df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
    todays_homework = df_homework[
        (df_homework['Uploaded By'] == st.session_state.user_name) & 
        (df_homework['Date'] == today_str)
    ]
    if todays_homework.empty:
        st.info("You have not created any homework assignments today.")
    else:
        summary = todays_homework.groupby(['Class', 'Subject']).size().reset_index(name='Question Count')
        for index, row in summary.iterrows():
            st.success(f"Class: **{row['Class']}** | Subject: **{row['Subject']}** | Questions Added: **{row['Question Count']}**")
    
    st.markdown("---")
    
    create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

    with create_tab:
        # --- FILLED IN: Complete code for creating homework ---
        st.subheader("Create a New Homework Assignment")
        if 'context_set' not in st.session_state:
            st.session_state.context_set = False

        if not st.session_state.context_set:
            with st.form("context_form"):
                st.info("First, select the details for the homework assignment.")
                subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK"])
                cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
                date = st.date_input("Date", datetime.today())
                start_button = st.form_submit_button("Start Adding Questions →")
                if start_button:
                    st.session_state.context_set = True
                    st.session_state.homework_context = {"subject": subject, "class": cls, "date": date}
                    st.session_state.questions_list = []
                    st.rerun()

        if st.session_state.context_set:
            ctx = st.session_state.homework_context
            st.success(f"Creating homework for: **{ctx['class']} - {ctx['subject']}** (Date: {ctx['date'].strftime(DATE_FORMAT)})")
            with st.form("add_question_form", clear_on_submit=True):
                question_text = st.text_area("Enter a question to add:", height=100)
                add_button = st.form_submit_button("Add Question")
                if add_button and question_text:
                    st.session_state.questions_list.append(question_text)
            
            if st.session_state.questions_list:
                st.markdown("---")
                st.write("#### Current Questions in this Assignment:")
                for i, q in enumerate(st.session_state.questions_list):
                    st.write(f"{i + 1}. {q}")
                
                if st.button("Final Submit Homework"):
                    rows_to_add = []
                    for q_text in st.session_state.questions_list:
                        rows_to_add.append([ctx['class'], ctx['date'].strftime(DATE_FORMAT), st.session_state.user_name, ctx['subject'], q_text])
                    HOMEWORK_QUESTIONS_SHEET.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                    st.success("Homework submitted successfully!")
                    st.balloons()
                    del st.session_state.context_set
                    del st.session_state.homework_context
                    del st.session_state.questions_list
                    st.rerun()

            if st.session_state.context_set and st.button("Create Another Homework (Reset)"):
                del st.session_state.context_set
                del st.session_state.homework_context
                del st.session_state.questions_list
                st.rerun()
        # --- END OF FILLED IN SECTION ---

    with grade_tab:
        st.subheader("Grade Student Answers")
        
        df_answers = pd.DataFrame(MASTER_ANSWER_SHEET.get_all_records())
        
        if df_answers.empty:
            st.info("No students have submitted any answers yet.")
        else:
            # --- FILLED IN: Complete logic for student selection ---
            students_with_answers_gmail = df_answers['Student Gmail'].unique().tolist()
            df_students = load_data(STUDENT_SHEET)
            gradable_students = df_students[df_students['Gmail ID'].isin(students_with_answers_gmail)]
            student_name_list = gradable_students['Student Name'].tolist()

            if not student_name_list:
                st.info("No confirmed students have submitted answers yet.")
            else:
                selected_student_name = st.selectbox("Select a Student to Grade", student_name_list)
                # --- END OF FILLED IN SECTION ---

                if selected_student_name:
                    student_gmail = gradable_students[gradable_students['Student Name'] == selected_student_name].iloc[0]['Gmail ID']
                    st.markdown(f"#### Showing answers for: **{selected_student_name}**")
                    
                    student_answers_df = df_answers[df_answers['Student Gmail'] == student_gmail]
                    student_answers_df = student_answers_df.sort_values(by='Date', ascending=False)
                    
                    st.markdown("##### Student Growth Chart")
                    if not student_answers_df.empty and 'Marks' in student_answers_df.columns and pd.to_numeric(student_answers_df['Marks'], errors='coerce').notna().any():
                        student_answers_df['Marks'] = pd.to_numeric(student_answers_df['Marks'], errors='coerce')
                        marks_by_subject = student_answers_df.groupby('Subject')['Marks'].mean().reset_index()
                        fig = px.bar(marks_by_subject, x='Subject', y='Marks', title=f'Average Marks for {selected_student_name}', text='Marks')
                        fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Growth chart will appear here once you have graded some answers.")
                    
                    st.markdown("---")
                    
                    for i, row in student_answers_df.iterrows():
                        st.markdown(f"**Date:** {row['Date']} | **Subject:** {row['Subject']}")
                        st.write(f"**Question:** {row['Question']}")
                        st.info(f"**Answer:** {row['Answer']}")
                        
                        with st.form(key=f"grade_form_{i}"):
                            current_marks_str = str(row.get('Marks', '0')).strip()
                            if not current_marks_str.isdigit():
                                current_marks_value = 0
                            else:
                                current_marks_value = int(current_marks_str)

                            marks = st.number_input("Marks", min_value=0, max_value=100, value=current_marks_value, key=f"marks_{i}")
                            submit_marks_button = st.form_submit_button("Save Marks")
                            
                            if submit_marks_button:
                                cell_row = i + 2 
                                marks_col = 6 
                                MASTER_ANSWER_SHEET.update_cell(cell_row, marks_col, marks)
                                st.success(f"Marks saved for this answer!")
                                st.rerun()
                        st.markdown("---")

    with report_tab:
        st.subheader("My Homework Submission Report")
        df_homework_report = load_data(HOMEWORK_QUESTIONS_SHEET)
        my_homework = df_homework_report[df_homework_report['Uploaded By'] == st.session_state.user_name]

        if my_homework.empty:
            st.info("You have not created any homework assignments yet.")
        else:
            st.markdown("#### Total Questions Created by You:")
            report_summary = my_homework.groupby(['Class', 'Subject']).size().reset_index(name='Total Questions')
            st.dataframe(report_summary)
            fig_report = px.bar(report_summary, x='Class', y='Total Questions', color='Subject', title='Your Homework Contributions')
            st.plotly_chart(fig_report, use_container_width=True)
   elif current_role == "student":
        st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")

        df_students = load_data(STUDENT_SHEET)
        user_info_row = df_students[df_students["Student Name"] == st.session_state.user_name]
        
        if not user_info_row.empty:
            user_info = user_info_row.iloc[0]
            student_class = user_info["Class"]
            student_gmail = user_info["Gmail ID"]
            st.subheader(f"Your Class: {student_class}")
            st.markdown("---")

            # Load all homework and answer data
            df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
            df_all_answers = pd.DataFrame(MASTER_ANSWER_SHEET.get_all_records())
            
            # Filter data for the current student
            homework_for_class = df_homework[df_homework["Class"] == student_class]
            student_answers = df_all_answers[df_all_answers['Student Gmail'] == student_gmail]

            st.header("Your Growth Chart")
            # ... (Growth chart code remains the same) ...

            st.markdown("---")
            st.header("Your Homework Assignments")

            if homework_for_class.empty:
                st.info("No homework has been assigned for your class yet.")
            else:
                # --- FIX: Sort assignments by date, newest first ---
                homework_for_class = homework_for_class.sort_values(by='Date', ascending=False)
                
                subjects = homework_for_class['Subject'].unique()
                for subject in subjects:
                    with st.expander(f"📚 Subject: {subject}", expanded=True):
                        subject_homework = homework_for_class[homework_for_class["Subject"] == subject]
                        assignments = subject_homework.groupby('Date')
                        
                        for date, assignment_df in assignments:
                            st.markdown(f"**Assignment Date: {date}**")
                            
                            for i, row in enumerate(assignment_df.itertuples()):
                                # Check if this specific question has been answered
                                is_answered = not student_answers[
                                    (student_answers['Date'] == date) &
                                    (student_answers['Question'] == row.Question)
                                ].empty
                                
                                st.write(f"**Q{i+1}:** {row.Question}")
                                
                                # --- FEATURE: Uneditable Answers ---
                                if is_answered:
                                    # If answered, just show the saved answer
                                    saved_answer = student_answers[
                                        (student_answers['Date'] == date) &
                                        (student_answers['Question'] == row.Question)
                                    ].iloc[0]['Answer']
                                    st.success(f"**Your Saved Answer:** {saved_answer}")
                                else:
                                    # If not answered, show the form to save an answer
                                    with st.form(key=f"answer_form_{row.Index}"):
                                        answer_text = st.text_area("Your Answer:", key=f"answer_text_{row.Index}")
                                        submit_answer_button = st.form_submit_button("Save Answer")
                                        if submit_answer_button and answer_text:
                                            MASTER_ANSWER_SHEET.append_row([
                                                student_gmail, date, subject, row.Question,
                                                answer_text, ""
                                            ], value_input_option='USER_ENTERED')
                                            st.success(f"Answer for Q{i+1} saved!")
                                            st.rerun()
                            st.markdown("---")
        else:
            st.error("Could not find your student record.")
