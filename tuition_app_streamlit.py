import streamlit as st
import os
import base64
import json
import pandas as pd
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from fpdf import FPDF
import gspread

# === CONFIG ===
LOGO_PATH = "logo.png"
FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe"  # Homework folder
SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
STUDENT_SHEET_ID = "10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno"
TEACHER_SHEET_ID = "1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8"
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
NOTEBOOK_DIR = "uploaded_notebooks"
os.makedirs(NOTEBOOK_DIR, exist_ok=True)

# === GOOGLE AUTH ===
SERVICE_JSON = json.loads(base64.b64decode(st.secrets["google_service"]["base64_credentials"]))
creds = Credentials.from_service_account_info(SERVICE_JSON, scopes=["https://www.googleapis.com/auth/drive"])
drive_service = build("drive", "v3", credentials=creds)
gc = gspread.authorize(creds)
homework_sheet = gc.open_by_key(SHEET_ID).sheet1
student_sheet = gc.open_by_key(STUDENT_SHEET_ID).sheet1
teacher_sheet = gc.open_by_key(TEACHER_SHEET_ID).sheet1

# === UTILS ===
def load_students():
    return pd.DataFrame(student_sheet.get_all_records())

def load_teachers():
    return pd.DataFrame(teacher_sheet.get_all_records())

def save_students(df):
    df = df.fillna("").astype(str)
    student_sheet.clear()
    student_sheet.update([df.columns.values.tolist()] + df.values.tolist())

def upload_to_drive(local_path, folder_id, subject, date_str):
    ext = os.path.splitext(local_path)[1]
    file_name = f"{subject}_{date_str}{ext}"
    metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(local_path, resumable=True)
    uploaded = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()
    drive_service.permissions().create(fileId=uploaded["id"], body={"type": "anyone", "role": "reader"}).execute()
    return f"https://drive.google.com/file/d/{uploaded['id']}/view?usp=sharing"

def save_homework_entry(row):
    df = pd.DataFrame(homework_sheet.get_all_records())
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    homework_sheet.clear()
    homework_sheet.update([df.columns.tolist()] + df.values.tolist())

def generate_pdf(text, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    for line in text.split("\n"):
        pdf.multi_cell(0, 10, line)
    pdf.output(output_path)

# === UI CONFIG ===
st.set_page_config(layout="wide")
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=160)
st.title("🏫 PRK Home Tuition Advance Classes")
st.sidebar.title("🔐 Login Menu")

if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.success("Logged out.")
    st.stop()

role = st.sidebar.radio("Login as", ["Student", "Teacher", "Register", "Admin"])

