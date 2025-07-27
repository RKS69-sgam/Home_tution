import streamlit as st
import pandas as pd
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Principal Dashboard")

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
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

tab1, tab2 = st.tabs(["Send Instructions to Teachers", "View Reports"])

with tab1:
    st.subheader("Send Instruction to a Teacher")
    df_users = load_data(ALL_USERS_SHEET)
    df_teachers = df_users[df_users['Role'] == 'Teacher']
    
    if df_teachers.empty:
        st.warning("No teachers found in the database.")
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
                        
                        ALL_USERS_SHEET.update_cell(row_id, instruction_col, instruction_text)
                        st.success(f"Instruction sent to {selected_teacher}.")
                        load_data.clear() # Clear cache to reflect changes
                    else:
                        st.error("Could not find the selected teacher to update.")
                else:
                    st.warning("Please select a teacher and write an instruction.")

with tab2:
    st.subheader("Class-wise Top 3 Students Report")
    
    df_answers_report = load_data(MASTER_ANSWER_SHEET)
    df_users_report = load_data(ALL_USERS_SHEET)
    df_students_report = df_users_report[df_users_report['Role'] == 'Student']
    
    if df_answers_report.empty or df_students_report.empty:
        st.info("Leaderboard will be generated once students submit answers and they are graded.")
    else:
        df_answers_report['Marks'] = pd.to_numeric(df_answers_report['Marks'], errors='coerce')
        df_answers_report.dropna(subset=['Marks'], inplace=True)
        
        if df_answers_report.empty:
            st.info("The leaderboard is available after answers have been graded.")
        else:
            df_merged = pd.merge(df_answers_report, df_students_report, left_on='Student Gmail', right_on='Gmail ID')
            
            leaderboard_df = df_merged.groupby(['Class', 'User Name'])['Marks'].mean().reset_index()
            
            top_students_df = leaderboard_df.groupby('Class').apply(
                lambda x: x.nlargest(3, 'Marks')
            ).reset_index(drop=True)
            
            top_students_df['Marks'] = top_students_df['Marks'].round(2)
            
            st.dataframe(top_students_df)
            
            fig = px.bar(top_students_df, x='User Name', y='Marks', color='Class',
                         title='Top 3 Students by Average Marks per Class',
                         labels={'Marks': 'Average Marks', 'User Name': 'Student'})
            st.plotly_chart(fig, use_container_width=True)
