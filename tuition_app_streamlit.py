import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
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
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}

# === GOOGLE IDs ===
# (Apni actual IDs yahan daalein)
# HOMEWORK_FOLDER_ID = "YOUR_FOLDER_ID"

# === AUTHENTICATION ===
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
try:
    # Use st.secrets for deployment
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    drive_service = build("drive", "v3", credentials=credentials)
except Exception as e:
    st.error(f"Error connecting to Google APIs. Please check credentials. Error: {e}")
    st.stop()


# === GOOGLE SHEETS ===
try:
    # Apni actual Sheet keys yahan daalein
    STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
    TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Could not open Google Sheets. Ensure keys are correct and shared with service account: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

def load_data(sheet):
    all_values = sheet.get_all_values()
    if not all_values: return pd.DataFrame()
    headers = all_values[0]
    data = all_values[1:]
    return pd.DataFrame(data, columns=headers)

def save_data(df, sheet):
    df_str = df.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist(), value_input_option='USER_ENTERED')

def get_image_as_base64(path):
    try:
        with open(path, "rb") as f: data = f.read()
        encoded = base64.b64encode(data).decode()
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type is None: mime_type = "image/png"
        return f"data:{mime_type};base64,{encoded}"
    except FileNotFoundError: return None

def get_class_rankings(df_all_answers, df_students, class_name):
    class_students = df_students[df_students['Class'] == class_name]
    if class_students.empty: return pd.DataFrame()
    class_student_gmails = class_students['Gmail ID'].tolist()
    class_answers = df_all_answers[df_all_answers['Student Gmail'].isin(class_student_gmails)].copy()
    if class_answers.empty or 'Score' not in class_answers.columns: return pd.DataFrame()

    class_answers['Score'] = pd.to_numeric(class_answers['Score'], errors='coerce').fillna(0)
    scores = class_answers.groupby('Student Gmail')['Score'].sum().reset_index()
    ranked_df = pd.merge(scores, df_students[['Gmail ID', 'Student Name']], left_on='Student Gmail', right_on='Gmail ID', how='left')
    ranked_df = ranked_df.sort_values(by='Score', ascending=False).reset_index(drop=True)
    ranked_df['Rank'] = ranked_df['Score'].rank(method='min', ascending=False).astype(int)
    return ranked_df[['Rank', 'Student Name', 'Score', 'Gmail ID']]

# === SESSION STATE, SIDEBAR, HEADER ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""

st.sidebar.title("Login / Register")
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

# (Header display code unchanged)

# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    role = st.sidebar.radio("Login As:", ["Student", "Teacher", "New Registration", "Admin", "Principal"])

    if role == "New Registration":
        # ... (Registration logic with new subscription options)
        st.header("✍️ New Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            st.subheader("Choose Your Subscription Plan")
            plan = st.radio(
                "Select a plan:",
                ["₹100 for 30 days (Normal Subscription)", "₹550 for 6 months (With Advance Classes)", "₹1000 for 1 year (With Advance Classes)"],
                index=0, label_visibility="collapsed"
            )
            st.info(f"You have selected: **{plan}**")
            
            with st.form("student_registration_form"):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
                pwd = st.text_input("Password", type="password")
                if st.form_submit_button("Register (After Payment)"):
                    if not all([name, gmail, cls, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df_students = load_data(STUDENT_SHEET)
                        if not df_students.empty and gmail in df_students["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            if "Normal" in plan: sub_type = "Normal_30D"
                            elif "6 months" in plan: sub_type = "Advance_6M"
                            else: sub_type = "Advance_1Y"
                            
                            new_row = {"Student Name": name, "Gmail ID": gmail, "Class": cls, "Password": make_hashes(pwd), "Subscription Type": sub_type, "Payment Confirmed": "No"}
                            df_new = pd.DataFrame([new_row])
                            df_students = pd.concat([df_students, df_new], ignore_index=True)
                            save_data(df_students, STUDENT_SHEET)
                            st.success("Registration successful! Please wait for admin to confirm your payment.")
                            st.balloons()
    #... (Rest of login and teacher registration logic unchanged)
    
# === LOGGED-IN USER PANELS ===
if st.session_state.logged_in:
    current_role = st.session_state.user_role

    if current_role == "admin":
        st.header("👑 Admin Panel")
        df_students_admin = load_data(STUDENT_SHEET)
        unconfirmed_students = df_students_admin[df_students_admin["Payment Confirmed"] != "Yes"]
        
        st.subheader("Pending Student Confirmations")
        for i, row in unconfirmed_students.iterrows():
            if st.button(f"Confirm Payment for {row.get('Student Name')}", key=f"confirm_{i}"):
                today = datetime.today()
                sub_type = row.get("Subscription Type")
                if sub_type == "Normal_30D": till_date = today + relativedelta(days=30)
                elif sub_type == "Advance_6M": till_date = today + relativedelta(months=6)
                elif sub_type == "Advance_1Y": till_date = today + relativedelta(years=1)
                else: till_date = today + relativedelta(days=30)
                
                df_students_admin.loc[i, "Subscribed Till"] = till_date.strftime(DATE_FORMAT)
                df_students_admin.loc[i, "Subscription Date"] = today.strftime(DATE_FORMAT)
                df_students_admin.loc[i, "Payment Confirmed"] = "Yes"
                save_data(df_students_admin, STUDENT_SHEET)
                st.success(f"Payment confirmed for {row.get('Student Name')}")
                st.rerun()
        # ... (Rest of Admin panel unchanged) ...

    elif current_role == "teacher":
        st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")
        df_teachers_all = load_data(TEACHER_SHEET)
        teacher_row = df_teachers_all[df_teachers_all['Gmail ID'] == st.session_state.user_gmail]
        if not teacher_row.empty:
            instruction = teacher_row.iloc[0].get('Instruction From Principal', '').strip()
            if instruction:
                st.warning(f"**Message from Principal:** {instruction}")
                if st.button("Acknowledge & Clear Message"):
                    teacher_index = teacher_row.index[0]
                    df_teachers_all.loc[teacher_index, 'Instruction From Principal'] = ""
                    save_data(df_teachers_all, TEACHER_SHEET)
                    st.rerun()

        create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])

        with create_tab:
            subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
            # ... (Rest of create tab unchanged) ...

        with grade_tab:
            st.subheader("Grade Student Answers")
            df_all_answers = load_data(MASTER_ANSWER_SHEET)
            if 'Grade' not in df_all_answers.columns or 'Score' not in df_all_answers.columns:
                st.error("Sheet Error: 'Grade' and/or 'Score' columns not found in MASTER_ANSWER_SHEET.")
            else:
                # ... (logic to get gradable students)
                for i, row in student_answers_to_grade.iterrows():
                     with st.form(key=f"grade_form_{i}"):
                        grade_val = st.selectbox("Grade", options=list(GRADE_MAP.keys()), index=2)
                        remarks = st.text_area("Remarks for Correction (if any)")
                        if st.form_submit_button("Save Grade"):
                            score_val = GRADE_MAP[grade_val]
                            row_num = i + 2 # Sheet row number
                            MASTER_ANSWER_SHEET.update_cell(row_num, df_all_answers.columns.get_loc('Grade') + 1, grade_val)
                            MASTER_ANSWER_SHEET.update_cell(row_num, df_all_answers.columns.get_loc('Score') + 1, score_val)
                            MASTER_ANSWER_SHEET.update_cell(row_num, df_all_answers.columns.get_loc('Remarks') + 1, remarks)
                            st.success("Grade saved!")
                            st.rerun()
                            
        with report_tab:
            st.subheader("Class Performance")
            df_students_report = load_data(STUDENT_SHEET)
            all_classes = sorted(df_students_report['Class'].unique())
            for cls in all_classes:
                with st.expander(f"🏆 Top Performers in {cls}"):
                    rankings = get_class_rankings(load_data(MASTER_ANSWER_SHEET), df_students_report, cls)
                    st.dataframe(rankings.head(3)) if not rankings.empty else st.info("No data.")

    elif current_role == "student":
        st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")
        df_students = load_data(STUDENT_SHEET)
        df_all_answers = load_data(MASTER_ANSWER_SHEET)
        user_info = df_students[df_students["Gmail ID"] == st.session_state.user_gmail].iloc[0]
        student_class = user_info.get("Class")
        student_sub_type = user_info.get("Subscription Type")

        st.subheader(f"Your Class: {student_class}")
        class_rankings = get_class_rankings(df_all_answers, df_students, student_class)
        # ... (Ranking display logic unchanged) ...
        
        pending_tab, previous_tab = st.tabs(["**Pending Homework**", "**My Revision Zone**"])
        
        df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
        if "Advance" not in student_sub_type:
            df_homework = df_homework[df_homework['Subject'] != "Advance Classes"]
        homework_for_class = df_homework[df_homework.get("Class") == student_class]
        student_answers = df_all_answers[df_all_answers.get('Student Gmail') == st.session_state.user_gmail].copy()

        with pending_tab:
            st.header("Assignments to be Completed")
            # Logic to find and display pending/unanswered questions
            # This is a complex loop that checks status for each homework question
            if homework_for_class.empty:
                st.info("Great job! No pending homework for you right now.")
            else:
                 for i, hw_row in homework_for_class.iterrows():
                    # Find if answer exists
                    answer_row = student_answers[student_answers['Question'] == hw_row['Question']]
                    if answer_row.empty:
                        # Display form for new answer
                        pass
                    else:
                        remark = answer_row.iloc[0].get('Remarks', '').strip()
                        grade = answer_row.iloc[0].get('Grade', '').strip()
                        if remark:
                            # Display form to edit answer
                            pass
                        elif not grade:
                            # Display "Awaiting grading"
                            pass
            
        with previous_tab:
            st.header("Your Graded Answers for Revision")
            if not student_answers.empty:
                graded_answers = student_answers[(student_answers['Grade'].str.strip() != '') & (student_answers['Remarks'].str.strip() == '')].sort_values(by='Date', ascending=False)
                if graded_answers.empty:
                    st.info("You have no finally graded answers yet.")
                else:
                    for i, row in graded_answers.iterrows():
                        st.success(f"**Grade:** {row.get('Grade')} ({row.get('Score')}/5)")
                        # ... (Rest of display logic)

    elif current_role == "principal":
        st.header("🏛️ Principal Dashboard")
        st.subheader("Manage Teacher Instructions")
        df_teachers_principal = load_data(TEACHER_SHEET)
        selected_teacher_name = st.selectbox("Select Teacher", df_teachers_principal['Teacher Name'].tolist())
        if selected_teacher_name:
            instruction_text = st.text_area("Instruction for " + selected_teacher_name)
            if st.button("Send Instruction"):
                idx_to_update = df_teachers_principal.index[df_teachers_principal['Teacher Name'] == selected_teacher_name][0]
                df_teachers_principal.loc[idx_to_update, 'Instruction From Principal'] = instruction_text
                save_data(df_teachers_principal, TEACHER_SHEET)
                st.success(f"Instruction sent to {selected_teacher_name}.")

        st.subheader("Class Performance Rankings")
        #... (Ranking display logic unchanged)
