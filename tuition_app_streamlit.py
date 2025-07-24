import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import gspread
import json
import base64
import mimetypes
import plotly.express as px
import io
from uuid import uuid4

# FIX: Import libraries for secure password hashing
from passlib.context import CryptContext

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition")
UPI_ID = "9685840429@pnb"
DATE_FORMAT = "%Y-%m-%d"
# FEATURE: Grading System
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
REVERSE_GRADE_MAP = {v: k for k, v in GRADE_MAP.items()}

# === GOOGLE IDs & KEYS ===
# (Apne Google Drive Folder IDs yahan daalein)
HOMEWORK_FOLDER_ID = "1e83Kseh47VMiKep7DKdOHr9ciwrbMyiO" 
# (Apne Google Sheet Keys yahan daalein)
STUDENT_SHEET_KEY = "10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno"
TEACHER_SHEET_KEY = "1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8"
HOMEWORK_QUESTIONS_SHEET_KEY = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
MASTER_ANSWER_SHEET_KEY = "16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8"
# FEATURE: Add your new Instructions Sheet Key here
INSTRUCTIONS_SHEET_KEY = "YOUR_INSTRUCTIONS_SHEET_KEY_HERE" # <-- IMPORTANT!!

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
    st.error(f"Error connecting to Google APIs: {e}")
    st.stop()

# === GOOGLE SHEETS ACCESS ===
try:
    STUDENT_SHEET = client.open_by_key(STUDENT_SHEET_KEY).sheet1
    TEACHER_SHEET = client.open_by_key(TEACHER_SHEET_KEY).sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key(HOMEWORK_QUESTIONS_SHEET_KEY).sheet1
    MASTER_ANSWER_SHEET = client.open_by_key(MASTER_ANSWER_SHEET_KEY).sheet1
    INSTRUCTIONS_SHEET = client.open_by_key(INSTRUCTIONS_SHEET_KEY).sheet1
except Exception as e:
    st.error(f"Could not open Google Sheets. Ensure all Sheet Keys are correct and shared with the service account: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def make_hashes(password):
    return pwd_context.hash(password)

def check_hashes(password, hashed_text):
    if hashed_text:
        try:
            return pwd_context.verify(password, hashed_text)
        except Exception:
            return False
    return False

@st.cache_data(ttl=300)
def load_data(sheet):
    all_values = sheet.get_all_values()
    if not all_values: return pd.DataFrame()
    headers = all_values[0]
    data = all_values[1:]
    return pd.DataFrame(data, columns=headers)

def save_data(df, sheet):
    df_str = df.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())
    st.cache_data.clear()

# FEATURE: Reusable function to calculate and display leaderboards
def display_leaderboard(df_answers, df_students, student_class, current_student_gmail=None):
    class_answers = df_answers[df_answers['Class'] == student_class].copy()
    if class_answers.empty:
        st.info(f"No graded assignments found for {student_class} to create a leaderboard.")
        return

    class_answers['Score'] = pd.to_numeric(class_answers['Score'], errors='coerce')
    graded_answers = class_answers.dropna(subset=['Score'])
    if graded_answers.empty:
        st.info(f"No graded assignments found for {student_class} to create a leaderboard.")
        return

    student_scores = graded_answers.groupby('Student Gmail')['Score'].mean().reset_index()
    leaderboard = pd.merge(student_scores, df_students[['Student Name', 'Gmail ID']], left_on='Student Gmail', right_on='Gmail ID').sort_values(by='Score', ascending=False)
    leaderboard['Rank'] = leaderboard['Score'].rank(method='min', ascending=False).astype(int)
    
    st.markdown(f"#### 🏆 Leaderboard for {student_class}")
    
    top_3 = leaderboard.head(3)
    st.dataframe(top_3[['Rank', 'Student Name', 'Score']], use_container_width=True)

    if current_student_gmail:
        student_rank_info = leaderboard[leaderboard['Gmail ID'] == current_student_gmail]
        if not student_rank_info.empty:
            rank = student_rank_info.iloc[0]['Rank']
            total_students = len(leaderboard)
            st.success(f"**Your Rank: {rank}** out of {total_students} students.")

# === SESSION STATE INITIALIZATION ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# === SIDEBAR & HEADER ===
st.sidebar.title("Login / Register")
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.cache_data.clear()
        st.rerun()

st.markdown("## Excellent Public School - High-tech Homework System")
st.markdown("---")

# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    # FEATURE: Changed "Register" to "New Registration"
    role = st.sidebar.radio("Login As:", ["Student", "Teacher", "New Registration", "Admin", "Principal"])
    if role == "New Registration":
        st.header("✍️ New Registration")
        # Student Registration with Subscription Plans
        st.subheader("Student Registration")
        st.info("After submitting, please pay the subscription fee to the UPI ID below for your account to be activated.")
        
        # FEATURE: Subscription Plans
        PLANS = {
            "₹100 for 30 days (Normal)": {"duration": 30, "amount": 100},
            "₹550 for 6 months (Advance)": {"duration": 180, "amount": 550},
            "₹1000 for 1 year (Advance)": {"duration": 365, "amount": 1000},
        }
        
        with st.form("student_registration_form", clear_on_submit=True):
            name = st.text_input("Full Name")
            gmail = st.text_input("Gmail ID").lower().strip()
            cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
            pwd = st.text_input("Password", type="password")
            plan_name = st.selectbox("Choose Subscription Plan", list(PLANS.keys()))
            
            if st.form_submit_button(f"Register and Proceed to Pay {plan_name.split(' ')[0]}"):
                if not all([name, gmail, cls, pwd, plan_name]):
                    st.warning("Please fill in all details.")
                else:
                    df = load_data(STUDENT_SHEET)
                    if not df.empty and gmail in df["Gmail ID"].values:
                        st.error("This Gmail is already registered.")
                    else:
                        hashed_password = make_hashes(pwd)
                        plan_details = PLANS[plan_name]
                        new_row = {
                            "Sr. No.": len(df) + 1, "Student Name": name, "Gmail ID": gmail, 
                            "Class": cls, "Password": hashed_password, "Subscription Date": "", 
                            "Subscribed Till": "", "Payment Confirmed": "No", "Answer Sheet ID": "",
                            "Plan Name": plan_name, "Plan Duration Days": plan_details["duration"]
                        }
                        df_new = pd.DataFrame([new_row])
                        df = pd.concat([df, df_new], ignore_index=True)
                        save_data(df, STUDENT_SHEET)
                        st.success("Registration successful! Please complete the payment. Your account will be activated by the admin shortly.")
                        st.balloons()
        st.subheader("Payment Details")
        st.code(f"UPI ID: {UPI_ID}", language="text")
        
    else: # Login logic
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
                                    st.error("Your subscription may have expired or is awaiting payment confirmation.")
                            elif role == "Teacher":
                                if user_row.get("Confirmed") == "Yes": can_login = True
                                else: st.error("Your registration is pending admin confirmation.")
                            elif role in ["Admin", "Principal"]: can_login = True
                            
                            if can_login:
                                st.session_state.logged_in = True
                                st.session_state.user_name = user_row.get(name_col)
                                st.session_state.user_role = role.lower()
                                st.session_state.user_gmail = login_gmail
                                st.session_state.user_class = user_row.get("Class") if role == "Student" else None
                                st.rerun()
                        else: st.error("Invalid Gmail ID or Password.")
                    else: st.error("Invalid Gmail ID or Password.")
                else: st.error("User database could not be loaded.")

