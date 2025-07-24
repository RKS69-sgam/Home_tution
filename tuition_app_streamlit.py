import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import gspread
import json
import base64
import mimetypes
import hashlib
import plotly.express as px
import io

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Excellent Homework System")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}

# === GOOGLE AUTHENTICATION & SETUP ===
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    # Use st.secrets for deployment
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    drive_service = build("drive", "v3", credentials=credentials)
except Exception as e:
    st.error(f"Error connecting to Google APIs. Please check credentials. Error: {e}")
    st.stop()

# === GOOGLE SHEETS SETUP ===
try:
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

@st.cache_data(ttl=60)
def load_data(sheet):
    all_values = sheet.get_all_values()
    if not all_values: return pd.DataFrame()
    headers = all_values[0]
    data = all_values[1:]
    df = pd.DataFrame(data, columns=headers)
    # Ensure Score is numeric, fill non-numeric with 0
    if 'Score' in df.columns:
        df['Score'] = pd.to_numeric(df['Score'], errors='coerce').fillna(0)
    return df

def save_data(df, sheet):
    df_str = df.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist(), value_input_option='USER_ENTERED')
    st.cache_data.clear()

@st.cache_data(ttl=300) # Cache rankings for 5 minutes
def get_class_rankings(class_name):
    df_all_answers = load_data(MASTER_ANSWER_SHEET)
    df_students = load_data(STUDENT_SHEET)
    class_students = df_students[df_students['Class'] == class_name]
    if class_students.empty: return pd.DataFrame()
    
    class_student_gmails = class_students['Gmail ID'].tolist()
    class_answers = df_all_answers[df_all_answers['Student Gmail'].isin(class_student_gmails)].copy()
    
    if class_answers.empty: return pd.DataFrame()

    scores = class_answers.groupby('Student Gmail')['Score'].sum().reset_index()
    
    ranked_df = pd.merge(scores, df_students[['Gmail ID', 'Student Name']], on='Gmail ID', how='left')
    ranked_df = ranked_df.sort_values(by='Score', ascending=False).reset_index(drop=True)
    ranked_df['Rank'] = ranked_df['Score'].rank(method='min', ascending=False).astype(int)
    
    return ranked_df[['Rank', 'Student Name', 'Score', 'Gmail ID']]

# === SESSION STATE AND UI SETUP ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""

st.sidebar.title("Login / Register")
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
# (Header display code can be added here)

# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    role = st.sidebar.radio("Login As:", ["Student", "Teacher", "New Registration", "Admin", "Principal"])

    if role == "New Registration":
        st.header("✍️ New Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        if registration_type == "Student":
            st.subheader("Choose Your Subscription Plan")
            plan = st.radio(
                "Select a plan:",
                ["₹100 for 30 days (Normal Subscription)", "₹550 for 6 months (With Advance Classes)", "₹1000 for 1 year (With Advance Classes)"],
                index=0
            )
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
                            
                            new_row_dict = {"Student Name": name, "Gmail ID": gmail, "Class": cls, "Password": make_hashes(pwd), "Subscription Type": sub_type, "Payment Confirmed": "No"}
                            
                            # Add new row, ensuring all columns from sheet are present
                            sheet_cols = load_data(STUDENT_SHEET).columns
                            new_row_df = pd.DataFrame([new_row_dict])
                            # Reorder and fill missing columns
                            new_row_df = new_row_df.reindex(columns=sheet_cols).fillna('')
                            
                            df_students = pd.concat([load_data(STUDENT_SHEET), new_row_df], ignore_index=True)
                            
                            save_data(df_students, STUDENT_SHEET)
                            st.success("Registration successful! Please wait for admin to confirm your payment.")
                            st.balloons()

    elif role in ["Student", "Teacher", "Admin", "Principal"]:
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
                                if user_row.get("Confirmed") == "Yes": can_login = True
                                else: st.error("Registration is pending admin confirmation.")
                            elif role in ["Admin", "Principal"]:
                                can_login = True

                            if can_login:
                                st.session_state.logged_in = True
                                st.session_state.user_name = user_row.get(name_col)
                                st.session_state.user_role = role.lower()
                                st.session_state.user_gmail = login_gmail
                                st.rerun()
                        else: st.error("Invalid Gmail ID or Password.")
                    else: st.error("Invalid Gmail ID or Password.")
                else: st.error("User database is empty.")

# === LOGGED-IN USER PANELS ===
if st.session_state.logged_in:
    current_role = st.session_state.user_role

    if current_role == "admin":
        st.header("👑 Admin Panel")
        st.subheader("Student Management")
        df_students_admin = load_data(STUDENT_SHEET)
        unconfirmed_students = df_students_admin[df_students_admin["Payment Confirmed"] != "Yes"]
        st.markdown("#### Pending Payment Confirmations")
        for i, row in unconfirmed_students.iterrows():
            st.write(f"Name: {row.get('Student Name')}, Gmail: {row.get('Gmail ID')}, Plan: {row.get('Subscription Type')}")
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
        # (Other admin functionalities can be added here)

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

        with grade_tab:
            st.subheader("Grade Student Answers")
            df_all_answers = load_data(MASTER_ANSWER_SHEET)
            my_questions_df = load_data(HOMEWORK_QUESTIONS_SHEET).query(f"`Uploaded By` == '{st.session_state.user_name}'")
            if my_questions_df.empty:
                st.info("You haven't created any questions yet.")
            else:
                answers_to_my_questions = df_all_answers[df_all_answers['Question'].isin(my_questions_df['Question'].tolist())]
                
                # Find answers that need grading (Grade is empty)
                needs_grading = answers_to_my_questions[answers_to_my_questions['Grade'].str.strip() == '']
                
                if needs_grading.empty:
                    st.success("🎉 All submitted answers have been graded!")
                else:
                    students_to_grade = load_data(STUDENT_SHEET)[load_data(STUDENT_SHEET)['Gmail ID'].isin(needs_grading['Student Gmail'].unique())]
                    selected_student_name = st.selectbox("Select Student to Grade", students_to_grade['Student Name'].unique())
                    if selected_student_name:
                        student_gmail = students_to_grade.query(f"`Student Name` == '{selected_student_name}'").iloc[0]['Gmail ID']
                        student_answers_to_grade = needs_grading.query(f"`Student Gmail` == '{student_gmail}'")
                        
                        for i, row in student_answers_to_grade.iterrows():
                            st.markdown(f"**Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                            st.write(f"**Question:** {row.get('Question')}")
                            st.info(f"**Student's Answer:** {row.get('Answer')}")
                            
                            with st.form(key=f"grade_form_{i}"):
                                grade_val = st.selectbox("Grade", options=list(GRADE_MAP.keys()), index=2)
                                remarks = st.text_area("Remarks for Correction (if any)")
                                if st.form_submit_button("Save Grade"):
                                    score_val = GRADE_MAP[grade_val]
                                    row_num = i + 2 # Sheet row number is DataFrame index + 2
                                    MASTER_ANSWER_SHEET.update_cell(row_num, df_all_answers.columns.get_loc('Grade') + 1, grade_val)
                                    MASTER_ANSWER_SHEET.update_cell(row_num, df_all_answers.columns.get_loc('Score') + 1, score_val)
                                    MASTER_ANSWER_SHEET.update_cell(row_num, df_all_answers.columns.get_loc('Remarks') + 1, remarks)
                                    st.success("Grade saved!")
                                    st.rerun()
                            st.markdown("---")
        
        with report_tab:
            st.subheader("Class Performance")
            all_classes = sorted(load_data(STUDENT_SHEET)['Class'].unique())
            for cls in all_classes:
                with st.expander(f"🏆 Top Performers in {cls}"):
                    rankings = get_class_rankings(cls)
                    st.dataframe(rankings.head(3)[['Rank', 'Student Name', 'Score']]) if not rankings.empty else st.info(f"No graded data for {cls}.")

    elif current_role == "student":
        st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")
        user_info = load_data(STUDENT_SHEET).query(f"`Gmail ID` == '{st.session_state.user_gmail}'").iloc[0]
        student_class = user_info.get("Class")
        student_sub_type = user_info.get("Subscription Type")

        st.subheader(f"Your Class: {student_class}")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("#### Leaderboard (Top 3)")
            class_rankings = get_class_rankings(student_class)
            st.dataframe(class_rankings.head(3)[['Rank', 'Student Name', 'Score']]) if not class_rankings.empty else st.info("No rankings yet.")
        with col2:
            st.markdown("#### Your Position")
            your_rank_row = class_rankings[class_rankings['Gmail ID'] == st.session_state.user_gmail]
            if not your_rank_row.empty:
                st.metric("Your Rank", f"#{your_rank_row.iloc[0]['Rank']}", f"{your_rank_row.iloc[0]['Score']} Total Score")
            else:
                st.metric("Your Rank", "Not Ranked", "Submit answers!")
        st.markdown("---")

        pending_tab, revision_tab = st.tabs(["**📝 Pending Homework**", "**📚 My Revision Zone**"])
        
        df_homework_all = load_data(HOMEWORK_QUESTIONS_SHEET)
        if "Advance" not in student_sub_type:
            df_homework_all = df_homework_all[df_homework_all['Subject'] != "Advance Classes"]
        homework_for_class = df_homework_all.query(f"Class == '{student_class}'")
        student_answers = load_data(MASTER_ANSWER_SHEET).query(f"`Student Gmail` == '{st.session_state.user_gmail}'")

        with pending_tab:
            st.header("Assignments to be Completed")
            pending_found = False
            for i, hw_row in homework_for_class.sort_values(by='Date', ascending=False).iterrows():
                answer_row = student_answers[student_answers['Question'] == hw_row['Question']]
                
                # Condition 1: No answer submitted yet
                if answer_row.empty:
                    pending_found = True
                    st.markdown(f"**Question:** {hw_row['Question']} ({hw_row['Subject']} - {hw_row['Date']})")
                    with st.form(key=f"new_{i}"):
                        answer_text = st.text_area("Your Answer")
                        if st.form_submit_button("Submit Answer"):
                            new_row_data = [st.session_state.user_gmail, hw_row['Date'], hw_row['Subject'], hw_row['Question'], answer_text, "", "", ""]
                            MASTER_ANSWER_SHEET.append_row(new_row_data, value_input_option='USER_ENTERED')
                            st.success("Answer Submitted!")
                            st.rerun()
                    st.markdown("---")
                else: # Answer exists, check if needs correction
                    remark = answer_row.iloc[0].get('Remarks', '').strip()
                    grade = answer_row.iloc[0].get('Grade', '').strip()
                    if remark: # Condition 2: Needs correction
                        pending_found = True
                        st.markdown(f"**Question:** {hw_row['Question']} ({hw_row['Subject']} - {hw_row['Date']})")
                        st.warning(f"**Teacher's Remark:** {remark}")
                        with st.form(key=f"edit_{answer_row.index[0]}"):
                            edited_answer = st.text_area("Your Corrected Answer", value=answer_row.iloc[0]['Answer'])
                            if st.form_submit_button("Resubmit Corrected Answer"):
                                row_num_to_update = answer_row.index[0] + 2
                                MASTER_ANSWER_SHEET.update_cell(row_num_to_update, student_answers.columns.get_loc('Answer') + 1, edited_answer)
                                MASTER_ANSWER_SHEET.update_cell(row_num_to_update, student_answers.columns.get_loc('Remarks') + 1, "") # Clear remark
                                MASTER_ANSWER_SHEET.update_cell(row_num_to_update, student_answers.columns.get_loc('Grade') + 1, "") # Clear grade for re-grading
                                MASTER_ANSWER_SHEET.update_cell(row_num_to_update, student_answers.columns.get_loc('Score') + 1, "") # Clear score
                                st.success("Corrected Answer Resubmitted!")
                                st.rerun()
                        st.markdown("---")
            if not pending_found:
                st.success("🎉 Great job! You have no pending homework.")

        with revision_tab:
            st.header("Your Graded Answers for Revision")
            if not student_answers.empty:
                graded_answers = student_answers[(student_answers['Grade'].str.strip() != '') & (student_answers['Remarks'].str.strip() == '')].sort_values(by='Date', ascending=False)
                if graded_answers.empty:
                    st.info("You have no finally graded answers yet.")
                else:
                    for i, row in graded_answers.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**Subject:** {row.get('Subject')} | **Date:** {row.get('Date')}")
                            st.write(f"**Question:** {row.get('Question')}")
                            st.info(f"**Your Answer:** {row.get('Answer')}")
                            st.success(f"**Your Grade:** {row.get('Grade')} ({row.get('Score')}/5)")

    elif current_role == "principal":
        st.header("🏛️ Principal Dashboard")
        st.subheader("Manage Teacher Instructions")
        df_teachers_principal = load_data(TEACHER_SHEET)
        selected_teacher_name = st.selectbox("Select Teacher", df_teachers_principal['Teacher Name'].tolist())
        if selected_teacher_name:
            instruction_text = st.text_area("Instruction for " + selected_teacher_name)
            if st.button("Send Instruction"):
                idx_to_update = df_teachers_principal[df_teachers_principal['Teacher Name'] == selected_teacher_name].index[0]
                df_teachers_principal.loc[idx_to_update, 'Instruction From Principal'] = instruction_text
                save_data(df_teachers_principal, TEACHER_SHEET)
                st.success(f"Instruction sent to {selected_teacher_name}.")
        
        st.subheader("Class Performance Rankings")
        all_classes_p = sorted(load_data(STUDENT_SHEET)['Class'].unique())
        for cls_p in all_classes_p:
            with st.expander(f"🏆 Top Performers in {cls_p}"):
                rankings_p = get_class_rankings(cls_p)
                st.dataframe(rankings_p.head(3)[['Rank', 'Student Name', 'Score']]) if not rankings_p.empty else st.info("No data.")
