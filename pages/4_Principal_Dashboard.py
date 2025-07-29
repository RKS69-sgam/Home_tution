import streamlit as st
import pandas as pd
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Principal Dashboard")

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"
    MASTER_ANSWER_SHEET_ID = "1lW2Eattf9kyhllV_NzMMq9tznibkhNJ4Ma-wLV5rpW0"
    ANNOUNCEMENTS_SHEET_ID = "1zEAhoWC9_3UK09H4cFk6lRd6i5ChF3EknVc76L7zquQ"

except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(sheet_id):
    try:
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

# Load data once
df_users = load_data(ALL_USERS_SHEET_ID)
df_answers = load_data(MASTER_ANSWER_SHEET_ID)

tab1, tab2 = st.tabs(["Send Messages", "View Reports"])

with tab1:
    st.subheader("Send a Message")
    
    message_type = st.radio("Select message type:", ["Private Instruction", "Public Announcement"])
    
    if message_type == "Private Instruction":
        with st.form("instruction_form"):
            # Create a temporary copy to avoid warnings
            df_temp = df_users.copy()
            
            # Create a new column that combines Name and Class for students
            df_temp['display_name'] = df_temp.apply(
            lambda row: f"{row['User Name']} ({row['Class']})" if row['Role'] == 'Student' else row['User Name'],
            axis=1
            )

            # Create the list from the new column
            user_list = df_temp['display_name'].tolist()

            selected_user = st.selectbox("Select a User (Teacher or Student)", user_list)
            instruction_text = st.text_area("Instruction:")
            
            if st.form_submit_button("Send Instruction"):
                if selected_user and instruction_text:
                    user_row = df_users[df_users['User Name'] == selected_user]
                    if not user_row.empty:
                        row_id = int(user_row.iloc[0]['Row ID'])
                        instruction_col = df_users.columns.get_loc('Instructions') + 1
                        sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                        sheet.update_cell(row_id, instruction_col, instruction_text)
                        st.success(f"Instruction sent to {selected_user}.")
                        load_data.clear()
                else:
                    st.warning("Please select a user and write an instruction.")

    elif message_type == "Public Announcement":
        with st.form("announcement_form"):
            announcement_text = st.text_area("Enter Public Announcement:")
            if st.form_submit_button("Broadcast Announcement"):
                if announcement_text:
                    announcement_sheet_obj = client.open_by_key(ANNOUNCEMENTS_SHEET_ID).sheet1
                    announcement_sheet_obj.insert_row([announcement_text], 2)
                    st.success("Public announcement sent to all dashboards!")
                    load_data.clear()
                else:
                    st.warning("Announcement text cannot be empty.")

with tab2:
    st.subheader("Class-wise Top 3 Students Report")
    
    df_students_report = df_users[df_users['Role'] == 'Student']
    
    if df_answers.empty or df_students_report.empty:
        st.info("Leaderboard will be generated once students submit and get graded.")
    else:
        df_answers['Marks'] = pd.to_numeric(df_answers.get('Marks'), errors='coerce')
        df_answers.dropna(subset=['Marks'], inplace=True)
        
        if df_answers.empty:
            st.info("The leaderboard is available after answers have been graded.")
        else:
            df_merged = pd.merge(df_answers, df_students_report, left_on='Student Gmail', right_on='Gmail ID')
            leaderboard_df = df_merged.groupby(['Class', 'User Name'])['Marks'].mean().reset_index()
            top_students_df = leaderboard_df.groupby('Class').apply(lambda x: x.nlargest(3, 'Marks')).reset_index(drop=True)
            top_students_df['Marks'] = top_students_df['Marks'].round(2)
            
            st.dataframe(top_students_df)
            
            fig = px.bar(top_students_df, x='User Name', y='Marks', color='Class',
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