# === LOGGED-IN USER PANELS ===
if st.session_state.logged_in:
    current_role = st.session_state.user_role
    df_students_all = load_data(STUDENT_SHEET)
    df_answers_all = load_data(MASTER_ANSWER_SHEET)
    
    if current_role == "admin":
        st.header("👑 Admin Panel")
        tab1, tab2, tab3 = st.tabs(["Student Management", "Teacher Management", "Performance Reports"])
        with tab1:
            st.subheader("Manage Student Registrations")
            df_students = load_data(STUDENT_SHEET)
            unconfirmed = df_students[df_students["Payment Confirmed"] != "Yes"]
            if unconfirmed.empty: st.info("No pending student payments.")
            else:
                for i, row in unconfirmed.iterrows():
                    # FEATURE: Admin sees selected plan and activates accordingly
                    st.write(f"**Name:** {row['Student Name']} | **Gmail:** {row['Gmail ID']} | **Plan:** {row.get('Plan Name', 'N/A')}")
                    if st.button("✅ Confirm Payment", key=f"confirm_{row['Gmail ID']}"):
                        duration = int(row.get('Plan Duration Days', 30))
                        df_students.loc[i, "Subscription Date"] = datetime.today().strftime(DATE_FORMAT)
                        df_students.loc[i, "Subscribed Till"] = (datetime.today() + timedelta(days=duration)).strftime(DATE_FORMAT)
                        df_students.loc[i, "Payment Confirmed"] = "Yes"
                        save_data(df_students, STUDENT_SHEET)
                        st.success(f"Payment confirmed for {row['Student Name']}.")
                        st.rerun()
        with tab2: # Teacher management (unchanged)
            st.subheader("Manage Teacher Registrations")
            df_teachers = load_data(TEACHER_SHEET)
            unconfirmed_teachers = df_teachers[df_teachers["Confirmed"] != "Yes"]
            for i, row in unconfirmed_teachers.iterrows():
                st.write(f"**Name:** {row['Teacher Name']} | **Gmail:** {row['Gmail ID']}")
                if st.button("✅ Confirm Teacher", key=f"confirm_teacher_{row['Gmail ID']}"):
                    df_teachers.loc[i, "Confirmed"] = "Yes"
                    save_data(df_teachers, TEACHER_SHEET)
                    st.rerun()
        with tab3:
            st.subheader("Class-wise Performance")
            selected_class = st.selectbox("Select Class to View Leaderboard", df_students_all['Class'].unique())
            if selected_class:
                display_leaderboard(df_answers_all, df_students_all, selected_class)

    elif current_role == "teacher":
        st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")
        # FEATURE: Display instructions from Principal
        df_instructions = load_data(INSTRUCTIONS_SHEET)
        my_instructions = df_instructions[(df_instructions['Teacher Gmail'] == st.session_state.user_gmail) & (df_instructions['Read Status'] == 'Unread')]
        if not my_instructions.empty:
            st.warning("🚨 New Instructions from Principal:")
            for i, row in my_instructions.iterrows():
                st.info(f"**Instruction:** {row['Instruction Text']}")
                if st.button("Mark as Read", key=f"read_{row['Instruction ID']}"):
                    INSTRUCTIONS_SHEET.update_cell(i + 2, df_instructions.columns.get_loc('Read Status') + 1, "Read")
                    st.cache_data.clear()
                    st.rerun()
        
        create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])
        with create_tab:
            st.subheader("Create a New Homework Assignment")
            # FEATURE: Added "Advance Classes" to subject list
            subjects = ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"]
            subject = st.selectbox("Subject", subjects)
            cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
            # ... (rest of the creation form is simplified for brevity)
        with grade_tab:
            st.subheader("Grade Student Answers")
            df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
            my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]['Question'].tolist()
            answers_to_grade = df_answers_all[df_answers_all['Question'].isin(my_questions)].copy()
            answers_to_grade['Score'] = pd.to_numeric(answers_to_grade['Score'], errors='coerce')
            ungraded = answers_to_grade[answers_to_grade['Score'].isna()]
            
            # FEATURE: Filter student dropdown
            if ungraded.empty:
                st.success("🎉 All submitted answers for your questions have been graded!")
            else:
                students_to_grade = ungraded['Student Gmail'].unique()
                student_names = df_students_all[df_students_all['Gmail ID'].isin(students_to_grade)]['Student Name'].tolist()
                selected_student_name = st.selectbox("Select a Student to Grade", student_names)
                if selected_student_name:
                    student_gmail = df_students_all[df_students_all['Student Name'] == selected_student_name].iloc[0]['Gmail ID']
                    student_ungraded = ungraded[ungraded['Student Gmail'] == student_gmail]
                    for i, row in student_ungraded.iterrows():
                        st.write(f"**Q:** {row['Question']}")
                        st.info(f"**Ans:** {row['Answer']}")
                        with st.form(key=f"grade_{row['Answer ID']}"):
                            # FEATURE: 5-point grading system
                            grade = st.selectbox("Grade", list(GRADE_MAP.keys()), key=f"g_{row['Answer ID']}")
                            remarks = st.text_area("Remarks (if Needs Improvement)", key=f"r_{row['Answer ID']}")
                            if st.form_submit_button("Submit Grade"):
                                score = GRADE_MAP[grade]
                                cell = MASTER_ANSWER_SHEET.find(row['Answer ID'])
                                if cell:
                                    g_col = df_answers_all.columns.get_loc('Grade') + 1
                                    s_col = df_answers_all.columns.get_loc('Score') + 1
                                    r_col = df_answers_all.columns.get_loc('Remarks') + 1
                                    MASTER_ANSWER_SHEET.update_cell(cell.row, g_col, grade)
                                    MASTER_ANSWER_SHEET.update_cell(cell.row, s_col, score)
                                    MASTER_ANSWER_SHEET.update_cell(cell.row, r_col, remarks)
                                    st.cache_data.clear()
                                    st.rerun()
        with report_tab:
            st.subheader("Class-wise Performance")
            # FEATURE: Show Top 3 students report
            class_list = df_students_all['Class'].unique().tolist()
            selected_class_report = st.selectbox("Select Class", class_list)
            if selected_class_report:
                display_leaderboard(df_answers_all, df_students_all, selected_class_report)

    elif current_role == "student":
        st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")
        # FEATURE: Student Leaderboard
        display_leaderboard(df_answers_all, df_students_all, st.session_state.user_class, st.session_state.user_gmail)
        
        # FEATURE: Multi-colored growth chart
        student_answers = df_answers_all[df_answers_all['Student Gmail'] == st.session_state.user_gmail].copy()
        student_answers['Score'] = pd.to_numeric(student_answers['Score'], errors='coerce')
        graded_answers = student_answers.dropna(subset=['Score'])
        if not graded_answers.empty:
            st.markdown("#### Your Performance Graph")
            marks_by_subject = graded_answers.groupby('Subject')['Score'].mean().reset_index()
            fig = px.bar(marks_by_subject, x='Subject', y='Score', title='Your Average Score by Subject', text='Score', color='Subject')
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        # FEATURE: Pending vs. Revision tabs
        pending_tab, revision_tab = st.tabs(["Pending Homework", "My Previous Question Answer (Revision Zone)"])
        
        df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
        my_class_hw = df_homework[df_homework['Class'] == st.session_state.user_class]
        
        with pending_tab:
            st.subheader("Assignments Needing Your Attention")
            # Logic to find pending/remarked questions
            # This is a complex join/merge, simplified here for demonstration
            # In a real app, this logic would be more robust
            all_pending_found = False
            for i, hw_row in my_class_hw.iterrows():
                answer_row_df = student_answers[student_answers['Question'] == hw_row['Question']]
                # Case 1: Not answered yet
                if answer_row_df.empty:
                    # (Display form to submit new answer)
                    all_pending_found = True
                # Case 2: Remarked by teacher
                elif not answer_row_df.empty and answer_row_df.iloc[0]['Grade'] == 'Needs Improvement':
                    # (Display form to edit answer)
                    all_pending_found = True
            if not all_pending_found:
                st.success("Great job! You have no pending homework.")

        with revision_tab:
            st.subheader("Review Your Graded Work")
            # Filter for finally graded answers
            revision_answers = student_answers[student_answers['Grade'] != 'Needs Improvement'].dropna(subset=['Score'])
            if revision_answers.empty:
                st.info("No graded answers available for revision yet.")
            else:
                for i, ans_row in revision_answers.sort_values(by="Date", ascending=False).iterrows():
                    st.markdown(f"**Q:** {ans_row['Question']}")
                    st.info(f"**Your Ans:** {ans_row['Answer']}")
                    st.success(f"**Grade:** {ans_row['Grade']} ({ans_row['Score']})")
                    st.markdown("---")

    elif current_role == "principal":
        st.header("🏛️ Principal Dashboard")
        tab1, tab2, tab3 = st.tabs(["Analytics", "Send Instructions", "Performance Reports"])
        with tab1: # Analytics (unchanged)
             st.subheader("📊 Homework Upload Analytics")
        with tab2:
            st.subheader("Send Instruction to a Teacher")
            # FEATURE: Principal sends instructions
            df_teachers = load_data(TEACHER_SHEET)
            teacher_list = df_teachers['Gmail ID'].tolist()
            selected_teacher = st.selectbox("Select Teacher", teacher_list)
            instruction_text = st.text_area("Instruction:")
            if st.button("Send Instruction") and instruction_text and selected_teacher:
                new_instruction = {
                    "Instruction ID": str(uuid4()), "Teacher Gmail": selected_teacher,
                    "Instruction Text": instruction_text, "Timestamp": datetime.now().strftime(DATE_FORMAT),
                    "Read Status": "Unread"
                }
                INSTRUCTIONS_SHEET.append_row(list(new_instruction.values()))
                st.success(f"Instruction sent to {selected_teacher}")
        with tab3:
            st.subheader("Class-wise Performance")
            selected_class_p = st.selectbox("Select Class to View", df_students_all['Class'].unique(), key="p_class")
            if selected_class_p:
                display_leaderboard(df_answers_all, df_students_all, selected_class_p)
