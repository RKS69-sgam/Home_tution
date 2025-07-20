# FINAL MERGED STREAMLIT CODE WITH RECEIPT GENERATION

import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt
from PIL import Image
import gspread
import json
import base64
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import plotly.express as px

# === CONFIG ===
st.set_page_config(layout="wide")
LOGO_PATH = "logo.png"
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
NOTEBOOK_DIR = "uploaded_notebooks"
HOMEWORK_FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe"
NOTEBOOKS_FOLDER_ID = "1diGm7ukz__yVze4JlH3F-oJ7GBsPJkHy"
RECEIPTS_FOLDER_ID = "1dlDauaPLZ-FQGzS2rIIyMnVjmUiBIAfr"

os.makedirs(NOTEBOOK_DIR, exist_ok=True)

# === GOOGLE AUTH ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
encoded = st.secrets["google_service"]["base64_credentials"]
decoded = base64.b64decode(encoded)
credentials_dict = json.loads(decoded)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)
drive_service = build("drive", "v3", credentials=credentials)

# === SHEETS ===
STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
homework_sheet = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1

# === UTILS ===
def load_students():
    return pd.DataFrame(STUDENT_SHEET.get_all_records())

def load_teachers():
    return pd.DataFrame(TEACHER_SHEET.get_all_records())

def save_students(df):
    df = df.fillna("").astype(str)
    STUDENT_SHEET.clear()
    STUDENT_SHEET.update([df.columns.values.tolist()] + df.values.tolist())

def upload_to_drive(path, folder_id, filename):
    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(path, resumable=True)
    file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()
    return f"https://drive.google.com/file/d/{file.get('id')}/view"

def generate_receipt(student_name, gmail, date, output_path):
    doc = Document()
    p = doc.add_paragraph()
    p.add_run("PRK HOME TUITION\n").bold = True
    p.add_run("Payment Receipt\n").bold = True
    doc.add_paragraph(f"Name: {student_name}")
    doc.add_paragraph(f"Gmail ID: {gmail}")
    doc.add_paragraph(f"Amount: ₹100")
    doc.add_paragraph(f"Date: {date}")
    doc.add_paragraph("Subscription valid for 30 days.")
    doc.save(output_path)

# === UI HEADER ===
st.sidebar.title("Login Menu")
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=160)
st.title("PRK Home Tuition Advance Classes")

# === SESSION ===
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.success("Logged out successfully.")
    st.stop()

# === LOGIN ===
role = st.sidebar.radio("Login as", ["Student", "Teacher", "Register", "Admin", "Principal"])

