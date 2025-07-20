import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt
from fpdf import FPDF
from PIL import Image
import gspread
import json
import base64
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import plotly.express as px

# === CONFIGURATION ===
st.set_page_config(layout="wide")
LOGO_PATH = "logo.png"
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
NOTEBOOK_DIR = "uploaded_notebooks"
DRIVE_FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe"

os.makedirs(NOTEBOOK_DIR, exist_ok=True)

# === GOOGLE AUTH ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
encoded = st.secrets["google_service"]["base64_credentials"]
decoded = base64.b64decode(encoded)
credentials_dict = json.loads(decoded)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)

# Google Sheets & Drive Setup
STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1
homework_sheet = client.open_by_key("1fU_oJWR8GbOCX_0TRu2qiXIwQ19pYy__ezXPsRH61qI").sheet1

drive_service = build("drive", "v3", credentials=credentials)

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
    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(path, resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")
    return f"https://drive.google.com/file/d/{file_id}/view"

def insert_heading_and_placeholders(doc_lines, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, "विद्या ददाति विनयं", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, "PRK Home Tuition Advance Classes", ln=True, align='C')
    pdf.ln(10)
    for line in doc_lines:
        pdf.multi_cell(0, 8, line)
    pdf.output(output_path)

# === HEADER ===
st.sidebar.title("Login Menu")
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=160)
st.title("PRK Home Tuition Advance Classes")

# === SESSION STATE ===
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.success("Logged out successfully.")
    st.stop()

