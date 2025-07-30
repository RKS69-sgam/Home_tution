import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
import base64
import time
import plotly.express as px

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Student Dashboard")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP_REVERSE = {1: "Needs Improvement", 2: "Average", 3: "Good", 4: "Very Good", 5: "Outstanding"}

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

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    client = connect_to_gsheets()
    if client is None:
        st.stop()
        
    ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
    HOMEWORK_QUESTIONS_SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
    MASTER_ANSWER_SHEET_ID = "1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0"
    ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()


# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "student":
    st.error("You must be logged in as a Student to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === STUDENT DASHBOARD UI ===
st.image("PRK_logo.jpg", use_container_width=True)
st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")

# In Teacher_Dashboard.py and Student_Dashboard.py, after st.header(...)

# --- INSTRUCTION & REPLY SYSTEM ---
df_users_live = load_data(ALL_USERS_SHEET_ID)
user_info = df_users_live[df_users_live['Gmail ID'] == st.session_state.user_gmail].iloc[0]
instruction = user_info.get('Instruction', '').strip()
reply = user_info.get('Instruction_Reply', '').strip()
status = user_info.get('Instruction_Status', '')

if status == 'Sent' and instruction and not reply:
    st.warning(f"**New Instruction from Principal:** {instruction}")
    with st.form(key="reply_form"):
        reply_text = st.text_area("Your Reply:")
        if st.form_submit_button("Send Reply"):
            if reply_text:
                row_id = int(user_info.get('Row ID'))
                reply_col = df_users.columns.get_loc('Instruction_Reply') + 1
                status_col = df_users.columns.get_loc('Instruction_Status') + 1
                sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                sheet.update_cell(row_id, reply_col, reply_text)
                sheet.update_cell(row_id, status_col, "Replied")
                st.success("Your reply has been sent.")
                load_data.clear()
                st.rerun()
            else:
                st.warning("Reply cannot be empty.")
# ------------------------------------


# Load all necessary data once
df_all_users = load_data(ALL_USERS_SHEET_ID)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET_ID)
df_all_answers = load_data(MASTER_ANSWER_SHEET_ID)

user_info_row = df_all_users[df_all_users["Gmail ID"] == st.session_state.user_gmail]