# === REGISTER ===
if role == "Register":
    st.subheader("New Student Registration")
    name = st.text_input("Student Name")
    gmail = st.text_input("Gmail ID")
    cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
    password = st.text_input("Create Password", type="password")
    st.code(UPI_ID, language="text")
    if st.button("I have paid. Register me"):
        df = load_students()
        if gmail in df["Gmail ID"].values:
            st.error("Already registered.")
        else:
            new_sr = df.shape[0] + 1
            till = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime('%Y-%m-%d')
            new_row = {
                "Sr. No.": new_sr,
                "Student Name": name,
                "Gmail ID": gmail,
                "Class": cls,
                "Password": password,
                "Subscription Date": "",
                "Subscribed Till": till,
                "Payment Confirmed": "No"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_students(df)
            st.success("Registered. Wait for admin to confirm payment.")

# === STUDENT LOGIN ===
elif role == "Student":
    st.subheader("Student Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df = load_students()
        user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not user.empty:
            sub_date = pd.to_datetime(user.iloc[0]["Subscribed Till"])
            if user.iloc[0]["Payment Confirmed"] == "Yes" and datetime.today() <= sub_date:
                st.session_state.user_name = user.iloc[0]["Student Name"]
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
            df_students = load_students()
            st.session_state["admin_df"] = df_students
            st.session_state["admin_logged_in"] = True
        else:
            st.error("Invalid credentials")

if st.session_state.get("admin_logged_in", False):
    df = st.session_state["admin_df"]
    pending = df[df["Payment Confirmed"] != "Yes"]
    st.subheader("Pending Confirmations")
    for i, row in pending.iterrows():
        st.write(f"{row['Sr. No.']} - {row['Student Name']} ({row['Gmail ID']})")
        if st.button(f"Confirm {row['Student Name']}", key=row['Gmail ID']):
            today = datetime.today().date()
            df.at[i, "Payment Confirmed"] = "Yes"
            df.at[i, "Subscription Date"] = today.strftime('%Y-%m-%d')
            df.at[i, "Subscribed Till"] = (today + timedelta(days=SUBSCRIPTION_DAYS)).strftime('%Y-%m-%d')
            save_students(df)
            st.session_state["admin_df"] = df
            # Generate receipt
            receipt_name = f"{row['Student Name']}_{today}.docx"
            receipt_path = f"/tmp/{receipt_name}"
            generate_receipt(row["Student Name"], row["Gmail ID"], today, receipt_path)
            link = upload_to_drive(receipt_path, RECEIPTS_FOLDER_ID, receipt_name)
            st.success(f"Payment confirmed. Receipt: [View]({link})")
            st.rerun()

# === PRINCIPAL PANEL ===
elif role == "Principal":
    st.subheader("Principal Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login as Principal"):
        df = load_teachers()
        principal = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not principal.empty:
            st.session_state["is_principal_logged_in"] = True
            st.success("Principal login successful")

if st.session_state.get("is_principal_logged_in", False):
    st.title("📊 Principal Dashboard")
    df = pd.DataFrame(homework_sheet.get_all_records())
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
        st.plotly_chart(px.bar(df, x="Uploaded By", color="Subject", title="Homework per Teacher"))
        trend = df.groupby(["Date", "Subject"]).size().reset_index(name="Count")
        st.plotly_chart(px.line(trend, x="Date", y="Count", color="Subject", markers=True))

# === STUDENT DASHBOARD ===
if st.session_state.user_name and st.session_state.user_role == "student":
    st.sidebar.success(f"Welcome {st.session_state.user_name}")
    df = load_students()
    user = df[df["Student Name"] == st.session_state.user_name].iloc[0]
    cls = user["Class"]
    date = st.date_input("Select Homework Date", datetime.today())
    df_files = pd.DataFrame(homework_sheet.get_all_records())
    df_files = df_files[(df_files["Class"] == cls) & (df_files["Date"] == str(date))]

    if not df_files.empty:
        for _, row in df_files.iterrows():
            st.markdown(f"📘 **{row['Subject']}** → [📥 {row['File Name']}]({row['Drive Link']})")
    else:
        st.warning("No homework for this date.")

    st.subheader("Upload Completed Notebook")
    notebook = st.file_uploader("Upload Notebook", type=["jpg", "jpeg", "png", "pdf"])
    if notebook:
        fname = f"{st.session_state.user_name}_{date}_{notebook.name}"
        path = os.path.join(NOTEBOOK_DIR, fname)
        with open(path, "wb") as f:
            f.write(notebook.read())
        upload_to_drive(path, NOTEBOOKS_FOLDER_ID, fname)
        st.success("Notebook uploaded.")

# === TEACHER DASHBOARD ===
if st.session_state.user_name and st.session_state.user_role == "teacher":
    st.sidebar.success(f"Welcome {st.session_state.user_name}")
    st.subheader("Upload Homework")
    subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance"])
    cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
    date = st.date_input("Homework Date", datetime.today())
    file = st.file_uploader("Upload Homework", type=["docx", "pdf", "jpg", "png", "xlsx"])

    if st.button("Upload File"):
        if file:
            fname = f"{subject}_{cls}_{date}_{file.name}"
            path = f"/tmp/{fname}"
            with open(path, "wb") as f:
                f.write(file.read())
            link = upload_to_drive(path, HOMEWORK_FOLDER_ID, fname)
            homework_sheet.append_row([cls, str(date), fname, link, st.session_state.user_name, subject])
            st.success(f"Uploaded: [View File]({link})")
        else:
            st.warning("Upload required.")