# === LOGIN OPTIONS ===
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
            new_row = {
                "Sr. No.": new_sr,
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
            st.success("Registered successfully. Wait for admin to confirm payment.")

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
    st.subheader("Admin Panel")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login as Admin"):
        df_teacher = load_teachers()
        admin_user = df_teacher[(df_teacher["Gmail ID"] == email) & (df_teacher["Password"] == password)]
        if not admin_user.empty:
            st.success("Admin login successful")
            df = load_students()
            st.session_state["is_admin_logged_in"] = True
            st.session_state["admin_df"] = df
        else:
            st.error("Invalid Admin credentials")

if st.session_state.get("is_admin_logged_in", False):
    df = st.session_state.get("admin_df", load_students())
    pending = df[df["Payment Confirmed"] != "Yes"]
    if not pending.empty:
        st.subheader("Pending Confirmations")
        for i, row in pending.iterrows():
            st.write(f"{row['Sr. No.']}. {row['Student Name']} ({row['Gmail ID']})")
            if st.button(f"Confirm Payment for {row['Student Name']}", key=row['Gmail ID']):
                today = datetime.today().date()
                df.at[i, "Payment Confirmed"] = "Yes"
                df.at[i, "Subscription Date"] = today.strftime('%Y-%m-%d')
                df.at[i, "Subscribed Till"] = (today + timedelta(days=SUBSCRIPTION_DAYS)).strftime('%Y-%m-%d')
                save_students(df)
                st.session_state["admin_df"] = df
                st.success(f"Payment confirmed for {row['Student Name']}")
                st.rerun()
    else:
        st.info("No pending confirmations.")

    st.subheader("All Students")
    editable_df = df.copy()
    editable_df["Subscribed Till"] = editable_df["Subscribed Till"].astype(str)
    edited_df = st.data_editor(editable_df, num_rows="dynamic", key="admin_table")
    if st.button("Save Changes"):
        edited_df["Subscribed Till"] = pd.to_datetime(edited_df["Subscribed Till"], errors='coerce').dt.strftime('%Y-%m-%d')
        save_students(edited_df.fillna("").astype(str))
        st.session_state["admin_df"] = edited_df
        st.success("Student data updated successfully.")
        st.rerun()

# === PRINCIPAL PANEL ===
elif role == "Principal":
    st.subheader("Principal Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login as Principal"):
        df_teacher = load_teachers()
        principal_user = df_teacher[(df_teacher["Gmail ID"] == email) & (df_teacher["Password"] == password)]
        if not principal_user.empty:
            st.success("Principal login successful")
            st.session_state["is_principal_logged_in"] = True
        else:
            st.error("Invalid Principal credentials")

if st.session_state.get("is_principal_logged_in", False):
    st.sidebar.success("Welcome Principal")
    st.title("📊 Overall Progress Dashboard")
    hw_df = pd.DataFrame(homework_sheet.get_all_records())
    if not hw_df.empty:
        hw_df["Date"] = pd.to_datetime(hw_df["Date"], errors='coerce')
        fig1 = px.bar(hw_df, x="Uploaded By", color="Subject", title="Homework Uploads per Teacher")
        st.plotly_chart(fig1)
        trend = hw_df.groupby(["Date", "Subject"]).size().reset_index(name="Uploads")
        fig2 = px.line(trend, x="Date", y="Uploads", color="Subject", markers=True, title="Upload Trend per Subject")
        st.plotly_chart(fig2)
    else:
        st.info("No homework records found.")

    st.header("📒 Student Notebook Upload Summary")
    upload_stats = {}
    for f in os.listdir(NOTEBOOK_DIR):
        try:
            name, date, _ = f.split("_", 2)
            key = (name, date)
            upload_stats[key] = upload_stats.get(key, 0) + 1
        except:
            continue
    if upload_stats:
        records = [{"Student": k[0], "Date": k[1], "Uploads": v} for k, v in upload_stats.items()]
        notebook_df = pd.DataFrame(records)
        notebook_df["Date"] = pd.to_datetime(notebook_df["Date"], errors='coerce')
        fig3 = px.bar(notebook_df, x="Student", y="Uploads", color="Date", title="Notebook Uploads per Student")
        st.plotly_chart(fig3)
        fig4 = px.line(notebook_df, x="Date", y="Uploads", color="Student", title="Notebook Upload Trend", markers=True)
        st.plotly_chart(fig4)
    else:
        st.info("No student notebook uploads yet.")

# === DASHBOARDS ===
if st.session_state.user_name:
    st.sidebar.success(f"Welcome {st.session_state.user_name}")
    if st.session_state.user_role == "teacher":
        st.subheader("Upload Homework")
        subject = st.selectbox("Select Subject", ["Hindi", "English", "Math", "Science", "SST", "Computer", "GK", "Advance Classes"])
        cls = st.selectbox("Select Class", [f"{i}th" for i in range(6,13)])
        date = st.date_input("Homework Date", datetime.today())
        file = st.file_uploader("Upload Homework File", type=["docx", "pdf", "jpg", "png", "xlsx"])
        doc_lines = st.text_area("OR Create Homework On Screen (each line will be a paragraph)").split("\n")

        if st.button("Upload Homework"):
            final_file_name = f"{subject}_{cls}_{date}.pdf"
            temp_path = f"/tmp/{final_file_name}"

            if any(doc_lines) and not file:
                insert_heading_and_placeholders(doc_lines, temp_path)
            elif file:
                with open(temp_path, "wb") as f:
                    f.write(file.read())
            else:
                st.warning("Please upload or type the homework.")
                st.stop()

            link = upload_to_drive(temp_path, DRIVE_FOLDER_ID, final_file_name)
            homework_sheet.append_row([cls, str(date), final_file_name, link, st.session_state.user_name])
            st.success(f"Homework uploaded and saved. [View File]({link})")

    elif st.session_state.user_role == "student":
        df = load_students()
        user = df[df["Student Name"] == st.session_state.user_name].iloc[0]
        cls = user["Class"]
        date = st.date_input("Select Homework Date", datetime.today())
        files = pd.DataFrame(homework_sheet.get_all_records())
        files = files[(files["Class"] == cls) & (files["Date"] == str(date))]

        if not files.empty:
            for i, row in files.iterrows():
                st.markdown(f"📘 **{row['File Name']}**  →  [📥 Download File]({row['Drive Link']})")
        else:
            st.warning("No homework available for selected date.")

        st.subheader("Upload Completed Notebook")
        notebook = st.file_uploader("Upload Notebook", type=["jpg", "jpeg", "png", "pdf"])
        if notebook:
            filename = f"{st.session_state.user_name}_{date}_{notebook.name}"
            with open(os.path.join(NOTEBOOK_DIR, filename), "wb") as f:
                f.write(notebook.read())
            st.success("Notebook uploaded successfully.")