import streamlit as st
import pandas as pd
import json
import base64
import plotly.express as px
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Principal Dashboard")
DATE_FORMAT = "%d-%m-%Y"

# === UTILITY FUNCTIONS for FIREBASE ===
@st.cache_resource
def connect_to_firestore():
    """Establishes a connection to Google Firestore and caches it."""
    try:
        if not firebase_admin._apps:
            creds_base64 = st.secrets["firebase_service"]["base64_credentials"]
            creds_json_str = base64.b64decode(creds_base64).decode("utf-8")
            creds_dict = json.loads(creds_json_str)
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        st.error(f"Error connecting to Firebase Firestore: {e}")
        return None

@st.cache_data(ttl=60)
def load_collection(_collection_name):
    """Loads all documents from a Firestore collection into a Pandas DataFrame."""
    try:
        db = connect_to_firestore()
        if db is None: return pd.DataFrame()
        
        collection_ref = db.collection(_collection_name).stream()
        data = []
        for doc in collection_ref:
            doc_data = doc.to_dict()
            doc_data['doc_id'] = doc.id
            data.append(doc_data)
            
        if not data: return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to load data from collection '{_collection_name}': {e}")
        return pd.DataFrame()

# === FIRESTORE COLLECTION NAMES ===
USERS_COLLECTION = "users"
HOMEWORK_COLLECTION = "homework"
ANSWERS_COLLECTION = "answers"
ANSWER_BANK_COLLECTION = "answer_bank"
ANNOUNCEMENTS_COLLECTION = "announcements"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "principal":
    st.error("You must be logged in as a Principal to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === PRINCIPAL DASHBOARD UI ===
st.header("🏛️ Principal Dashboard")

# --- Display Public Announcement ---
try:
    announcements_df = load_collection(ANNOUNCEMENTS_COLLECTION)
    if not announcements_df.empty and 'Date' in announcements_df.columns:
        today_str = datetime.today().strftime(DATE_FORMAT)
        todays_announcement = announcements_df[announcements_df.get('Date') == today_str]
        if not todays_announcement.empty:
            latest_message = todays_announcement['Message'].iloc[0]
            st.info(f"📢 **Public Announcement:** {latest_message}")
except Exception:
    pass

# Load all necessary data from Firestore
df_users = load_collection(USERS_COLLECTION)
df_live_answers = load_collection(ANSWERS_COLLECTION)
df_homework = load_collection(HOMEWORK_COLLECTION)
df_answer_bank = load_collection(ANSWER_BANK_COLLECTION)

# --- Radio Button Navigation ---
page = st.radio(
    "Select a section",
    ["Send Messages", "Performance Reports", "Individual Growth Charts"],
    horizontal=True,
    label_visibility="collapsed"
)

if page == "Send Messages":
    st.subheader("Send a Message")
    message_type = st.radio("Select message type:", ["Individual Instruction", "Public Announcement"])
    
    if message_type == "Individual Instruction":
        st.markdown("##### Send an Instruction to a Single User")
        if df_users.empty:
            st.warning("No users found.")
        else:
            search_term = st.text_input("Search for a User by Name:")
            df_temp = df_users.copy()
            df_temp['display_name'] = df_temp.apply(lambda row: f"{row['User_Name']} ({row['Class']})" if row['Role'] == 'Student' and row.get('Class') else row['User_Name'], axis=1)
            
            if search_term:
                filtered_users = df_temp[df_temp['display_name'].str.contains(search_term, case=False, na=False)]
            else:
                filtered_users = df_temp
            
            user_list = ["---Select a User---"] + filtered_users['display_name'].tolist()
            with st.form("instruction_form"):
                selected_display_name = st.selectbox("Select a User", user_list)
                instruction_text = st.text_area("Instruction:")
                if st.form_submit_button("Send Instruction"):
                    if selected_display_name != "---Select a User---" and instruction_text:
                        real_user_name = selected_display_name.split(' (')[0]
                        user_row = df_users[df_users['User_Name'] == real_user_name]
                        if not user_row.empty:
                            user_doc_id = user_row.iloc[0]['doc_id']
                            db = connect_to_firestore()
                            user_ref = db.collection('users').document(user_doc_id)
                            user_ref.update({'Instruction': instruction_text, 'Instruction_Status': 'Sent'})
                            st.success(f"Instruction sent to {real_user_name}.")
                            st.rerun()
                    else:
                        st.warning("Please select a user and write an instruction.")

    elif message_type == "Public Announcement":
        with st.form("announcement_form"):
            announcement_text = st.text_area("Enter Public Announcement:")
            if st.form_submit_button("Broadcast Announcement"):
                if announcement_text:
                    db = connect_to_firestore()
                    new_announcement = {"Message": announcement_text, "Date": datetime.today().strftime(DATE_FORMAT)}
                    db.collection(ANNOUNCEMENTS_COLLECTION).add(new_announcement)
                    st.success("Public announcement sent to all dashboards!")
                    st.rerun()
                else:
                    st.warning("Announcement text cannot be empty.")

elif page == "Performance Reports":
    st.subheader("Performance Reports")
    st.markdown("#### 📅 Today's Teacher Activity")
    
    today_str = datetime.today().strftime(DATE_FORMAT)
    df_teachers_report = df_users[df_users['Role'].isin(['Teacher', 'Admin', 'Principal'])].copy()
    todays_homework = df_homework[df_homework['Date'] == today_str] if not df_homework.empty else pd.DataFrame()
    
    if not todays_homework.empty:
        questions_created = todays_homework.groupby('Uploaded_By').size().reset_index(name='Created Today')
        teacher_activity = pd.merge(df_teachers_report[['User_Name']], questions_created, left_on='User_Name', right_on='Uploaded_By', how='left')
        teacher_activity.drop(columns=['Uploaded_By'], inplace=True, errors='ignore')
    else:
        teacher_activity = df_teachers_report[['User_Name']].copy()
        teacher_activity['Created Today'] = 0

    df_live_answers['Marks'] = pd.to_numeric(df_live_answers.get('Marks'), errors='coerce')
    ungraded_answers = df_live_answers[df_live_answers['Marks'].isna()]
    
    pending_summary_list = []
    for teacher_name in teacher_activity['User_Name']:
        teacher_questions = df_homework[df_homework['Uploaded_By'] == teacher_name]['Question'].tolist()
        pending_count = len(ungraded_answers[ungraded_answers['Question'].isin(teacher_questions)])
        pending_summary_list.append({'User_Name': teacher_name, 'Pending Answers': pending_count})
        
    pending_df = pd.DataFrame(pending_summary_list)
    teacher_activity = pd.merge(teacher_activity, pending_df, on='User_Name', how='left')
    
    teacher_activity.fillna(0, inplace=True)
    st.dataframe(teacher_activity)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🏆 Top Teachers Leaderboard (All Time)")
        df_teachers = df_users[df_users['Role'] == 'Teacher'].copy()
        df_teachers['Salary_Points'] = pd.to_numeric(df_teachers.get('Salary_Points', 0), errors='coerce').fillna(0)
        ranked_teachers = df_teachers.sort_values(by='Salary_Points', ascending=False)
        ranked_teachers['Rank'] = range(1, len(ranked_teachers) + 1)
        st.dataframe(ranked_teachers[['User_Name', 'Salary_Points']])
        fig_teachers = px.bar(ranked_teachers, x='User_Name', y='Salary_Points', color='User_Name', title='All Teachers by Performance Points')
        st.plotly_chart(fig_teachers, use_container_width=True)

    with col2:
        st.markdown("#### 📉 Students Needing Improvement")
        df_students = df_users[df_users['Role'] == 'Student']
        if not df_answer_bank.empty:
            df_answer_bank['Marks'] = pd.to_numeric(df_answer_bank.get('Marks'), errors='coerce')
            graded_answers = df_answer_bank.dropna(subset=['Marks'])
            if not graded_answers.empty:
                student_performance = graded_answers.groupby('Student_Gmail')['Marks'].mean().reset_index()
                merged_df = pd.merge(student_performance, df_students, left_on='Student_Gmail', right_on='Gmail_ID')
                weakest_students = merged_df.nsmallest(5, 'Marks').round(2)
                st.dataframe(weakest_students[['User_Name', 'Class', 'Marks']])
            else:
                st.info("No graded answers in Answer Bank.")
        else:
            st.info("Answer Bank is empty.")

    st.markdown("---")
    
    st.subheader("🥇 Class-wise Top 3 Students")
    df_students_report = df_users[df_users['Role'] == 'Student']
    if df_answer_bank.empty or df_students_report.empty:
        st.info("Leaderboard will be generated once answers are graded and moved to the bank.")
    else:
        df_answer_bank['Marks'] = pd.to_numeric(df_answer_bank.get('Marks'), errors='coerce')
        graded_answers_all = df_answer_bank.dropna(subset=['Marks'])
        if graded_answers_all.empty:
            st.info("The leaderboard is available after answers have been graded.")
        else:
            df_merged_all = pd.merge(graded_answers_all, df_students_report, left_on='Student_Gmail', right_on='Gmail_ID')
            leaderboard_df_all = df_merged_all.groupby(['Class', 'User_Name'])['Marks'].mean().reset_index()
            top_students_df_all = leaderboard_df_all.groupby('Class').apply(lambda x: x.nlargest(3, 'Marks')).reset_index(drop=True)
            top_students_df_all['Marks'] = top_students_df_all['Marks'].round(2)
            
            st.markdown("#### Top Performers Summary")
            st.dataframe(top_students_df_all)
            
            fig = px.bar(top_students_df_all, x='User_Name', y='Marks', color='Class',
                         title='Top 3 Students by Average Marks per Class',
                         labels={'Marks': 'Average Marks', 'User_Name': 'Student'})
            st.plotly_chart(fig, use_container_width=True)

elif page == "Individual Growth Charts":
    st.subheader("Individual Growth Charts")
    report_type = st.selectbox("Select report type", ["Student", "Teacher"])

    if report_type == "Student":
        df_students = df_users[df_users['Role'] == 'Student'].copy()
        df_students['display_name'] = df_students.apply(lambda row: f"{row['User_Name']} ({row['Class']})", axis=1)
        student_name_display = st.selectbox("Select Student", df_students['display_name'].tolist())
        
        if student_name_display:
            real_name = student_name_display.split(' (')[0]
            student_gmail = df_students[df_students['User_Name'] == real_name].iloc[0]['Gmail_ID']
            student_answers = df_answer_bank[df_answer_bank['Student_Gmail'] == student_gmail].copy()
            if not student_answers.empty:
                student_answers['Marks'] = pd.to_numeric(student_answers['Marks'], errors='coerce')
                graded_answers = student_answers.dropna(subset=['Marks'])
                if not graded_answers.empty:
                    fig = px.bar(graded_answers, x='Subject', y='Marks', color='Subject', title=f"Subject-wise Performance for {student_name_display}")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"{student_name_display} has no graded answers yet.")
            else:
                st.info(f"{student_name_display} has not submitted any answers to the Answer Bank yet.")

    elif report_type == "Teacher":
        df_teachers = df_users[df_users['Role'] == 'Teacher']
        teacher_name = st.selectbox("Select Teacher", df_teachers['User_Name'].tolist())
        if teacher_name:
            teacher_homework = df_homework[df_homework['Uploaded_By'] == teacher_name]
            if not teacher_homework.empty:
                questions_by_subject = teacher_homework.groupby('Subject').size().reset_index(name='Question Count')
                fig = px.bar(questions_by_subject, x='Subject', y='Question Count', color='Subject', title=f"Homework Created by {teacher_name}")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"{teacher_name} has not created any homework yet.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