# === REGISTER ===
if role == "Register":
    st.subheader("🆕 Student Registration")
    name = st.text_input("Student Name")
    gmail = st.text_input("Gmail ID")
    cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
    password = st.text_input("Create Password", type="password")

    st.subheader("Pay ₹100 for Subscription")
    st.code(UPI_ID, language="text")

    if st.button("I have paid. Register me"):
        df = load_students()
        if gmail in df["Gmail ID"].values:
            st.error("Already registered.")
        else:
            new_row = {
                "Sr. No.": df.shape[0] + 1,
                "Student Name": name,
                "Gmail ID": gmail,
                "Class": cls,
                "Password": password,
                "Subscription Date": "",
                "Subscribed Till": (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime('%Y-%m-%d'),
                "Payment Confirmed": "No"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_students(df)
            st.success("Registered! Awaiting admin confirmation.")

# === STUDENT LOGIN ===
elif role == "Student":
    st.subheader("Student Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df = load_students()
        user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not user.empty:
            row = user.iloc[0]
            if row["Payment Confirmed"] == "Yes" and datetime.today() <= pd.to_datetime(row["Subscribed Till"]):
                st.session_state.user_name = row["Student Name"]
                st.session_state.user_role = "student"
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Payment not confirmed or subscription expired.")
        else:
            st.error("Invalid credentials")

# === TEACHER LOGIN ===
elif role == "Teacher":
    st.subheader("Teacher Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df = load_teachers()
        user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not user.empty:
            st.session_state.user_name = user.iloc[0]["Teacher Name"]
            st.session_state.user_role = "teacher"
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

# === ADMIN PANEL ===
elif role == "Admin":
    st.subheader("Admin Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login as Admin"):
        df = load_teachers()
        admin = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not admin.empty:
            st.success("Admin login successful")
            st.session_state["is_admin"] = True
            st.session_state["admin_df"] = load_students()
        else:
            st.error("Invalid credentials")

if st.session_state.get("is_admin", False):
    df = st.session_state["admin_df"]
    st.subheader("🟡 Pending Confirmations")
    pending = df[df["Payment Confirmed"] != "Yes"]
    for i, row in pending.iterrows():
        st.write(f"{row['Sr. No.']}. {row['Student Name']} ({row['Gmail ID']})")
        if st.button(f"✅ Confirm Payment: {row['Student Name']}", key=row['Gmail ID']):
            today = datetime.today().date()
            df.at[i, "Payment Confirmed"] = "Yes"
            df.at[i, "Subscription Date"] = today.strftime('%Y-%m-%d')
            df.at[i, "Subscribed Till"] = (today + timedelta(days=SUBSCRIPTION_DAYS)).strftime('%Y-%m-%d')
            save_students(df)
            st.session_state["admin_df"] = df
            st.success(f"Confirmed for {row['Student Name']}")
            st.rerun()

    st.subheader("📋 All Student Data")
    edited = st.data_editor(df, num_rows="dynamic", key="admin_table")
    if st.button("Save Changes"):
        edited["Subscribed Till"] = pd.to_datetime(edited["Subscribed Till"], errors="coerce").dt.strftime('%Y-%m-%d')
        save_students(edited.fillna("").astype(str))
        st.session_state["admin_df"] = edited
        st.success("Saved.")
        st.rerun()

# === DASHBOARDS ===
if st.session_state.user_name:
    st.sidebar.success(f"Welcome {st.session_state.user_name}")
    if st.session_state.user_role == "teacher":
        st.subheader("📤 Upload Homework")
        teacher = st.session_state.user_name
        subject = st.selectbox("📚 Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
        cls = st.selectbox("🏫 Class", [f"{i}th" for i in range(6,13)])
        date = st.date_input("📅 Homework Date", datetime.today())
        date_str = date.strftime('%Y-%m-%d')

        mode = st.radio("Upload Method", ["Upload File", "Write On-Screen"])

        if mode == "Upload File":
            file = st.file_uploader("📂 Choose File", type=["docx", "pdf", "xlsx", "jpg", "png"])
            if file and st.button("Upload"):
                path = f"{subject}_{date_str}_{file.name}"
                with open(path, "wb") as f:
                    f.write(file.read())
                link = upload_to_drive(path, FOLDER_ID, subject, date_str)
                save_homework_entry({
                    "Class": cls,
                    "Date": date_str,
                    "Subject": subject,
                    "File Name": file.name,
                    "Drive Link": link,
                    "Uploaded By": teacher
                })
                st.success("✅ Uploaded")
                st.write("🔗", link)

        else:
            content = st.text_area("📝 Write Homework Here")
            if content and st.button("Generate & Upload"):
                filename = f"{subject}_{date_str}_{teacher.replace(' ', '_')}.pdf"
                generate_pdf(content, filename)
                link = upload_to_drive(filename, FOLDER_ID, subject, date_str)
                save_homework_entry({
                    "Class": cls,
                    "Date": date_str,
                    "Subject": subject,
                    "File Name": filename,
                    "Drive Link": link,
                    "Uploaded By": teacher
                })
                st.success("✅ PDF uploaded")
                st.write("🔗", link)

    elif st.session_state.user_role == "student":
        df = load_students()
        user = df[df["Student Name"] == st.session_state.user_name].iloc[0]
        cls = user["Class"]
        date = st.date_input("Select Homework Date", datetime.today())
        st.subheader("📥 Upload Completed Notebook")
        notebook = st.file_uploader("Upload Image or PDF", type=["jpg", "png", "jpeg", "pdf"])
        if notebook:
            save_path = os.path.join(NOTEBOOK_DIR, f"{st.session_state.user_name}_{date}_{notebook.name}")
            with open(save_path, "wb") as f:
                f.write(notebook.read())
            st.success("Notebook uploaded.")