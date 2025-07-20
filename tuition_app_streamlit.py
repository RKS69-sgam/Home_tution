import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt
import gspread
import json
import base64
import mimetypes
import hashlib
import plotly.express as px

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition")
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30

# === GOOGLE DRIVE FOLDER IDs ===
HOMEWORK_FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe"
NOTEBOOK_FOLDER_ID = "1diGm7ukz__yVze4JlH3F-oJ7GBsPJkHy"
RECEIPT_FOLDER_ID = "1dlDauaPLZ-FQGzS2rIIyMnVjmUiBIAfr"

# === AUTHENTICATION ===
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
try:
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    drive_service = build("drive", "v3", credentials=credentials)
except Exception as e:
    st.error("Error connecting to Google APIs. Please check your credentials and sharing permissions.")
    st.stop()

# === GOOGLE SHEETS ===
try:
    STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
    TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
    HOMEWORK_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1
except gspread.exceptions.SpreadsheetNotFound:
    st.error("One or more Google Sheets were not found. Please check the Sheet Keys.")
    st.stop()
except HttpError as e:
    st.error(f"An error occurred accessing Google Sheets. Ensure they are shared with the service account: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
def make_hashes(password):
    """Hashes the password for security."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    """Checks if the provided password matches the stored hash."""
    if hashed_text:
        return make_hashes(password) == hashed_text
    return False

def upload_to_drive(path, folder_id, filename):
    """Uploads a file to Google Drive and returns its shareable link."""
    try:
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        media = MediaFileUpload(path, mimetype=mime_type, resumable=True)
        metadata = {"name": filename, "parents": [folder_id]}
        file = drive_service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
        return file.get('webViewLink')
    except HttpError as error:
        st.error(f"An error occurred while uploading to Google Drive: {error}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during upload: {e}")
        return None

def create_receipt(student_name, gmail, cls, subs_date, till_date):
    """Creates a payment receipt and uploads it to Drive."""
    doc = Document()
    title = doc.add_paragraph("PRK Home Tuition\nAdvance Classes\n\nReceipt")
    title.alignment = 1
    title.runs[0].bold = True
    title.runs[0].font.size = Pt(16)
    doc.add_paragraph(f"Name: {student_name}")
    doc.add_paragraph(f"Class: {cls}")
    doc.add_paragraph(f"Gmail: {gmail}")
    doc.add_paragraph(f"Subscription Date: {subs_date}")
    doc.add_paragraph(f"Valid Till: {till_date}")
    path = f"/tmp/receipt_{student_name}.docx"
    doc.save(path)
    return upload_to_drive(path, RECEIPT_FOLDER_ID, f"Receipt_{student_name}.docx")

def load_data(sheet):
    """Loads data from the specified Google Sheet."""
    return pd.DataFrame(sheet.get_all_records())

def save_students_data(df):
    """Saves the students DataFrame to the Google Sheet."""
    df_str = df.fillna("").astype(str)
    STUDENT_SHEET.clear()
    STUDENT_SHEET.update([df_str.columns.values.tolist()] + df_str.values.tolist())

def save_teachers_data(df):
    """Saves the teachers DataFrame to the Google Sheet."""
    df_str = df.fillna("").astype(str)
    TEACHER_SHEET.clear()
    TEACHER_SHEET.update([df_str.columns.values.tolist()] + df_str.values.tolist())

# === SESSION STATE INITIALIZATION ===
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.logged_in = False

# === SIDEBAR & HEADER ===
st.sidebar.title("Login / Register")
if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("🏫 PRK Home Tuition App")
st.markdown("---")

# === LOGIN / REGISTRATION ROUTING ===
if not st.session_state.logged_in:
    role = st.sidebar.radio("Login As:", ["Student", "Teacher", "Register", "Admin", "Principal"])

    if role == "Register":
        st.header("✍️ Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            st.subheader("Student Registration")
            with st.form("student_registration_form"):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
                pwd = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Register (After Payment)")

                if submitted:
                    if not all([name, gmail, cls, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df = load_data(STUDENT_SHEET)
                        if gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            hashed_password = make_hashes(pwd)
                            till_date = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime("%Y-%m-%d")
                            new_row = {
                                "Sr. No.": len(df) + 1, "Student Name": name, "Gmail ID": gmail,
                                "Class": cls, "Password": hashed_password,
                                "Subscription Date": "", "Subscribed Till": till_date,
                                "Payment Confirmed": "No"
                            }
                            df_new = pd.DataFrame([new_row])
                            df = pd.concat([df, df_new], ignore_index=True)
                            save_students_data(df)
                            st.success("Registration successful! Waiting for payment confirmation by admin.")
                            st.balloons()
            st.subheader("Payment Details")
            st.code(f"UPI ID: {UPI_ID}", language="text")

        elif registration_type == "Teacher":
            st.subheader("Teacher Registration")
            with st.form("teacher_registration_form"):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                pwd = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Register Teacher")
                
                if submitted:
                    if not all([name, gmail, pwd]):
                        st.warning("Please fill in all details.")
                    else:
                        df_teachers = load_data(TEACHER_SHEET)
                        if gmail in df_teachers["Gmail ID"].values:
                            st.error("This Gmail is already registered as a teacher.")
                        else:
                            hashed_password = make_hashes(pwd)
                            new_row = {
                                "Sr. No.": len(df_teachers) + 1,
                                "Teacher Name": name,
                                "Gmail ID": gmail,
                                "Password": hashed_password,
                                "Confirmed": "No"
                            }
                            df_new = pd.DataFrame([new_row])
                            df_teachers = pd.concat([df_teachers, df_new], ignore_index=True)
                            save_teachers_data(df_teachers)
                            st.success("Teacher registered successfully! Please wait for admin confirmation.")
                            st.balloons()
    else:
        st.header(f"🔑 {role} Login")
        with st.form(f"{role}_login_form"):
            login_gmail = st.text_input("Gmail ID").lower().strip()
            login_pwd = st.text_input("Password", type="password")
            login_submitted = st.form_submit_button("Login")

            if login_submitted:
                if role in ["Admin", "Principal", "Teacher"]:
                    sheet_to_check = TEACHER_SHEET
                    name_col = "Teacher Name"
                else:
                    sheet_to_check = STUDENT_SHEET
                    name_col = "Student Name"

                df_users = load_data(sheet_to_check)
                user_data = df_users[df_users["Gmail ID"] == login_gmail]

                if not user_data.empty:
                    user_row = user_data.iloc[0]
                    hashed_pwd_from_sheet = user_row["Password"]

                    if check_hashes(login_pwd, hashed_pwd_from_sheet):
                        can_login = False
                        if role == "Student":
                            if user_row["Payment Confirmed"] == "Yes" and datetime.today() <= pd.to_datetime(user_row["Subscribed Till"]):
                                can_login = True
                            else:
                                st.error("Your subscription has expired or is not yet confirmed.")
                        elif role == "Teacher":
                            if user_row["Confirmed"] == "Yes":
                                can_login = True
                            else:
                                st.error("Your registration is pending confirmation from the admin.")
                        elif role in ["Admin", "Principal"]:
                            can_login = True

                        if can_login:
                            st.session_state.logged_in = True
                            st.session_state.user_name = user_row[name_col]
                            st.session_state.user_role = role.lower()
                            st.rerun()
                    else:
                        st.error("Invalid Gmail ID or Password.")
                else:
                    st.error("Invalid Gmail ID or Password.")

# === LOGGED-IN USER PANELS ===
if st.session_state.logged_in:
    current_role = st.session_state.user_role.lower()

    if current_role == "admin":
        st.header("👑 Admin Panel")
        tab1, tab2 = st.tabs(["Student Management", "Teacher Management"])

        with tab1:
            st.subheader("Manage Student Registrations")
            df_students = load_data(STUDENT_SHEET)
            st.markdown("#### Pending Payment Confirmations")
            unconfirmed_students = df_students[df_students["Payment Confirmed"] != "Yes"]

            if unconfirmed_students.empty:
                st.info("No pending student payments to confirm.")
            else:
                for i, row in unconfirmed_students.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Name:** {row['Student Name']} | **Gmail:** {row['Gmail ID']}")
                    with col2:
                        if st.button("✅ Confirm Payment", key=f"confirm_student_{row['Gmail ID']}", use_container_width=True):
                            df_students.loc[i, "Subscription Date"] = datetime.today().strftime("%Y-%m-%d")
                            df_students.loc[i, "Subscribed Till"] = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime("%Y-%m-%d")
                            df_students.loc[i, "Payment Confirmed"] = "Yes"
                            save_students_data(df_students)
                            st.success(f"Payment confirmed for {row['Student Name']}.")
                            st.rerun()
            st.markdown("---")
            st.markdown("#### Confirmed Students")
            confirmed_students = df_students[df_students["Payment Confirmed"] == "Yes"]
            st.dataframe(confirmed_students)

        with tab2:
            st.subheader("Manage Teacher Registrations")
            df_teachers = load_data(TEACHER_SHEET)
            st.markdown("#### Pending Teacher Confirmations")
            unconfirmed_teachers = df_teachers[df_teachers.get("Confirmed", "Yes") != "Yes"]

            if unconfirmed_teachers.empty:
                st.info("No pending teacher confirmations.")
            else:
                for i, row in unconfirmed_teachers.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Name:** {row['Teacher Name']} | **Gmail:** {row['Gmail ID']}")
                    with col2:
                        if st.button("✅ Confirm Teacher", key=f"confirm_teacher_{row['Gmail ID']}", use_container_width=True):
                            df_teachers.loc[i, "Confirmed"] = "Yes"
                            save_teachers_data(df_teachers)
                            st.success(f"Teacher {row['Teacher Name']} has been confirmed.")
                            st.rerun()

            st.markdown("---")
            st.markdown("#### Confirmed Teachers")
            confirmed_teachers = df_teachers[df_teachers.get("Confirmed") == "Yes"]
            st.dataframe(confirmed_teachers)

    elif current_role == "teacher":
        st.header("🧑‍🏫 Teacher Dashboard")
        st.subheader("Upload Homework")
        with st.form("homework_upload_form"):
            subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK"])
            cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
            date = st.date_input("Date", datetime.today())
            uploaded_file = st.file_uploader("Upload Homework File", type=["docx", "pdf", "jpg", "png", "txt"])
            upload_button = st.form_submit_button("Upload Homework")

            if upload_button and uploaded_file:
                fname = f"{subject}_{cls}_{date.strftime('%Y-%m-%d')}_{uploaded_file.name}"
                path = f"/tmp/{fname}"
                with open(path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                link = upload_to_drive(path, HOMEWORK_FOLDER_ID, fname)
                if link:
                    HOMEWORK_SHEET.append_row([cls, date.strftime('%Y-%m-%d'), fname, link, st.session_state.user_name, subject])
                    st.success(f"Homework uploaded successfully: [📎 {fname}]({link})")
                    os.remove(path)

    elif current_role == "student":
        st.header("🧑‍🎓 Student Dashboard")
        df_students = load_data(STUDENT_SHEET)
        user_info = df_students[df_students["Student Name"] == st.session_state.user_name].iloc[0]
        student_class = user_info["Class"]

        st.subheader("View Homework")
        hw_date = st.date_input("Select date for homework:", datetime.today())
        
        all_homework = load_data(HOMEWORK_SHEET)
        if not all_homework.empty:
            hw_for_date = all_homework[(all_homework["Class"] == student_class) & (all_homework["Date"] == str(hw_date.strftime('%Y-%m-%d')))]
            if not hw_for_date.empty:
                for _, row in hw_for_date.iterrows():
                    st.markdown(f"📘 **{row['Subject']}**: [{row['File Name']}]({row['Drive Link']})")
            else:
                st.warning("No homework found for the selected date.")

        st.subheader("Upload Completed Work")
        completed_work = st.file_uploader("Upload your notebook/worksheet", type=["pdf", "jpg", "png"])
        if completed_work and st.button("Upload Completed Work"):
            fname = f"{st.session_state.user_name}_{hw_date.strftime('%Y-%m-%d')}_{completed_work.name}"
            path = f"/tmp/{fname}"
            with open(path, "wb") as f:
                f.write(completed_work.getbuffer())
            
            link = upload_to_drive(path, NOTEBOOK_FOLDER_ID, fname)
            if link:
                st.success(f"Your work was uploaded successfully: [📎 {fname}]({link})")
                os.remove(path)

    elif current_role == "principal":
        st.header("🏛️ Principal Dashboard")
        st.subheader("📊 Homework Upload Analytics")
        df_homework = load_data(HOMEWORK_SHEET)
        if not df_homework.empty:
            df_homework["Date"] = pd.to_datetime(df_homework["Date"], errors='coerce').dt.date
            
            st.dataframe(df_homework)

            fig1 = px.bar(df_homework, x="Uploaded By", y=None, color="Subject", title="Uploads per Teacher")
            st.plotly_chart(fig1, use_container_width=True)
            
            trend = df_homework.groupby("Date").size().reset_index(name="Count")
            fig2 = px.line(trend, x="Date", y="Count", title="Upload Trend Over Time", markers=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No homework data available for analysis.")

