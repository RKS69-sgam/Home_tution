import streamlit as st
import pandas as pd
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Principal Dashboard")

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    client = connect_to_gsheets() # Call the new cached function

    # Define your Sheet IDs
    ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
    HOMEWORK_QUESTIONS_SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
    MASTER_ANSWER_SHEET_ID = "1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0"
    ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"

    # Open the sheets using the connected client
    ALL_USERS_SHEET = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key(HOMEWORK_QUESTIONS_SHEET_ID).sheet1
    MASTER_ANSWER_SHEET = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
    ANNOUNCEMENTS_SHEET = client.open_by_key(ANNOUNCEMENTS_SHEET_ID).sheet1

except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()


# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(sheet_id):
    """
    Opens a sheet by its ID and loads the data. This works correctly with Streamlit's cache.
    """
    try:
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

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "principal":
    st.error("You must be logged in as a Principal to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === PRINCIPAL DASHBOARD UI ===
st.header("🏛️ Principal Dashboard")

# Load all necessary data once
df_users = load_data(ALL_USERS_SHEET_ID)
df_answers = load_data(MASTER_ANSWER_SHEET_ID)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET_ID)

report_tab, individual_tab, instruction_tab = st.tabs(["Performance Reports", "Individual Growth Charts", "Send Instructions"])

with report_tab:
    st.subheader("Performance Reports")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏆 Top 3 Teachers (by Points)")
        df_teachers = df_users[df_users['Role'] == 'Teacher'].copy()
        df_teachers['Salary Points'] = pd.to_numeric(df_teachers.get('Salary Points', 0), errors='coerce').fillna(0)
        top_teachers = df_teachers.nlargest(3, 'Salary Points')
        st.dataframe(top_teachers[['User Name', 'Salary Points']])

    with col2:
        st.markdown("#### 🥇 Class-wise Top 3 Students")
        df_students = df_users[df_users['Role'] == 'Student']
        if not df_answers.empty:
            df_answers['Marks'] = pd.to_numeric(df_answers['Marks'], errors='coerce')
            graded_answers = df_answers.dropna(subset=['Marks'])
            if not graded_answers.empty:
                df_merged = pd.merge(graded_answers, df_students, left_on='Student Gmail', right_on='Gmail ID')
                leaderboard_df = df_merged.groupby(['Class', 'User Name'])['Marks'].mean().reset_index()
                top_students_df = leaderboard_df.groupby('Class').apply(lambda x: x.nlargest(3, 'Marks')).reset_index(drop=True)
                top_students_df['Marks'] = top_students_df['Marks'].round(2)
                st.dataframe(top_students_df[['Class', 'User Name', 'Marks']])
            else:
                st.info("No graded student answers yet.")
        else:
            st.info("No student answers submitted yet.")

with individual_tab:
    st.subheader("Individual Growth Charts")
    report_type = st.selectbox("Select report type", ["Student", "Teacher"])

    if report_type == "Student":
        df_students = df_users[df_users['Role'] == 'Student']
        student_name = st.selectbox("Select Student", df_students['User Name'].tolist())
        if student_name:
            student_gmail = df_students[df_students['User Name'] == student_name].iloc[0]['Gmail ID']
            student_answers = df_answers[df_answers['Student Gmail'] == student_gmail].copy()
            if not student_answers.empty:
                student_answers['Marks'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
                graded_answers = student_answers.dropna(subset=['Marks'])
                if not graded_answers.empty:
                    fig = px.bar(graded_answers, x='Subject', y='Marks', color='Subject', title=f"Subject-wise Performance for {student_name}")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"{student_name} has no graded answers yet.")
            else:
                st.info(f"{student_name} has not submitted any answers yet.")

    elif report_type == "Teacher":
        df_teachers = df_users[df_users['Role'] == 'Teacher']
        teacher_name = st.selectbox("Select Teacher", df_teachers['User Name'].tolist())
        if teacher_name:
            teacher_homework = df_homework[df_homework['Uploaded By'] == teacher_name]
            if not teacher_homework.empty:
                questions_by_subject = teacher_homework.groupby('Subject').size().reset_index(name='Question Count')
                fig = px.bar(questions_by_subject, x='Subject', y='Question Count', color='Subject', title=f"Homework Created by {teacher_name}")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"{teacher_name} has not created any homework yet.")

with instruction_tab:
    st.subheader("Send Instruction to a Teacher")
    df_teachers = df_users[df_users['Role'].isin(['Teacher', 'Admin', 'Principal'])]
    if df_teachers.empty:
        st.warning("No teachers found.")
    else:
        with st.form("instruction_form"):
            teacher_list = df_teachers['User Name'].tolist()
            selected_teacher = st.selectbox("Select Teacher", teacher_list)
            instruction_text = st.text_area("Instruction:")
            if st.form_submit_button("Send Instruction"):
                if selected_teacher and instruction_text:
                    teacher_row = df_teachers[df_teachers['User Name'] == selected_teacher]
                    if not teacher_row.empty:
                        row_id = int(teacher_row.iloc[0]['Row ID'])
                        instruction_col = df_users.columns.get_loc('Instructions') + 1
                        sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                        sheet.update_cell(row_id, instruction_col, instruction_text)
                        st.success(f"Instruction sent to {selected_teacher}.")
                        load_data.clear()
                else:
                    st.warning("Please select a teacher and write an instruction.")
