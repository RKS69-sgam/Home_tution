import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
import base64
import time
import plotly.express as px
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Student Dashboard")
DATE_FORMAT = "%d-%m-%Y"
GRADE_MAP_REVERSE = {1: "Needs Improvement", 2: "Average", 3: "Good", 4: "Very Good", 5: "Outstanding"}

# === UTILITY FUNCTIONS ===
@st.cache_resource
def connect_to_gsheets():
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

def get_text_similarity(text1, text2):
    try:
        vectorizer = TfidfVectorizer()
        vectors = vectorizer.fit_transform([text1, text2])
        similarity_matrix = cosine_similarity(vectors)
        return similarity_matrix[0][1] * 100
    except Exception:
        return 0.0

def get_grade_from_similarity(percentage):
    if percentage >= 95: return 5
    elif percentage >= 80: return 4
    elif percentage >= 60: return 3
    elif percentage >= 40: return 2
    else: return 1

# === SHEET IDs ===
ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
HOMEWORK_QUESTIONS_SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
MASTER_ANSWER_SHEET_ID = "1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0"
ANSWER_BANK_SHEET_ID = "12S2YwNPHZIVtWSqXaRHIBakbFqoBVB4xcAcFfpwN3uw"
ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "student":
    st.error("You must be logged in as a Student to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT & COPYRIGHT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)

# === STUDENT DASHBOARD UI ===
st.header(f"🧑‍🎓 Student Dashboard: Welcome {st.session_state.user_name}")

# --- INSTRUCTION & ANNOUNCEMENT SYSTEMS ---
df_all_users = load_data(ALL_USERS_SHEET_ID)
user_info_row = df_all_users[df_all_users['Gmail ID'] == st.session_state.user_gmail]
if not user_info_row.empty:
    user_info = user_info_row.iloc[0]
    # (Your instruction and announcement display logic here)
    st.markdown("---")

    # Load other necessary data
    df_homework = load_data(HOMEWORK_QUESTIONS_SHEET_ID)
    df_live_answers = load_data(MASTER_ANSWER_SHEET_ID)
    df_answer_bank = load_data(ANSWER_BANK_SHEET_ID)
    
    student_class = user_info.get("Class")
    st.subheader(f"Your Class: {student_class}")
    st.markdown("---")

    # Filter dataframes for the current student
    homework_for_class = df_homework[df_homework.get("Class") == student_class]
    student_answers_live = df_live_answers[df_live_answers.get('Student Gmail') == st.session_state.user_gmail].copy()
    student_answers_from_bank = df_answer_bank[df_answer_bank.get('Student Gmail') == st.session_state.user_gmail].copy()
    
    # (Your performance chart logic here)
    st.markdown("---")
    
    pending_tab, revision_tab, leaderboard_tab = st.tabs(["Pending Homework", "Revision Zone", "Class Leaderboard"])
    
    with pending_tab:
        st.subheader("Pending Questions")
        pending_questions_list = []
        # (Logic to find pending questions remains the same)
        
        if not pending_questions_list:
            st.success("🎉 Good job! You have no pending homework.")
        else:
            df_pending = pd.DataFrame(pending_questions_list).sort_values(by='Date', ascending=False)
            for i, row in df_pending.iterrows():
                st.markdown(f"**Assignment Date:** {row.get('Date')} | **Due Date:** {row.get('Due_Date')}")
                st.write(f"**Question:** {row.get('Question')}")

                question_id = f"question_{i}"
                if question_id not in st.session_state:
                    st.session_state[question_id] = 'initial'

                if st.session_state[question_id] == 'initial':
                    if st.button("View Model Answer & Start Timer", key=f"view_{i}"):
                        st.session_state[question_id] = 'timer_running'
                        st.rerun()

                elif st.session_state[question_id] == 'timer_running':
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
                        answer_text = st.text_area("Your Answer:", key=f"answer_{i}")
                        if st.form_submit_button("Submit Final Answer"):
                            if answer_text:
                                with st.spinner("Grading your answer..."):
                                    model_answer = row.get('Model_Answer', '').strip()
                                    if not model_answer:
                                        st.error("Auto-grading failed: Model answer not found.")
                                    else:
                                        similarity = get_text_similarity(answer_text, model_answer)
                                        grade_score = get_grade_from_similarity(similarity)
                                        client = connect_to_gsheets()
                                        if grade_score >= 3: # Good, Very Good, or Outstanding
                                            sheet = client.open_by_key(ANSWER_BANK_SHEET_ID).sheet1
                                            remark = f"Auto-Graded: Well done! ({similarity:.2f}%)" if grade_score >= 4 else "Good! Try for better performance next time."
                                            st.success(f"Good work! Your answer was {similarity:.2f}% correct and has been saved.")
                                        else: # Needs Improvement or Average
                                            sheet = client.open_by_key(MASTER_ANSWER_SHEET_ID).sheet1
                                            remark = f"Auto-Remark: Your answer was {similarity:.2f}% correct. Please review and improve it."
                                            grade_score = "" # Marks left blank for auto-return
                                            st.warning(f"Your answer was {similarity:.2f}% correct. Please review the auto-remark and resubmit.")
                                        
                                        new_row_data = [st.session_state.user_gmail, row.get('Date'), student_class, row.get('Subject'), row.get('Question'), answer_text, grade_score, remark]
                                        sheet.append_row(new_row_data, value_input_option='USER_ENTERED')
                                        load_data.clear()
                                        st.rerun()
                            else:
                                st.warning("Answer cannot be empty.")
                
                with st.form(key=f"help_form_{i}"):
                    help_text = st.text_input("Need help? Ask your teacher a question:")
                    if st.form_submit_button("Ask for Help"):
                        if help_text:
                            # (Logic to save help request)
                            pass
                        else:
                            st.warning("Please type your question before asking for help.")
                st.markdown("---")

    with revision_tab:
        # (Full revision tab logic here)
        pass
    
    with leaderboard_tab:
        # (Full leaderboard tab logic here)
        pass
else:
    st.error("Could not find your student record.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>© 2025 PRK Home Tuition. All Rights Reserved.</p>", unsafe_allow_html=True)
