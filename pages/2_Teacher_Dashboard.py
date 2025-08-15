import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%d-%m-%Y"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}

# === UTILITY FUNCTIONS ===
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

# === SHEET IDs (Firestore Collection Names) ===
USERS_COLLECTION = "users"
HOMEWORK_COLLECTION = "homework"
ANSWERS_COLLECTION = "answers"
ANSWER_BANK_COLLECTION = "answer_bank"
ANNOUNCEMENTS_COLLECTION = "announcements"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to access this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === TEACHER DASHBOARD UI ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# --- INSTRUCTION, ANNOUNCEMENT & SALARY NOTIFICATION ---
df_users = load_collection(USERS_COLLECTION)
teacher_info_row = df_users[df_users['Gmail ID'] == st.session_state.user_gmail]
if not teacher_info_row.empty:
    teacher_info = teacher_info_row.iloc[0]
    points_str = str(teacher_info.get('Salary Points', '0')).strip()
    salary_points = int(points_str) if points_str.isdigit() else 0

    if salary_points >= 5000:
        st.success("🎉 Congratulations! You have earned 5000+ points. Please contact administration to register your salary account.")
        st.balloons()
    
    instruction = teacher_info.get('Instruction', '').strip()
    reply = teacher_info.get('Instruction_Reply', '').strip()
    status = teacher_info.get('Instruction_Status', '')
    if status == 'Sent' and instruction and not reply:
        st.warning(f"**New Instruction from Principal:** {instruction}")
        with st.form(key="reply_form"):
            reply_text = st.text_area("Your Reply:")
            if st.form_submit_button("Send Reply"):
                if reply_text:
                    with st.spinner("Sending reply..."):
                        db = connect_to_firestore()
                        user_doc_id = teacher_info.get('doc_id')
                        user_ref = db.collection('users').document(user_doc_id)
                        user_ref.update({
                            'Instruction_Reply': reply_text,
                            'Instruction_Status': 'Replied'
                        })
                        st.success("Your reply has been sent.")
                        st.rerun()
                else:
                    st.warning("Reply cannot be empty.")
    st.markdown("---")

# Load other necessary data
df_homework = load_collection(HOMEWORK_COLLECTION)
df_live_answers = load_collection(ANSWERS_COLLECTION)
df_answer_bank = load_collection(ANSWER_BANK_COLLECTION)

# Display a summary of today's submitted homework
st.subheader("Today's Submitted Homework")
today_str = datetime.today().strftime(DATE_FORMAT)
todays_homework = df_homework[(df_homework.get('Uploaded By') == st.session_state.user_name) & (df_homework.get('Date') == today_str)]
if todays_homework.empty:
    st.info("You have not created any homework assignments today.")
else:
    if 'selected_assignment' not in st.session_state:
        summary_table = pd.pivot_table(todays_homework, index='Class', columns='Subject', aggfunc='size', fill_value=0)
        st.markdown("#### Summary Table")
        st.dataframe(summary_table)
        st.markdown("---")
        st.markdown("#### View Details")
        for class_name, row in summary_table.iterrows():
            for subject_name, count in row.items():
                if count > 0:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**Class:** {class_name} | **Subject:** {subject_name}")
                    with col2:
                        if st.button(f"View {count} Questions", key=f"view_{class_name}_{subject_name}"):
                            st.session_state.selected_assignment = {'Class': class_name, 'Subject': subject_name, 'Date': today_str}
                            st.rerun()
    
    if 'selected_assignment' in st.session_state:
        st.markdown("---")
        st.subheader("Viewing Questions for Selected Assignment")
        selected = st.session_state.selected_assignment
        st.info(f"Class: **{selected['Class']}** | Subject: **{selected['Subject']}** | Date: **{selected['Date']}**")
        selected_questions = df_homework[
            (df_homework['Class'] == selected['Class']) &
            (df_homework['Subject'] == selected['Subject']) &
            (df_homework['Date'] == selected['Date'])
        ]
        for i, row in enumerate(selected_questions.itertuples()):
            st.write(f"{i + 1}. {row.Question}")
        if st.button("Back to Main View"):
            del st.session_state.selected_assignment
            st.rerun()

st.markdown("---")

# --- Radio Button Navigation System ---
page = st.radio(
    "Navigation",
    ["Create Homework", "My Reports"],
    horizontal=True,
    label_visibility="collapsed"
)

