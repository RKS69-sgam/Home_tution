import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import base64
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
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

# --- INSTRUCTION & ANNOUNCEMENT SYSTEMS ---
df_users = load_collection(USERS_COLLECTION)
teacher_info_row = df_users[df_users['Gmail_ID'] == st.session_state.user_gmail]
if not teacher_info_row.empty:
    teacher_info = teacher_info_row.iloc[0]
    # (Your instruction and announcement display logic can be added here)
st.markdown("---")

# Load other necessary data
df_homework = load_collection(HOMEWORK_COLLECTION)
df_answer_bank = load_collection(ANSWER_BANK_COLLECTION)

# --- Top Level Metrics ---
st.markdown("#### Your Overall Performance")
col1, col2, col3 = st.columns(3)

my_points = int(teacher_info.get('Salary_Points', 0))
col1.metric("My Salary Points", my_points)

my_questions_count = len(df_homework[df_homework['Uploaded_By'] == st.session_state.user_name]) if not df_homework.empty else 0
col2.metric("My Total Questions Created", my_questions_count)

df_all_teachers_rank = df_users[df_users['Role'] == 'Teacher'].copy()
if not df_all_teachers_rank.empty:
    df_all_teachers_rank['Salary_Points'] = pd.to_numeric(df_all_teachers_rank.get('Salary_Points', 0), errors='coerce').fillna(0)
    df_all_teachers_rank = df_all_teachers_rank.sort_values(by='Salary_Points', ascending=False).reset_index()
    my_rank_row = df_all_teachers_rank[df_all_teachers_rank['Gmail_ID'] == st.session_state.user_gmail]
    my_rank = my_rank_row.index[0] + 1 if not my_rank_row.empty else "N/A"
    col3.metric("My Rank Among Teachers", f"#{my_rank}")

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
            subject = st.selectbox("Subject", ["---Select Subject---", "Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Physics", "Chemistry", "Biology", "Advance Classes"])
            cls = st.selectbox("Class", ["---Select Class---"] + [f"{i}th" for i in range(5, 13)])
            date = st.date_input("Date", datetime.today(), format="DD-MM-YYYY")
            if st.form_submit_button("Start Adding Questions →"):
                if subject == "---Select Subject---" or cls == "---Select Class---":
                    st.warning("Please select a valid subject and class.")
                else:
                    st.session_state.context_set = True
                    st.session_state.homework_context = {"subject": subject, "class": cls, "date": date}
                    st.session_state.questions_list = []
                    st.rerun()
    
    if st.session_state.context_set:
        ctx = st.session_state.homework_context
        st.success(f"Creating homework for: **{ctx['class']} - {ctx['subject']}** (Date: {ctx['date'].strftime(DATE_FORMAT)})")
        
        with st.form("add_question_form", clear_on_submit=True):
            question_text = st.text_area("Enter Question:", height=100)
            model_answer_text = st.text_area("Enter Model Answer:", height=100)
            
            if ctx['subject'] in ['Math', 'Physics', 'Chemistry', 'Science']:
                st.info("For math equations, use LaTeX format. Example: `x^2 + y^2 = z^2`")
                st.markdown("**Question Preview:**")
                st.latex(question_text)
                st.markdown("**Model Answer Preview:**")
                st.latex(model_answer_text)

            if st.form_submit_button("Add Question"):
                if question_text and model_answer_text:
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
                        "Uploaded_By": st.session_state.user_name, "Subject": ctx['subject'],
                        "Question": item['question'], "Model_Answer": item['model_answer'],
                        "Due_Date": due_date
                    }
                    db.collection('homework').add(new_homework_doc)
                
                st.success("Homework submitted successfully!")
                del st.session_state.context_set, st.session_state.homework_context, st.session_state.questions_list
                st.rerun()

elif page == "My Reports":
    st.subheader("Performance Reports")
    
    st.markdown("#### Top Teacher Performers")
    df_all_teachers = df_users[df_users['Role'] == 'Teacher'].copy()
    if not df_all_teachers.empty:
        df_all_teachers['Salary_Points'] = pd.to_numeric(df_all_teachers.get('Salary_Points', 0), errors='coerce').fillna(0)
        ranked_teachers = df_all_teachers.sort_values(by='Salary_Points', ascending=False)
        ranked_teachers['Rank'] = range(1, len(ranked_teachers) + 1)
        st.dataframe(ranked_teachers[['User_Name', 'Salary_Points']])
        fig = px.bar(ranked_teachers, x='User_Name', y='Salary_Points', color='User_Name', title="Teacher Leaderboard")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Student Performance")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 🥇 Overall Top 3 Students")
        df_students = df_users[df_users['Role'] == 'Student']
        if not df_answer_bank.empty:
            df_answer_bank['Marks'] = pd.to_numeric(df_answer_bank.get('Marks'), errors='coerce')
            overall_student_perf = df_answer_bank.groupby('Student_Gmail')['Marks'].mean().reset_index()
            merged_df = pd.merge(overall_student_perf, df_students, left_on='Student_Gmail', right_on='Gmail_ID')
            top_overall = merged_df.nlargest(3, 'Marks').round(2)
            st.dataframe(top_overall[['User_Name', 'Class', 'Marks']])
    
    with col2:
        st.markdown("##### 🥇 Class-wise Top 3 Students")
        if not df_answer_bank.empty:
            df_merged_classwise = pd.merge(df_answer_bank, df_students, left_on='Student_Gmail', right_on='Gmail_ID')
            leaderboard_df = df_merged_classwise.groupby(['Class', 'User_Name'])['Marks'].mean().reset_index()
            top_classwise = leaderboard_df.groupby('Class').apply(lambda x: x.nlargest(3, 'Marks')).reset_index(drop=True)
            st.dataframe(top_classwise[['User_Name', 'Class', 'Marks']])

    if 'top_classwise' in locals() and not top_classwise.empty:
        fig = px.bar(top_classwise, x='User_Name', y='Marks', color='Class', title='Class-wise Top 3 Students')
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
