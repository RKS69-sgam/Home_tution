import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import hashlib
import plotly.express as px
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}
SUBSCRIPTION_PLANS = {
    "₹100 for 30 days (Normal)": 30,
    "₹550 for 6 months (Advance)": 182,
    "₹1000 for 1 year (Advance)": 365
}
UPI_ID = "9685840429@pnb"

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    drive_service = build("drive", "v3", credentials=credentials)

    STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
    TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

@st.cache_data(ttl=60)
def load_data(_sheet):
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    return pd.DataFrame(all_values[1:], columns=all_values[0])

def save_data(df, sheet):
    df_str = df.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())

def get_image_as_base64(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"
    except FileNotFoundError:
        return None

# === SESSION STATE ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""

# === HEADER ===
st.sidebar.title("Login / New Registration")

prk_logo_b64 = get_image_as_base64("PRK_logo.jpg")
excellent_logo_b64 = get_image_as_base64("Excellent_logo.jpg")

if prk_logo_b64 and excellent_logo_b64:
    st.markdown(
        """
        <style>
        .header-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 20px;
        }
        .header-text {
            font-size: 24px;
            font-weight: bold;
            color: #2E4053;
            text-align: center;
            margin-bottom: 15px;
        }
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            gap: 20px;
        }
        .logo-wrapper {
            flex: 1;
            text-align: center;
            padding: 5px;
        }
        .logo-img {
            max-width: 100%;
            height: auto;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="header-container">
            <div class="header-text">
                Excellent Public School High-tech Homework System 📈
            </div>
            <div class="logo-container">
                <div class="logo-wrapper">
                    <img src="{prk_logo_b64}" class="logo-img">
                </div>
                <div class="logo-wrapper">
                    <img src="{excellent_logo_b64}" class="logo-img">
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.title("🏫 PRK Home Tuition App")
    st.error("One or both logo files ('PRK_logo.jpg', 'Excellent_logo.jpg') are missing.")

st.markdown("---")

# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    role = st.sidebar.radio("Login As:", ["Student", "Teacher", "New Registration", "Admin", "Principal"])

    if role == "New Registration":
        st.header("✍️ New Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            with st.form("student_registration_form", clear_on_submit=True):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
                pwd = st.text_input("Password", type="password")
                plan = st.selectbox("Choose Subscription Plan", list(SUBSCRIPTION_PLANS.keys()))
                st.info(f"Please pay {plan.split(' ')[0]} to the UPI ID below.")
                st.code(f"UPI: {UPI_ID}", language="text")
                if st.form_submit_button("Register (After Payment)"):
                    if not all([name, gmail, cls, pwd, plan]):
                        st.warning("Please fill in all details.")
                    else:
                        df = load_data(STUDENT_SHEET)
                        if not df.empty and gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            new_row = {
                                "Sr. No.": len(df) + 1, "Student Name": name, "Gmail ID": gmail,
                                "Class": cls, "Password": make_hashes(pwd),
                                "Subscription Date": "", "Subscribed Till": "",
                                "Subscription Plan": plan, "Payment Confirmed": "No"
                            }
                            df_new = pd.DataFrame([new_row])
                            df = pd.concat([df, df_new], ignore_index=True)
                            save_data(df, STUDENT_SHEET)
                            st.success("Registration successful! Waiting for admin confirmation.")
        
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
                            new_row = {"Sr. No.": len(df_teachers) + 1, "Teacher Name": name, "Gmail ID": gmail, "Password": make_hashes(pwd), "Confirmed": "No", "Instructions": ""}
                            df_new = pd.DataFrame([new_row])
                            df_teachers = pd.concat([df_teachers, df_new], ignore_index=True)
                            save_data(df_teachers, TEACHER_SHEET)
                            st.success("Teacher registered! Please wait for admin confirmation.")
    else: # Login Logic
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
                                if user_row.get("Payment Confirmed") == "Yes" and datetime.today().date() <= pd.to_datetime(user_row.get("Subscribed Till")).date():
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
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    current_role = st.session_state.user_role

    if current_role == "admin":
        st.header("👑 Admin Panel")
        df_students = load_data(STUDENT_SHEET)
        unconfirmed_students = df_students[df_students.get("Payment Confirmed") != "Yes"]
        st.subheader("Pending Student Confirmations")
        if unconfirmed_students.empty:
            st.info("No pending student payments.")
        else:
            for i, row in unconfirmed_students.iterrows():
                st.write(f"**Name:** {row.get('Student Name')} | **Plan:** {row.get('Subscription Plan')}")
                if st.button(f"✅ Confirm Payment for {row.get('Student Name')}", key=f"confirm_{row.get('Gmail ID')}"):
                    plan_days = SUBSCRIPTION_PLANS.get(row.get("Subscription Plan"), 30)
                    today = datetime.today()
                    till_date = (today + timedelta(days=plan_days)).strftime(DATE_FORMAT)
                    df_students.loc[i, "Subscription Date"] = today.strftime(DATE_FORMAT)
                    df_students.loc[i, "Subscribed Till"] = till_date
                    df_students.loc[i, "Payment Confirmed"] = "Yes"
                    save_data(df_students, STUDENT_SHEET)
                    st.success(f"Payment confirmed for {row.get('Student Name')}.")
                    st.rerun()
    
    elif current_role == "principal":
        st.header("🏛️ Principal Panel")
        df_teachers = load_data(TEACHER_SHEET)
        df_answers = load_data(MASTER_ANSWER_SHEET)
        tab1, tab2 = st.tabs(["Send Instructions", "View Reports"])
        with tab1:
            with st.form("instruction_form"):
                teacher_list = df_teachers['Teacher Name'].tolist()
                selected_teacher = st.selectbox("Select Teacher", teacher_list)
                instruction_text = st.text_area("Instruction:")
                if st.form_submit_button("Send Instruction"):
                    teacher_rows = TEACHER_SHEET.findall(selected_teacher)
                    if teacher_rows:
                        cell_row = teacher_rows[0].row
                        instruction_col = df_teachers.columns.get_loc('Instructions') + 1
                        TEACHER_SHEET.update_cell(cell_row, instruction_col, instruction_text)
                        st.success(f"Instruction sent to {selected_teacher}.")
                    else:
                        st.error("Teacher not found.")
        with tab2:
            st.subheader("Class-wise Top 3 Students")
            df_students_report = load_data(STUDENT_SHEET)
            if not df_answers.empty:
                df_answers['Marks'] = pd.to_numeric(df_answers['Marks'], errors='coerce')
                df_merged = pd.merge(df_answers, df_students_report, left_on='Student Gmail', right_on='Gmail ID')
                leaderboard = df_merged.groupby(['Class', 'Student Name'])['Marks'].mean().reset_index()
                top_students = leaderboard.groupby('Class').apply(lambda x: x.nlargest(3, 'Marks')).reset_index(drop=True)
                st.dataframe(top_students)
    
    elif current_role == "teacher":
        st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")
        df_teachers_live = load_data(TEACHER_SHEET)
        teacher_info = df_teachers_live[df_teachers_live['Teacher Name'] == st.session_state.user_name]
        if not teacher_info.empty and teacher_info.iloc[0].get("Instructions"):
            st.warning(f"**Instruction from Principal:** {teacher_info.iloc[0].get('Instructions')}")
        
        create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])
        
        with create_tab:
            st.subheader("Create a New Homework Assignment")
            # (Homework creation logic here)

        with grade_tab:
            st.subheader("Grade Student Answers")
            df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
            df_all_answers = load_data(MASTER_ANSWER_SHEET)
            my_questions = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]['Question'].tolist()
            answers_to_my_questions = df_all_answers[df_all_answers['Question'].isin(my_questions)].copy()
            answers_to_my_questions['Marks'] = pd.to_numeric(answers_to_my_questions['Marks'], errors='coerce')
            ungraded_answers = answers_to_my_questions[answers_to_my_questions['Marks'].isna()]
            if ungraded_answers.empty:
                st.success("🎉 All answers for your questions have been graded!")
            else:
                students_to_grade_gmail = ungraded_answers['Student Gmail'].unique().tolist()
                df_students = load_data(STUDENT_SHEET)
                gradable_students = df_students[df_students['Gmail ID'].isin(students_to_grade_gmail)]
                selected_student_name = st.selectbox("Select Student with Pending Answers", gradable_students['Student Name'].tolist())
                if selected_student_name:
                    student_gmail = gradable_students[gradable_students['Student Name'] == selected_student_name].iloc[0]['Gmail ID']
                    student_answers_df = ungraded_answers[ungraded_answers['Student Gmail'] == student_gmail]
                    for i, row in student_answers_df.sort_values(by='Date', ascending=False).iterrows():
                        with st.form(key=f"grade_form_{i}"):
                            grade = st.selectbox("Grade", list(GRADE_MAP.keys()), key=f"grade_{i}")
                            remarks = st.text_area("Remarks/Feedback", key=f"remarks_{i}")
                            if st.form_submit_button("Save Grade"):
                                # This is a robust way to find the row to update
                                cells = MASTER_ANSWER_SHEET.findall(row.get('Question'))
                                for cell in cells:
                                    record = MASTER_ANSWER_SHEET.row_values(cell.row)
                                    if record[0] == student_gmail and record[1] == row.get('Date'):
                                        marks_col = df_all_answers.columns.get_loc('Marks') + 1
                                        remarks_col = df_all_answers.columns.get_loc('Remarks') + 1
                                        MASTER_ANSWER_SHEET.update_cell(cell.row, marks_col, GRADE_MAP[grade])
                                        MASTER_ANSWER_SHEET.update_cell(cell.row, remarks_col, remarks)
                                        st.success(f"Grade and remarks saved!")
                                        st.rerun()
                                        break
        with report_tab:
            st.subheader("Class-wise Top 3 Students")
            # Leaderboard logic here
            
    elif current_role == "student":
        st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")
        pending_tab, revision_tab, leaderboard_tab = st.tabs(["Pending Homework", "Revision Zone", "Class Leaderboard"])
        
        df_students = load_data(STUDENT_SHEET)
        df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
        df_all_answers = load_data(MASTER_ANSWER_SHEET)
        user_info = df_students[df_students["Gmail ID"] == st.session_state.user_gmail].iloc[0]
        student_class = user_info.get("Class")
        homework_for_class = df_homework[df_homework.get("Class") == student_class]
        student_answers = df_all_answers[df_all_answers.get('Student Gmail') == st.session_state.user_gmail].copy()
        
    with pending_tab:
        st.subheader("Pending Questions")
    
        # DataFrames are already loaded at the top of the student panel
        # (homework_for_class, student_answers, df_all_answers)
    
        pending_questions_list = []
    
        # Iterate through all homework assigned to the student's class
        for index, hw_row in homework_for_class.iterrows():
        question_text = hw_row.get('Question')
        assignment_date = hw_row.get('Date')
        
        # Check if there's a corresponding answer
        answer_row = student_answers[
            (student_answers['Question'] == question_text) &
            (student_answers['Date'] == assignment_date)
        ]
        
        is_answered = not answer_row.empty
        has_remarks = False
        if is_answered:
            remarks = answer_row.iloc[0].get('Remarks', '').strip()
            if remarks:
                has_remarks = True

        # An item is "pending" if it's not answered OR if it has remarks for correction
        if not is_answered or has_remarks:
            pending_questions_list.append(hw_row)

    if not pending_questions_list:
        st.success("🎉 Good job! You have no pending homework.")
    else:
        # Display the pending questions, newest first
        df_pending = pd.DataFrame(pending_questions_list).sort_values(by='Date', ascending=False)
        
        for i, row in df_pending.iterrows():
            st.markdown(f"**Assignment Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
            st.write(f"**Question:** {row.get('Question')}")
            
            # Check again for remarks to display them
            matching_answer = student_answers[
                (student_answers['Question'] == row.get('Question')) &
                (student_answers['Date'] == row.get('Date'))
            ]
            
            # If it has remarks, show them and the previous answer
            if not matching_answer.empty and matching_answer.iloc[0].get('Remarks'):
                st.info(f"**Your Previous Answer:** {matching_answer.iloc[0].get('Answer')}")
                st.warning(f"**Teacher's Remark:** {matching_answer.iloc[0].get('Remarks')}")
                st.markdown("Please correct your answer and resubmit below.")

            # Show a form to submit or resubmit the answer
            with st.form(key=f"pending_form_{i}"):
                answer_text = st.text_area("Your Answer:", key=f"pending_text_{i}", value=matching_answer.iloc[0].get('Answer', '') if not matching_answer.empty else "")
                
                if st.form_submit_button("Submit Answer"):
                    if answer_text:
                        # If an answer with remarks exists, update it
                        if not matching_answer.empty:
                            row_index_to_update = matching_answer.index[0]
                            sheet_row_number = row_index_to_update + 2 # +2 for header and 0-indexing
                            
                            # Find column numbers by name for robustness
                            ans_col = df_all_answers.columns.get_loc('Answer') + 1
                            marks_col = df_all_answers.columns.get_loc('Marks') + 1
                            remarks_col = df_all_answers.columns.get_loc('Remarks') + 1
                            
                            MASTER_ANSWER_SHEET.update_cell(sheet_row_number, ans_col, answer_text)
                            MASTER_ANSWER_SHEET.update_cell(sheet_row_number, marks_col, "") # Clear marks
                            MASTER_ANSWER_SHEET.update_cell(sheet_row_number, remarks_col, "") # Clear remarks
                            st.success("Corrected answer submitted for re-grading!")
                        else:
                            # Append a new row for a first-time answer
                            new_row_data = [st.session_state.user_gmail, row.get('Date'), row.get('Subject'), row.get('Question'), answer_text, "", ""]
                            MASTER_ANSWER_SHEET.append_row(new_row_data, value_input_option='USER_ENTERED')
                            st.success("Answer saved!")
                        
                        st.rerun()
                    else:
                        st.warning("Answer cannot be empty.")
            st.markdown("---")
        
with revision_tab:
    st.subheader("Previously Graded Answers (Revision Zone)")

    # The 'student_answers' DataFrame is already loaded and filtered for the student
    
    # Ensure the 'Marks' column is numeric, converting errors to NaN (Not a Number)
    student_answers['Marks_Numeric'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
    
    # Filter for rows where 'Marks' is a valid number (not NaN)
    graded_answers = student_answers.dropna(subset=['Marks_Numeric'])

    if graded_answers.empty:
        st.info("You have no graded answers to review yet.")
    else:
        # Sort by date to show the newest graded answers first
        sorted_graded_answers = graded_answers.sort_values(by='Date', ascending=False)
        
        st.write("Review your previously submitted and graded work below.")
        
        for i, row in sorted_graded_answers.iterrows():
            st.markdown(f"**Assignment Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
            st.write(f"**Question:** {row.get('Question')}")
            st.info(f"**Your Answer:** {row.get('Answer')}")

            # Display the grade and any remarks from the teacher
            grade_value = int(row.get('Marks_Numeric'))
            grade_text = GRADE_MAP_REVERSE.get(grade_value, "N/A")
            st.success(f"**Grade:** {grade_text} ({grade_value}/5)")
            
            remarks = row.get('Remarks', '').strip()
            if remarks:
                st.warning(f"**Teacher's Remark:** {remarks}")
            
            st.markdown("---")
        
with leaderboard_tab:
    st.subheader(f"Class Leaderboard ({student_class})")

    # Filter answers for the student's entire class
    class_gmail_list = df_students[df_students['Class'] == student_class]['Gmail ID'].tolist()
    class_answers = df_all_answers[df_all_answers['Student Gmail'].isin(class_gmail_list)].copy()

    if class_answers.empty:
        st.info("The leaderboard will appear once answers have been graded for your class.")
    else:
        # Calculate average marks for each student in the class
        class_answers['Marks'] = pd.to_numeric(class_answers['Marks'], errors='coerce')
        graded_class_answers = class_answers.dropna(subset=['Marks'])
        
        if graded_class_answers.empty:
            st.info("The leaderboard will appear once answers have been graded for your class.")
        else:
            # Group by student and calculate their average score
            leaderboard_df = graded_class_answers.groupby('Student Gmail')['Marks'].mean().reset_index()
            
            # Merge with student names for display
            df_students_names = df_students[['Student Name', 'Gmail ID']]
            leaderboard_df = pd.merge(leaderboard_df, df_students_names, left_on='Student Gmail', right_on='Gmail ID', how='left')
            
            # Create a rank column
            leaderboard_df['Rank'] = leaderboard_df['Marks'].rank(method='dense', ascending=False).astype(int)
            leaderboard_df = leaderboard_df.sort_values(by='Rank')
            
            # Format the 'Marks' column to two decimal places
            leaderboard_df['Marks'] = leaderboard_df['Marks'].round(2)

            # Display Top 3 Performers
            st.markdown("##### 🏆 Top 3 Performers")
            top_3 = leaderboard_df.head(3)
            st.dataframe(top_3[['Rank', 'Student Name', 'Marks']])

            # --- Show the logged-in student's rank ---
            st.markdown("---")
            my_rank_row = leaderboard_df[leaderboard_df['Student Gmail'] == st.session_state.user_gmail]
            
            if not my_rank_row.empty:
                my_rank = my_rank_row.iloc[0]['Rank']
                my_avg_marks = my_rank_row.iloc[0]['Marks']
                st.success(f"**Your Current Rank:** {my_rank} (with an average score of **{my_avg_marks}**)")
            else:
                st.warning("Your rank will be shown here after your answers are graded.")
