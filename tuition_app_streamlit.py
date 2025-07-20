# === PRK Home Tuition Full System ===
import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.service_account import ServiceAccountCredentials
import json, base64, os

# === CONFIG ===
FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe"
SHEET_ID = "1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI"
SHEET_NAME = "Sheet1"
SUBJECTS = ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"]
CLASSES = [f"{i}th" for i in range(6, 13)]

# === GOOGLE AUTH ===
encoded = st.secrets["google_service"]["base64_credentials"]
creds_json = json.loads(base64.b64decode(encoded))
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
drive_service = build('drive', 'v3', credentials=creds)

# === UTILS ===
def upload_to_drive(file_path, folder_id, filename):
    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = file["id"]
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

def insert_drive_folder(path_list, base_folder_id):
    parent_id = base_folder_id
    for folder_name in path_list:
        query = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res = drive_service.files().list(q=query, fields="files(id)").execute()
        files = res.get("files", [])
        if files:
            parent_id = files[0]["id"]
        else:
            folder_metadata = {"name": folder_name, "parents": [parent_id], "mimeType": "application/vnd.google-apps.folder"}
            new_folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
            parent_id = new_folder["id"]
    return parent_id

def create_pdf(text, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, line)
    pdf.output(output_path)

def add_to_sheet(cls, subject, date, filename, drive_link, uploaded_by):
    sheet.append_row([cls, subject, str(date), filename, drive_link, uploaded_by])

def get_homework_entries(cls, student_name):
    rows = sheet.get_all_records()
    return [r for r in rows if r["Class"] == cls]

# === PAGE CONFIG ===
st.set_page_config(layout="wide")
st.title("📚 PRK Home Tuition System")

# === SIDEBAR LOGIN ===
role = st.sidebar.radio("Login As", ["Student", "Teacher", "Principal"])
name = st.sidebar.text_input("Your Name")

if not name:
    st.stop()

# === STUDENT PANEL ===
if role == "Student":
    st.header(f"🎓 Welcome, {name}")
    student_class = st.selectbox("Select Class", CLASSES, key="stu_cls")
    today = st.date_input("Select Homework Date", datetime.today(), key="stu_date")

    st.subheader("📥 Download Homework (Uploaded)")
    entries = get_homework_entries(student_class, name)
    found = False
    for entry in entries:
        if entry["Date"] == str(today):
            st.markdown(f"✅ **{entry['Subject']}**: [{entry['File Name']}]({entry['Drive Link']})")
            found = True
    if not found:
        st.info("Homework not found for selected date.")

    st.subheader("📤 Upload Completed Notebook")
    subject = st.selectbox("Subject", SUBJECTS, key="stu_subj")
    notebook = st.file_uploader("Upload File", type=["jpg", "jpeg", "png", "pdf"])
    if notebook and st.button("Upload Notebook"):
        folder_path = ["Notebook", student_class, subject, str(today)]
        folder_id = insert_drive_folder(folder_path, FOLDER_ID)
        save_path = f"/tmp/{name}_{subject}_{today}_{notebook.name}"
        with open(save_path, "wb") as f:
            f.write(notebook.read())
        link = upload_to_drive(save_path, folder_id, notebook.name)
        st.success(f"Uploaded notebook: [Open]({link})")

# === TEACHER PANEL ===
elif role == "Teacher":
    st.header(f"👨‍🏫 Welcome, {name}")
    tab1, tab2 = st.tabs(["📁 Upload File", "✍️ Type Homework"])

    with tab1:
        st.subheader("Upload Homework File")
        cls = st.selectbox("Class", CLASSES, key="file_cls")
        subject = st.selectbox("Subject", SUBJECTS, key="file_subj")
        date = st.date_input("Homework Date", datetime.today(), key="file_date")
        file = st.file_uploader("Upload Word, PDF, Image", type=["docx", "pdf", "jpg", "png"])

        if file and st.button("Upload Homework"):
            folder_path = ["Homework", cls, subject, str(date)]
            folder_id = insert_drive_folder(folder_path, FOLDER_ID)
            temp_path = f"/tmp/{file.name}"
            with open(temp_path, "wb") as f:
                f.write(file.read())
            link = upload_to_drive(temp_path, folder_id, file.name)
            add_to_sheet(cls, subject, date, file.name, link, name)
            st.success(f"✅ Uploaded: [Open File]({link})")

    with tab2:
        st.subheader("✍️ Type Homework & Save as PDF")
        cls2 = st.selectbox("Class", CLASSES, key="type_cls")
        subject2 = st.selectbox("Subject", SUBJECTS, key="type_subj")
        date2 = st.date_input("Homework Date", datetime.today(), key="type_date")
        text = st.text_area("Type Homework Content", height=300)

        if st.button("Save as PDF & Upload"):
            file_name = f"{cls2}_{subject2}_{date2}.pdf"
            temp_path = f"/tmp/{file_name}"
            create_pdf(text, temp_path)
            folder_path = ["Homework", cls2, subject2, str(date2)]
            folder_id = insert_drive_folder(folder_path, FOLDER_ID)
            link = upload_to_drive(temp_path, folder_id, file_name)
            add_to_sheet(cls2, subject2, date2, file_name, link, name)
            st.success(f"📄 PDF saved and uploaded: [Open PDF]({link})")

# === PRINCIPAL PANEL ===
elif role == "Principal":
    st.header(f"🎓 Principal Dashboard - {name}")
    df = pd.DataFrame(sheet.get_all_records())
    st.subheader("📊 Homework Upload History")
    st.dataframe(df)

    st.subheader("📈 Upload Count by Teacher")
    chart_df = df["Uploaded By"].value_counts().reset_index()
    chart_df.columns = ["Teacher", "Uploads"]
    st.bar_chart(chart_df.set_index("Teacher"))

    st.subheader("📈 Subject-Wise Upload Count")
    subj_chart = df["Subject"].value_counts().reset_index()
    subj_chart.columns = ["Subject", "Count"]
    st.bar_chart(subj_chart.set_index("Subject"))