if not user_info_row.empty:
    user_info = user_info_row.iloc[0]
    student_class = user_info.get("Class")
    st.subheader(f"Your Class: {student_class}")
    st.markdown("---")

    # Filter dataframes for the current student
    homework_for_class = df_homework[df_homework.get("Class") == student_class]
    student_answers = df_all_answers[df_all_answers.get('Student Gmail') == st.session_state.user_gmail].copy()

    # --- Subject-wise Growth Chart ---
    st.header("Your Performance Chart")
    if not student_answers.empty and 'Marks' in student_answers.columns:
        student_answers['Marks_Numeric'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
        graded_answers_chart = student_answers.dropna(subset=['Marks_Numeric'])
        
        if not graded_answers_chart.empty:
            marks_by_subject = graded_answers_chart.groupby('Subject')['Marks_Numeric'].mean().reset_index()
            marks_by_subject['Marks_Numeric'] = marks_by_subject['Marks_Numeric'].round(2)
            
            fig = px.bar(
                marks_by_subject, x='Subject', y='Marks_Numeric', title='Your Average Marks by Subject', 
                color='Subject', text='Marks_Numeric', labels={'Marks_Numeric': 'Average Marks'}
            )
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Your growth chart will appear here once your answers are graded.")
    else:
        st.info("Your growth chart will appear here once you submit answers.")

    st.markdown("---")

    pending_tab, revision_tab, leaderboard_tab = st.tabs(["Pending Homework", "Revision Zone", "Class Leaderboard"])
    
    with pending_tab:
        st.subheader("Pending Questions")
        pending_questions_list = []
        if 'Question' in homework_for_class.columns:
            for index, hw_row in homework_for_class.iterrows():
                answer_row = student_answers[(student_answers.get('Question') == hw_row.get('Question')) & (student_answers.get('Date') == hw_row.get('Date'))]
                is_answered = not answer_row.empty
                has_remarks = False
                if is_answered and answer_row.iloc[0].get('Remarks', '').strip():
                    has_remarks = True
                if not is_answered or has_remarks:
                    pending_questions_list.append(hw_row)
            if not pending_questions_list:
                st.success("🎉 Good job! You have no pending homework.")
            else:
                df_pending = pd.DataFrame(pending_questions_list).sort_values(by='Date', ascending=False)
                for i, row in df_pending.iterrows():
                    st.markdown(f"**Assignment Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                    st.write(f"**Question:** {row.get('Question')}")
                    matching_answer = student_answers[(student_answers['Question'] == row.get('Question')) & (student_answers['Date'] == row.get('Date'))]
                    if not matching_answer.empty and matching_answer.iloc[0].get('Remarks'):
                         st.warning(f"**Teacher's Remark:** {matching_answer.iloc[0].get('Remarks')}")
                         st.markdown("Please correct your answer and resubmit.")
                    with st.form(key=f"pending_form_{i}"):
                        answer_text = st.text_area("Your Answer:", key=f"pending_text_{i}", value=matching_answer.iloc[0].get('Answer', '') if not matching_answer.empty else "")
                        if st.form_submit_button("Submit Answer"):
                            if answer_text:
                                if not matching_answer.empty:
                                    row_id_to_update = int(matching_answer.iloc[0].get('Row ID'))
                                    ans_col = df_all_answers.columns.get_loc('Answer') + 1
                                    marks_col = df_all_answers.columns.get_loc('Marks') + 1
                                    remarks_col = df_all_answers.columns.get_loc('Remarks') + 1
                                    sheet = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
                                    sheet.update_cell(row_id_to_update, ans_col, answer_text)
                                    sheet.update_cell(row_id_to_update, marks_col, "")
                                    sheet.update_cell(row_id_to_update, remarks_col, "")
                                    st.success("Corrected answer submitted for re-grading!")
                                else:
                                    sheet = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
                                    new_row_data = [st.session_state.user_gmail, row.get('Date'), row.get('Subject'), row.get('Question'), answer_text, "", ""]
                                    sheet.append_row(new_row_data, value_input_option='USER_ENTERED')
                                    st.success("✅ Answer submitted and available soon in revision zone after grading.") 
                                st.rerun()
                                time.sleep(15)
                                @st.cache_resource
                                st.rerun()
                            else:
                                st.warning("Answer cannot be empty.")
                    st.markdown("---")
        else:
            st.error("Homework sheet is missing the 'Question' column.")

    with revision_tab:
        st.subheader("Previously Graded Answers (Revision Zone)")
        if 'Marks' in student_answers.columns:
            student_answers['Marks_Numeric'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
            graded_answers = student_answers.dropna(subset=['Marks_Numeric'])
            if graded_answers.empty:
                st.info("You have no graded answers to review yet.")
            else:
                for i, row in graded_answers.sort_values(by='Date', ascending=False).iterrows():
                    st.markdown(f"**Date:** {row.get('Date')} | **Subject:** {row.get('Subject')}")
                    st.write(f"**Question:** {row.get('Question')}")
                    st.info(f"**Your Answer:** {row.get('Answer')}")
                    grade_value = int(row.get('Marks_Numeric'))
                    grade_text = GRADE_MAP_REVERSE.get(grade_value, "N/A")
                    st.success(f"**Grade:** {grade_text} ({grade_value}/5)")
                    remarks = row.get('Remarks', '').strip()
                    if remarks:
                        st.warning(f"**Teacher's Remark:** {remarks}")
                    st.markdown("---")
        else:
            st.error("Answer sheet is missing the 'Marks' column.")
    
    with leaderboard_tab:
        st.subheader(f"Class Leaderboard ({student_class})")
        df_students_class = df_all_users[df_all_users['Class'] == student_class]
        class_gmail_list = df_students_class['Gmail ID'].tolist()
        class_answers = df_all_answers[df_all_answers['Student Gmail'].isin(class_gmail_list)].copy()
        if class_answers.empty or 'Marks' not in class_answers.columns:
            st.info("The leaderboard will appear once answers have been graded for your class.")
        else:
            class_answers['Marks'] = pd.to_numeric(class_answers['Marks'], errors='coerce')
            graded_class_answers = class_answers.dropna(subset=['Marks'])
            if graded_class_answers.empty:
                st.info("The leaderboard will appear once answers have been graded for your class.")
            else:
                leaderboard_df = graded_class_answers.groupby('Student Gmail')['Marks'].mean().reset_index()
                leaderboard_df = pd.merge(leaderboard_df, df_students_class[['User Name', 'Gmail ID']], left_on='Student Gmail', right_on='Gmail ID', how='left')
                leaderboard_df['Rank'] = leaderboard_df['Marks'].rank(method='dense', ascending=False).astype(int)
                leaderboard_df = leaderboard_df.sort_values(by='Rank')
                leaderboard_df['Marks'] = leaderboard_df['Marks'].round(2)
                st.markdown("##### 🏆 Top 3 Performers")
                st.dataframe(leaderboard_df.head(3)[['Rank', 'User Name', 'Marks']])
                st.markdown("---")
                my_rank_row = leaderboard_df[leaderboard_df['Student Gmail'] == st.session_state.user_gmail]
                if not my_rank_row.empty:
                    my_rank = my_rank_row.iloc[0]['Rank']
                    my_avg_marks = my_rank_row.iloc[0]['Marks']
                    st.success(f"**Your Current Rank:** {my_rank} (with an average score of **{my_avg_marks}**)")
                else:
                    st.warning("Your rank will be shown here after your answers are graded.")
else:
    st.error("Could not find your student record.")

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style='text-align: center; font-size: 12px;'>
    © 2025 PRK Home Tuition.<br>All Rights Reserved.
    </div>
    """,
    unsafe_allow_html=True
)