if page == "Create Homework":
    st.subheader("Create a New Homework Assignment")
    if 'context_set' not in st.session_state:
        st.session_state.context_set = False
    if not st.session_state.context_set:
        with st.form("context_form"):
            subject = st.selectbox("Subject", ["Hindi","Sanskrit","English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
            cls = st.selectbox("Class", [f"{i}th" for i in range(5, 13)])
            date = st.date_input("Date", datetime.today(), format="DD-MM-YYYY")
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
            model_answer_text = st.text_area("Enter the Model Answer for auto-grading:", height=100)
            if st.form_submit_button("Add Question"):
                if question_text and model_answer_text:
                    if 'questions_list' not in st.session_state:
                        st.session_state.questions_list = []
                    st.session_state.questions_list.append({"question": question_text, "model_answer": model_answer_text})
                else:
                    st.warning("Please enter both a question and a model answer.")
        
        if st.session_state.get('questions_list'):
            st.write("#### Current Questions:")
            for i, item in enumerate(st.session_state.questions_list):
                with st.expander(f"{i + 1}. {item['question']}"):
                    st.info(f"Model Answer: {item['model_answer']}")
            
            if st.button("Final Submit Homework"):
                db = connect_to_firestore()
                due_date = (ctx['date'] + timedelta(days=1)).strftime(DATE_FORMAT)
                for item in st.session_state.questions_list:
                    new_homework_doc = {
                        "Class": ctx['class'], "Date": ctx['date'].strftime(DATE_FORMAT),
                        "Uploaded By": st.session_state.user_name, "Subject": ctx['subject'],
                        "Question": item['question'], "Model_Answer": item['model_answer'],
                        "Due_Date": due_date
                    }
                    db.collection('homework').add(new_homework_doc)
                
                st.success("Homework submitted successfully!")
                del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                st.rerun()

elif page == "My Reports":
    st.subheader("My Reports")
    st.markdown("#### Homework Creation Report")
    teacher_homework = df_homework[df_homework.get('Uploaded By') == st.session_state.user_name]
    if teacher_homework.empty:
        st.info("No homework created yet.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.today() - timedelta(days=7), format="DD-MM-YYYY")
        with col2:
            end_date = st.date_input("End Date", datetime.today(), format="DD-MM-YYYY")
        
        teacher_homework['Date_dt'] = pd.to_datetime(teacher_homework['Date'], format=DATE_FORMAT, errors='coerce').dt.date
        filtered = teacher_homework[(teacher_homework['Date_dt'] >= start_date) & (teacher_homework['Date_dt'] <= end_date)]
        if filtered.empty:
            st.warning("No homework found in selected range.")
        else:
            summary = filtered.groupby(['Class', 'Subject']).size().reset_index(name='Total')
            st.dataframe(summary)

    st.markdown("---")
    st.subheader("🏆 Top Teachers Leaderboard")
    df_all_teachers = df_users[df_users['Role'] == 'Teacher'].copy()
    if 'Salary Points' in df_all_teachers.columns:
        df_all_teachers['Salary Points'] = pd.to_numeric(df_all_teachers.get('Salary Points', 0), errors='coerce').fillna(0)
        ranked_teachers = df_all_teachers.sort_values(by='Salary Points', ascending=False)
        ranked_teachers['Rank'] = range(1, len(ranked_teachers) + 1)
        st.dataframe(ranked_teachers[['Rank', 'User Name', 'Salary Points']])
    else:
        st.warning("'Salary Points' column not found in All Users Sheet.")

    st.markdown("---")
    st.subheader("🥇 Class-wise Top 3 Students")
    df_students_report = df_users[df_users['Role'] == 'Student']
    if df_answer_bank.empty or df_students_report.empty:
        st.info("Leaderboard will be generated once answers are graded and moved to the bank.")
    else:
        df_answer_bank['Marks'] = pd.to_numeric(df_answer_bank.get('Marks'), errors='coerce')
        graded_answers = df_answer_bank.dropna(subset=['Marks'])
        if graded_answers.empty:
            st.info("The leaderboard is available after answers have been graded and moved to the bank.")
        else:
            df_merged = pd.merge(graded_answers, df_students_report, left_on='Student Gmail', right_on='Gmail ID')
            leaderboard_df = df_merged.groupby(['Class', 'User Name'])['Marks'].mean().reset_index()
            leaderboard_df['Rank'] = leaderboard_df.groupby('Class')['Marks'].rank(method='dense', ascending=False).astype(int)
            leaderboard_df = leaderboard_df.sort_values(by=['Class', 'Rank'])
            top_students_df = leaderboard_df.groupby('Class').head(3).reset_index(drop=True)
            top_students_df['Marks'] = top_students_df['Marks'].round(2)
            st.markdown("#### Top Performers Summary")
            st.dataframe(top_students_df[['Rank', 'User Name', 'Class', 'Marks']])

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
