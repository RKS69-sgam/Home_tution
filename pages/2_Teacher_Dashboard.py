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
GRADE_MAP_REVERSE = {v: k for k, v in GRADE_MAP.items()}

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
st.warning("RUNNING DEBUG TEST FOR MASTER_ANSWER_SHEET")
try:
    df_answers_debug = load_data(MASTER_ANSWER_SHEET)
    
    st.write("Columns found in MASTER_ANSWER_SHEET:")
    st.write(list(df_answers_debug.columns))
    
    st.write("First 5 rows of data:")
    st.dataframe(df_answers_debug.head())
    
except Exception as e:
    st.error("An error occurred while reading the sheet for debugging:")
    st.exception(e)
st.stop()
# --- DEBUGGING CODE END ---


# The rest of your dashboard code is below.
# Once the error is fixed, you can remove the debugging block above.

# Load all necessary data once
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET)
df_all_answers = load_data(MASTER_ANSWER_SHEET)
df_users = load_data(ALL_USERS_SHEET)

# Display a summary of today's submitted homework
st.subheader("Today's Submitted Homework")
# (Rest of dashboard code)
