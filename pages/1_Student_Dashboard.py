import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import json
import base64
import time
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Student Dashboard")
DATE_FORMAT = "%d-%m-%Y"
GRADE_MAP_REVERSE = {1: "Needs Improvement", 2: "Average", 3: "Good", 4: "Very Good", 5: "Outstanding"}

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

def get_text_similarity(text1, text2):
    """Calculates similarity percentage between two texts."""
    try:
        if not text1 or not text2: return 0.0
        vectorizer = TfidfVectorizer().fit_transform([text1.lower(), text2.lower()])
        similarity_matrix = cosine_similarity(vectorizer)
        return similarity_matrix[0][1] * 100
    except Exception:
        return 0.0

def get_grade_from_similarity(percentage):
    """Assigns a grade score based on similarity percentage."""
    if percentage >= 80: return 4
    elif percentage >= 60: return 3
    else: return 1

# === FIRESTORE COLLECTION NAMES ===
USERS_COLLECTION = "users"
HOMEWORK_COLLECTION = "homework"
ANSWERS_COLLECTION = "answers"
ANSWER_BANK_COLLECTION = "answer_bank"
ANNOUNCEMENTS_COLLECTION = "announcements"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "student":
    st.error("You must be logged in as a Student to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === STUDENT DASHBOARD UI ===
st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")

# --- INSTRUCTION & ANNOUNCEMENT SYSTEMS ---
df_all_users = load_collection(USERS_COLLECTION)
user_info_row = df_all_users[df_all_users['Gmail_ID'] == st.session_state.user_gmail]
if not user_info_row.empty:
    user_info = user_info_row.iloc[0]
    instruction = user_info.get('Instruction', '').strip()
    reply = user_info.get('Instruction_Reply', '').strip()
    status = user_info.get('Instruction_Status', '')

    if status == 'Sent' and instruction and not reply:
        st.warning(f"**New Instruction from Principal:** {instruction}")
        with st.form(key="reply_form"):
            reply_text = st.text_area("Your Reply:")
            if st.form_submit_button("Send Reply"):
                if reply_text:
                    with st.spinner("Sending reply..."):
                        db = connect_to_firestore()
                        user_doc_id = user_info.get('doc_id')
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
    
    student_class = user_info.get("Class")
    st.subheader(f"Your Class: {student_class}")
    st.markdown("---")

    # Filter dataframes for the current student
    homework_for_class = df_homework[df_homework.get("Class") == student_class]
    student_answers_live = df_live_answers[df_live_answers.get('Student_Gmail') == st.session_state.user_gmail].copy()
    student_answers_from_bank = df_answer_bank[df_answer_bank.get('Student_Gmail') == st.session_state.user_gmail].copy()
    
    # --- Performance Overview Section ---
    st.header("Your Performance Overview")
    
    total_assigned = len(homework_for_class)
    total_completed = len(student_answers_from_bank)
    total_pending = total_assigned - total_completed
    
    average_score = 0.0
    if not student_answers_from_bank.empty and 'Marks' in student_answers_from_bank.columns:
        student_answers_from_bank['Marks_Numeric'] = pd.to_numeric(student_answers_from_bank['Marks'], errors='coerce')
        graded_answers = student_answers_from_bank.dropna(subset=['Marks_Numeric'])
        if not graded_answers.empty:
            average_score = graded_answers['Marks_Numeric'].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Homework Assigned", f"{total_assigned}")
    col2.metric("Homework Completed", f"{total_completed}", delta=f"-{total_pending} Pending" if total_pending > 0 else None)
    col3.metric("Overall Average Score", f"{average_score:.2f} / 5")
    
    if total_assigned > 0:
        chart_df = pd.DataFrame({'Status': ['Completed', 'Pending'], 'Count': [total_completed, total_pending]})
        fig = px.pie(chart_df, values='Count', names='Status', title='Homework Status', hole=.4, color_discrete_map={'Completed':'green', 'Pending':'orange'})
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")

    pending_tab, revision_tab, leaderboard_tab = st.tabs(["Pending Homework", "Revision Zone", "Class Leaderboard"])
    
    with pending_tab:
        st.subheader("Pending Questions")
        pending_questions_list = []
        today_date = date.today()
        
        for index, hw_row in homework_for_class.iterrows():
            question_text = hw_row.get('Question')
            assignment_date_str = hw_row.get('Date')
            
            answer_in_live = student_answers_live[(student_answers_live['Question'] == question_text) & (student_answers_live['Date'] == assignment_date_str)]
            answer_in_bank = student_answers_from_bank[(student_answers_from_bank['Question'] == question_text) & (student_answers_from_bank['Date'] == assignment_date_str)]

            if not answer_in_bank.empty:
                continue

            if not answer_in_live.empty:
                attempt_status = int(answer_in_live.iloc[0].get('Attempt_Status', '0'))
                assignment_date = datetime.strptime(assignment_date_str, DATE_FORMAT).date()
                if attempt_status >= 2 and today_date == assignment_date:
                    continue
                else:
                    pending_questions_list.append(hw_row)
            else:
                pending_questions_list.append(hw_row)

        if not pending_questions_list:
            st.success("🎉 Good job! You have no pending homework.")
        else:
            df_pending = pd.DataFrame(pending_questions_list).sort_values(by='Date', ascending=False)
            for i, row in df_pending.iterrows():
                question_id = f"question_{row['doc_id']}"
                if question_id not in st.session_state:
                    st.session_state[question_id] = 'initial'

                st.markdown(f"**Assignment Date:** {row.get('Date')} | **Due Date:** {row.get('Due_Date')}")
                st.write(f"**Question:** {row.get('Question')}")
                
                matching_answer = student_answers_live[(student_answers_live['Question'] == row.get('Question')) & (student_answers_live['Date'] == row.get('Date'))]
                current_attempt = 0
                if not matching_answer.empty:
                    current_attempt = int(matching_answer.iloc[0].get('Attempt_Status', 0))
                    if matching_answer.iloc[0].get('Remarks'):
                        st.warning(f"**Auto-Remark:** {matching_answer.iloc[0].get('Remarks')}")
                
                if current_attempt == 0 and st.session_state[question_id] == 'initial':
                    if st.button("View Model Answer & Start Timer", key=f"view_{i}"):
                        st.session_state[question_id] = 'timer_running'
                        st.rerun()
                elif current_attempt == 1 and st.session_state[question_id] == 'initial':
                    st.warning("This is your second chance.")
                    if st.button("View Answer (One More Chance)", key=f"view_{i}"):
                        st.session_state[question_id] = 'timer_running'
                        st.rerun()
                elif current_attempt >= 2 and st.session_state[question_id] == 'initial':
                    st.error("This is your final chance for this question.")
                    if st.button("View Answer (Final Chance)", key=f"view_{i}"):
                        st.session_state[question_id] = 'timer_running'
                        st.rerun()
                
                if st.session_state[question_id] == 'timer_running':
                    model_answer = row.get('Model_Answer', '').strip()
                    if model_answer:
                        word_count = len(model_answer.split())
                        timer_duration = max(10, word_count * 2) 
                        st.markdown(f"""<div style="user-select: none; border: 1px solid #ccc; padding: 10px; border-radius: 5px;"><h4>Model Answer:</h4><p>{model_answer}</p></div>""", unsafe_allow_html=True)
                        timer_placeholder = st.empty()
                        for seconds in range(timer_duration, 0, -1):
                            timer_placeholder.progress(seconds / timer_duration, text=f"Time remaining: {seconds} seconds")
                            time.sleep(1)
                        timer_placeholder.empty()
                        st.session_state[question_id] = 'show_form'
                        st.rerun()
                    else:
                        st.warning("No model answer available. You can answer directly.")
                        st.session_state[question_id] = 'show_form'
                        st.rerun()

                elif st.session_state[question_id] == 'show_form':
                    with st.form(key=f"answer_form_{i}"):
                        answer_text = st.text_area("Your Answer:", key=f"answer_{i}", value=matching_answer.iloc[0].get('Answer', '') if not matching_answer.empty else "")
                        if st.form_submit_button("Submit Final Answer"):
                            if answer_text:
                                with st.spinner("Grading your answer..."):
                                    model_answer = row.get('Model_Answer', '').strip()
                                    similarity = get_text_similarity(answer_text, model_answer)
                                    grade_score = get_grade_from_similarity(similarity)
                                    db = connect_to_firestore()
                                    
                                    new_attempt_status = current_attempt + 1
                                    
                                    if grade_score >= 3 or new_attempt_status >= 3:
                                        collection_ref = db.collection('answer_bank')
                                        remark = "Good! Try for better performance next time." if grade_score == 3 else f"Auto-Graded: Excellent! ({similarity:.2f}%)"
                                        st.success(f"Your answer was {similarity:.2f}% correct and has been saved.")
                                    else:
                                        collection_ref = db.collection('answers')
                                        remark = f"Auto-Remark: Your answer was {similarity:.2f}% correct. Please improve it."
                                        grade_score = None
                                        st.warning(f"Your answer was {similarity:.2f}% correct. Please resubmit.")
                                    
                                    if not matching_answer.empty:
                                        doc_id_to_delete = matching_answer.iloc[0].get('doc_id')
                                        db.collection('answers').document(doc_id_to_delete).delete()
                                    
                                    new_doc_data = {
                                        "Student_Gmail": st.session_state.user_gmail, "Date": row.get('Date'), 
                                        "Class": student_class, "Subject": row.get('Subject'), 
                                        "Question": row.get('Question'), "Answer": answer_text, 
                                        "Marks": grade_score, "Remarks": remark, "Attempt_Status": new_attempt_status
                                    }
                                    collection_ref.add(new_doc_data)
                                    
                                    st.rerun()
                            else:
                                st.warning("Answer cannot be empty.")
                st.markdown("---")

    with revision_tab:
        st.subheader("Previously Graded Answers (from Answer Bank)")
        if not student_answers_from_bank.empty and 'Marks' in student_answers_from_bank.columns:
            student_answers_from_bank['Marks_Numeric'] = pd.to_numeric(student_answers_from_bank['Marks'], errors='coerce')
            graded_answers = student_answers_from_bank.dropna(subset=['Marks_Numeric'])
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
            st.info("No graded answers to review yet.")
    
    with leaderboard_tab:
        st.subheader(f"Class Leaderboard ({student_class})")
        df_students_class = df_all_users[df_all_users['Class'] == student_class]
        class_gmail_list = df_students_class['Gmail_ID'].tolist()
        class_answers_bank = df_answer_bank[df_answer_bank['Student_Gmail'].isin(class_gmail_list)].copy()
        if class_answers_bank.empty or 'Marks' not in class_answers_bank.columns:
            st.info("The leaderboard will appear once answers have been graded for your class.")
        else:
            class_answers_bank['Marks'] = pd.to_numeric(class_answers_bank['Marks'], errors='coerce')
            graded_class_answers = class_answers_bank.dropna(subset=['Marks'])
            if graded_class_answers.empty:
                st.info("The leaderboard will appear once answers have been graded for your class.")
            else:
                leaderboard_df = graded_class_answers.groupby('Student_Gmail')['Marks'].mean().reset_index()
                leaderboard_df = pd.merge(leaderboard_df, df_students_class[['User_Name', 'Gmail_ID']], left_on='Student_Gmail', right_on='Gmail_ID', how='left')
                leaderboard_df['Rank'] = leaderboard_df['Marks'].rank(method='dense', ascending=False).astype(int)
                leaderboard_df = leaderboard_df.sort_values(by='Rank')
                leaderboard_df['Marks'] = leaderboard_df['Marks'].round(2)
                st.markdown("##### 🏆 Top 3 Performers")
                top_3_df = leaderboard_df.head(3)
                st.dataframe(top_3_df[['Rank', 'User_Name', 'Marks']])
                if not top_3_df.empty:
                    fig = px.bar(
                        top_3_df, x='User_Name', y='Marks', color='User_Name',
                        title=f"Top 3 Performers in {student_class}",
                        labels={'Marks': 'Average Marks', 'User_Name': 'Student'},
                        text='Marks'
                    )
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown("---")
                my_rank_row = leaderboard_df[leaderboard_df['Student_Gmail'] == st.session_state.user_gmail]
                if not my_rank_row.empty:
                    my_rank = my_rank_row.iloc[0]['Rank']
                    my_avg_marks = my_rank_row.iloc[0]['Marks']
                    st.success(f"**Your Current Rank:** {my_rank} (with an average score of **{my_avg_marks}**)")
                else:
                    st.warning("Your rank will be shown here after your answers are graded.")
else:
    st.error("Could not find your student record.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
