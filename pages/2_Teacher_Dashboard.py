import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Teacher Dashboard")
DATE_FORMAT = "%Y-%m-%d"
GRADE_MAP = {"Needs Improvement": 1, "Average": 2, "Good": 3, "Very Good": 4, "Outstanding": 5}

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
    HOMEWORK_QUESTIONS_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(_sheet):
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df.columns = df.columns.str.strip()
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "teacher":
    st.error("You must be logged in as a Teacher to access this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === TEACHER DASHBOARD UI ===
st.header(f"🧑‍🏫 Teacher Dashboard: Welcome {st.session_state.user_name}")

# --- DEBUGGING CODE START ---
# This block will run first to show you what the app is reading.
st.warning("RUNNING DEBUG TEST FOR HOMEWORK_QUESTIONS_SHEET")
try:
    df_homework_debug = load_data(HOMEWORK_QUESTIONS_SHEET)
    
    st.write("Columns found in HOMEWORK_QUESTIONS_SHEET:")
    st.write(list(df_homework_debug.columns))
    
    st.write("First 5 rows of data:")
    st.dataframe(df_homework_debug.head())
    
except Exception as e:
    st.error("An error occurred while reading the sheet for debugging:")
    st.exception(e)
st.stop()
# --- DEBUGGING CODE END ---


# The rest of your dashboard code is below.
# Once the error is fixed, you can remove the debugging block above.

df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_all_answers = load_data(MASTER_ANSWER_SHEET)
df_users = load_data(ALL_USERS_SHEET)

st.subheader("Today's Submitted Homework")
today_str = datetime.today().strftime(DATE_FORMAT)
todays_homework = df_homework[
    (df_homework.get('Uploaded By') == st.session_state.user_name) &
    (df_homework.get('Date') == today_str)
]
if todays_homework.empty:
    st.info("You have not created any homework assignments today.")
else:
    summary = todays_homework.groupby(['Class', 'Subject']).size().reset_index(name='Question Count')
    for _, row in summary.iterrows():
        st.success(f"Class: **{row['Class']}** | Subject: **{row['Subject']}** | Questions: **{row['Question Count']}**")
st.markdown("---")

create_tab, grade_tab, report_tab = st.tabs(["Create Homework", "Grade Answers", "My Reports"])
# (Rest of your dashboard code for tabs goes here)
)
    df_homework['Date_dt'] = pd.to_datetime(df_homework['Date'], errors='coerce')
    teacher_homework = df_homework[df_homework['Uploaded By'] == st.session_state.user_name]

    if teacher_homework.empty:
        st.info("No homework created yet.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.today() - timedelta(days=7))
        with col2:
            end_date = st.date_input("End Date", datetime.today())
        filtered = teacher_homework[
            (teacher_homework['Date_dt'] >= pd.to_datetime(start_date)) &
            (teacher_homework['Date_dt'] <= pd.to_datetime(end_date))
        ]
        if filtered.empty:
            st.warning("No homework found in selected range.")
        else:
            summary = filtered.groupby(['Class', 'Subject']).size().reset_index(name='Total')
            st.dataframe(summary)
            fig = px.bar(summary, x='Class', y='Total', color='Subject', title='Homework Summary')
            st.plotly_chart(fig, use_container_width=True)
