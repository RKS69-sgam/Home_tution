import streamlit as st
import pandas as pd
import gspread
import json
import base64
import plotly.express as px
from datetime import datetime, timedelta

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Principal Dashboard")

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

# === SHEET IDs ===
ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
HOMEWORK_QUESTIONS_SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
MASTER_ANSWER_SHEET_ID = "1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0"
ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"

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

# Display Public Announcement
try:
    announcements_df = load_data(ANNOUNCEMENTS_SHEET_ID)
    if not announcements_df.empty:
        latest_announcement = announcements_df['Message'].iloc[0]
        if latest_announcement:
            st.info(f"📢 **Latest Public Announcement:** {latest_announcement}")
except Exception:
    pass

# Load all necessary data once
df_users = load_data(ALL_USERS_SHEET_ID)
df_answers = load_data(MASTER_ANSWER_SHEET_ID)
df_homework = load_data(HOMEWORK_QUESTIONS_SHEET_ID)

instruction_tab, report_tab = st.tabs(["Send Messages", "Performance Reports"])

with instruction_tab:
    st.subheader("Send a Message")
    
    message_type = st.radio("Select message type:", ["Individual Instruction", "Public Announcement"])
    
    if message_type == "Individual Instruction":
        st.markdown("##### Send an Instruction to a Single User")
        if df_users.empty:
            st.warning("No users found in the database.")
        else:
            search_term = st.text_input("Search for a User by Name:")
            df_temp = df_users.copy()
            df_temp['display_name'] = df_temp.apply(
                lambda row: f"{row['User Name']} ({row['Class']})" if row['Role'] == 'Student' and row.get('Class') else row['User Name'],
                axis=1
            )
            if search_term:
                filtered_users = df_temp[df_temp['display_name'].str.contains(search_term, case=False, na=False)]
            else:
                filtered_users = df_temp
            
            user_list = filtered_users['display_name'].tolist()

            with st.form("instruction_form"):
                if not user_list:
                    st.warning("No users found matching your search.")
                else:
                    selected_display_name = st.selectbox("Select a User (Teacher or Student)", user_list)
                    instruction_text = st.text_area("Instruction:")
                    if st.form_submit_button("Send Instruction"):
                        if selected_display_name and instruction_text:
                            real_user_name = selected_display_name.split(' (')[0]
                            user_row = df_users[df_users['User Name'] == real_user_name]
                            if not user_row.empty:
                                row_id = int(user_row.iloc[0]['Row ID'])
                                instruction_col = df_users.columns.get_loc('Instructions') + 1
                                client = connect_to_gsheets()
                                sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                                sheet.update_cell(row_id, instruction_col, instruction_text)
                                st.success(f"Instruction sent to {real_user_name}.")
                                load_data.clear()
                        else:
                            st.warning("Please select a user and write an instruction.")

    elif message_type == "Public Announcement":
        st.markdown("##### Broadcast a Message to All Dashboards")
        with st.form("announcement_form"):
            announcement_text = st.text_area("Enter Public Announcement:")
            if st.form_submit_button("Broadcast Announcement"):
                if announcement_text:
                    client = connect_to_gsheets()
                    announcement_sheet_obj = client.open_by_key(ANNOUNCEMENTS_SHEET_ID).sheet1
                    announcement_sheet_obj.insert_row([announcement_text], 2)
                    st.success("Public announcement sent to all dashboards!")
                    load_data.clear()
                else:
                    st.warning("Announcement text cannot be empty.")

with report_tab:
    st.subheader("Performance Reports")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🏆 Top 3 Teachers (by Points)")
        df_teachers = df_users[df_users['Role'].isin(['Teacher', 'Admin', 'Principal'])].copy()
        df_teachers['Salary Points'] = pd.to_numeric(df_teachers.get('Salary Points', 0), errors='coerce').fillna(0)
        top_teachers = df_teachers.nlargest(3, 'Salary Points')
        st.dataframe(top_teachers[['User Name', 'Role', 'Salary Points']])

    with col2:
        st.markdown("#### 📉 Students Needing Improvement")
        df_students = df_users[df_users['Role'] == 'Student']
        if not df_answers.empty:
            df_answers['Marks'] = pd.to_numeric(df_answers.get('Marks'), errors='coerce')
            graded_answers = df_answers.dropna(subset=['Marks'])
            if not graded_answers.empty:
                student_performance = graded_answers.groupby('Student Gmail')['Marks'].mean().reset_index()
                merged_df = pd.merge(student_performance, df_students, left_on='Student Gmail', right_on='Gmail ID')
                weakest_students = merged_df.nsmallest(5, 'Marks').round(2)
                st.dataframe(weakest_students[['User Name', 'Class', 'Marks']])
            else:
                st.info("No graded answers available to determine student performance.")
        else:
            st.info("No student answers available yet.")

    st.markdown("---")
    st.subheader("Class-wise Student Performance")
    if df_answers.empty or df_students.empty:
        st.info("Leaderboard will be generated once students submit and get graded.")
    else:
        df_answers['Marks'] = pd.to_numeric(df_answers.get('Marks'), errors='coerce')
        graded_answers_all = df_answers.dropna(subset=['Marks'])
        if graded_answers_all.empty:
            st.info("The leaderboard is available after answers have been graded.")
        else:
            df_merged_all = pd.merge(graded_answers_all, df_students, left_on='Student Gmail', right_on='Gmail ID')
            leaderboard_df_all = df_merged_all.groupby(['Class', 'User Name'])['Marks'].mean().reset_index()
            top_students_df_all = leaderboard_df_all.groupby('Class').apply(lambda x: x.nlargest(3, 'Marks')).reset_index(drop=True)
            top_students_df_all['Marks'] = top_students_df_all['Marks'].round(2)
            
            st.markdown("#### 🥇 Top 3 Students per Class")
            st.dataframe(top_students_df_all)
            
            fig = px.bar(top_students_df_all, x='User Name', y='Marks', color='Class',
                         title='Top 3 Students by Average Marks per Class',
                         labels={'Marks': 'Average Marks', 'User Name': 'Student'})
            st.plotly_chart(fig, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown(
"""
<div style='text-align: center; font-size: 12px;'>
© 2025 PRK Home Tuition.<br>All Rights Reserved.
</div>
""",
unsafe_allow_html=True
)
