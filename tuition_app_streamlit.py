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
import mimetypes
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import plotly.express as px

# === CONFIG ===
st.set_page_config(layout="wide")
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
LOGO_PATH = "logo.png"

HOMEWORK_FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe"
NOTEBOOK_FOLDER_ID = "1diGm7ukz__yVze4JlH3F-oJ7GBsPJkHy"
RECEIPT_FOLDER_ID = "1dlDauaPLZ-FQGzS2rIIyMnVjmUiBIAfr"

# === AUTH ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
decoded = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
credentials_dict = json.loads(decoded)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)
drive_service = build("drive", "v3", credentials=credentials)

# === SHEETS ===
STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
HOMEWORK_SHEET = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1

# === UTILS ===
def upload_to_drive(path, folder_id, filename):
    mime_type, _ = mimetypes.guess_type(path)
    media = MediaFileUpload(path, mimetype=mime_type, resumable=True)
    metadata = {"name": filename, "parents": [folder_id]}
    file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()
    return f"https://drive.google.com/file/d/{file.get('id')}/view"

def create_receipt(student_name, gmail, cls, subs_date, till_date):
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

def load_students():
    return pd.DataFrame(STUDENT_SHEET.get_all_records())

def save_students(df):
    df = df.fillna("").astype(str)
    STUDENT_SHEET.clear()
    STUDENT_SHEET.update([df.columns.values.tolist()] + df.values.tolist())

def load_teachers():
    return pd.DataFrame(TEACHER_SHEET.get_all_records())

# === SESSION ===
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.experimental_rerun()

# === HEADER ===
st.sidebar.title("Login")
st.title("🏫 PRK Home Tuition App")

# === LOGIN MENU ===
role = st.sidebar.radio("Login As", ["Student", "Teacher", "Register", "Admin", "Principal"])

# === REGISTER ===
if role == "Register":
    st.subheader("Student Registration")
    name = st.text_input("Name")
    gmail = st.text_input("Gmail ID")
    cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
    pwd = st.text_input("Password", type="password")
    st.code(UPI_ID, language="text")
    if st.button("Register (After Payment)"):
        df = load_students()
        if gmail in df["Gmail ID"].values:
            st.error("Already registered")
        else:
            sr = df.shape[0] + 1
            till = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime("%Y-%m-%d")
            new_row = {
                "Sr. No.": sr, "Student Name": name, "Gmail ID": gmail,
                "Class": cls, "Password": pwd,
                "Subscription Date": "", "Subscribed Till": till,
                "Payment Confirmed": "No"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_students(df)
            st.success("Registered. Wait for admin to confirm.")

# === STUDENT LOGIN ===
elif role == "Student":
    st.subheader("Student Login")
    gmail = st.text_input("Gmail ID")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        df = load_students()
        user = df[(df["Gmail ID"] == gmail) & (df["Password"] == pwd)]
        if not user.empty:
            row = user.iloc[0]
            if row["Payment Confirmed"] == "Yes" and datetime.today() <= pd.to_datetime(row["Subscribed Till"]):
                st.session_state.user_name = row["Student Name"]
                st.session_state.user_role = "student"
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Subscription invalid or not confirmed.")
        else:
            st.error("Invalid credentials")

# === TEACHER LOGIN ===
elif role == "Teacher":
    st.subheader("Teacher Login")
    gmail = st.text_input("Gmail ID")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        df = load_teachers()
        user = df[(df["Gmail ID"] == gmail) & (df["Password"] == pwd)]
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
    gmail = st.text_input("Admin Gmail")
    pwd = st.text_input("Password", type="password")
    if st.button("Login as Admin"):
        df = load_teachers()
        user = df[(df["Gmail ID"] == gmail) & (df["Password"] == pwd)]
        if not user.empty:
            st.session_state["admin"] = True
            st.success("Logged in as Admin")
            df = load_students()
            for i, row in df[df["Payment Confirmed"] != "Yes"].iterrows():
                st.write(f"{row['Student Name']} ({row['Gmail ID']})")
                if st.button(f"✅ Confirm Payment - {row['Student Name']}", key=row["Gmail ID"]):
                    today = datetime.today().strftime("%Y-%m-%d")
                    till = (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).strftime("%Y-%m-%d")
                    df.at[i, "Subscription Date"] = today
                    df.at[i, "Subscribed Till"] = till
                    df.at[i, "Payment Confirmed"] = "Yes"
                    receipt = create_receipt(row["Student Name"], row["Gmail ID"], row["Class"], today, till)
                    st.success(f"Payment confirmed. Receipt generated: [🔗 View]({receipt})")
                    save_students(df)
                    st.rerun()

# === PRINCIPAL PANEL ===
elif role == "Principal":
    st.subheader("Principal Login")
    gmail = st.text_input("Principal Gmail")
    pwd = st.text_input("Password", type="password")
    if st.button("Login as Principal"):
        df = load_teachers()
        user = df[(df["Gmail ID"] == gmail) & (df["Password"] == pwd)]
        if not user.empty:
            st.session_state["principal"] = True
            st.success("Logged in as Principal")

if st.session_state.user_name and st.session_state.user_role == "teacher":
    st.subheader("Upload Homework")
    subject = st.selectbox("Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
    cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
    date = st.date_input("Date", datetime.today())
    file = st.file_uploader("Upload Homework File", type=["docx", "pdf", "jpg", "png"])
    if file and st.button("Upload"):
        fname = f"{subject}_{cls}_{date}_{file.name}"
        path = f"/tmp/{fname}"
        with open(path, "wb") as f:
            f.write(file.read())
        link = upload_to_drive(path, HOMEWORK_FOLDER_ID, fname)
        HOMEWORK_SHEET.append_row([cls, str(date), fname, link, st.session_state.user_name, subject])
        st.success(f"Uploaded: [📎 {fname}]({link})")

if st.session_state.user_name and st.session_state.user_role == "student":
    st.subheader("Your Homework")
    df = load_students()
    user = df[df["Student Name"] == st.session_state.user_name].iloc[0]
    cls = user["Class"]
    date = st.date_input("Select Date", datetime.today())
    data = pd.DataFrame(HOMEWORK_SHEET.get_all_records())
    data = data[(data["Class"] == cls) & (data["Date"] == str(date))]
    if not data.empty:
        for _, row in data.iterrows():
            st.markdown(f"📘 **{row['Subject']}** → [📥 {row['File Name']}]({row['Drive Link']})")
    else:
        st.warning("No homework found.")

    st.subheader("Upload Completed Notebook")
    nb = st.file_uploader("Upload Notebook", type=["pdf", "jpg", "png"])
    if nb:
        nbname = f"{st.session_state.user_name}_{date}_{nb.name}"
        path = f"/tmp/{nbname}"
        with open(path, "wb") as f:
            f.write(nb.read())
        link = upload_to_drive(path, NOTEBOOK_FOLDER_ID, nbname)
        st.success(f"Notebook uploaded: [📎 {nbname}]({link})")

if st.session_state.get("principal", False):
    st.subheader("📊 Homework Upload Dashboard")
    df = pd.DataFrame(HOMEWORK_SHEET.get_all_records())
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        fig1 = px.bar(df, x="Uploaded By", color="Subject", title="Uploads per Teacher")
        st.plotly_chart(fig1)
        trend = df.groupby(["Date", "Subject"]).size().reset_index(name="Count")
        fig2 = px.line(trend, x="Date", y="Count", color="Subject", markers=True, title="Upload Trend")
        st.plotly_chart(fig2)
