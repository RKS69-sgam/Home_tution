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

# === GOOGLE AUTH ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
encoded = st.secrets["google_service"]["base64_credentials"]
decoded = base64.b64decode(encoded)
credentials_dict = json.loads(decoded)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)

# === CONFIG ===
LOGO_PATH = "logo.png"
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
HOMEWORK_DIR = "uploaded_homeworks"
NOTEBOOK_DIR = "uploaded_notebooks"

STUDENT_SHEET = client.open_by_key("10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno").sheet1
TEACHER_SHEET = client.open_by_key("1BRyQ5-Hv5Qr8ZnDzkj1awoxLjbLh3ubsWzpXskFL4h8").sheet1

os.makedirs(HOMEWORK_DIR, exist_ok=True)
os.makedirs(NOTEBOOK_DIR, exist_ok=True)

# === UTILS ===
def load_students():
    return pd.DataFrame(STUDENT_SHEET.get_all_records())

def load_teachers():
    return pd.DataFrame(TEACHER_SHEET.get_all_records())

def save_students(df):
    df = df.fillna("").astype(str)
    STUDENT_SHEET.clear()
    STUDENT_SHEET.update([df.columns.values.tolist()] + df.values.tolist())

def insert_heading_and_placeholders(path_in, path_out):
    doc = Document(path_in)
    new_doc = Document()
    h1 = new_doc.add_paragraph("विद्या ददाति विनयं\nPRK Home Tuition Advance Classes")
    h1.alignment = 1
    h1.runs[0].bold = True
    h1.runs[0].font.size = Pt(16)
    new_doc.add_paragraph("[StudentName]")
    new_doc.add_paragraph("[Class]")
    new_doc.add_paragraph("[HomeworkDate]")
    for para in doc.paragraphs:
        new_doc.add_paragraph(para.text)
    new_doc.save(path_out)

def replace_placeholders(path_in, path_out, name, cls, date_str):
    doc = Document(path_in)
    for p in doc.paragraphs:
        for run in p.runs:
            run.text = run.text.replace("[StudentName]", f"Student Name: {name}")
            run.text = run.text.replace("[Class]", f"STD - {cls}")
            run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(path_out)

# === PAGE CONFIG ===
st.set_page_config(layout="wide")
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
role = st.sidebar.radio("Login as", ["Student", "Teacher", "Register", "Admin"])

# === REGISTER ===
if role == "Register":
    st.subheader("New Student Registration")
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
            st.stop()
        else:
            st.error("Invalid credentials")

# === Admin panel===
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
            if st.button(f"Confirm Payment for {row['Student Name']}", key="confirm_"+row['Gmail ID']):
                today = datetime.today().date()
                df.at[i, "Payment Confirmed"] = "Yes"
                df.at[i, "Subscription Date"] = today.strftime('%Y-%m-%d')
                df.at[i, "Subscribed Till"] = (today + timedelta(days=SUBSCRIPTION_DAYS)).strftime('%Y-%m-%d')
                save_students(df)
                st.session_state["admin_df"] = df
                st.success(f"Payment confirmed for {row['Student Name']} till {(today + timedelta(days=SUBSCRIPTION_DAYS)).strftime('%Y-%m-%d')}")
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

# === DASHBOARDS ===
if st.session_state.user_name:
    st.sidebar.success(f"Welcome {st.session_state.user_name}")
    if st.session_state.user_role == "teacher":
        st.subheader("Upload Homework")
        cls = st.selectbox("Select Class", [f"{i}th" for i in range(6,13)])
        date = st.date_input("Homework Date", datetime.today())
        file = st.file_uploader("Upload Word File", type=["docx"])
        if file and st.button("Upload Homework"):
            temp_path = os.path.join(HOMEWORK_DIR, f"temp_{cls}_{date}.docx")
            final_path = os.path.join(HOMEWORK_DIR, f"{cls}_{date}.docx")
            with open(temp_path, "wb") as f:
                f.write(file.read())
            insert_heading_and_placeholders(temp_path, final_path)
            st.success("Homework uploaded.")
    elif st.session_state.user_role == "student":
        df = load_students()
        user = df[df["Student Name"] == st.session_state.user_name].iloc[0]
        cls = user["Class"]
        date = st.date_input("Select Homework Date", datetime.today())
        file_path = os.path.join(HOMEWORK_DIR, f"{cls}_{date}.docx")
        output_path = os.path.join(HOMEWORK_DIR, f"{st.session_state.user_name}_{date}.docx")
        if os.path.exists(file_path):
            replace_placeholders(file_path, output_path, st.session_state.user_name, cls, str(date))
            with open(output_path, "rb") as f:
                st.download_button("Download Homework", f, file_name=os.path.basename(output_path))
        else:
            st.warning("Homework not available for selected date.")

        st.subheader("Upload Completed Notebook")
        notebook = st.file_uploader("Upload your notebook", type=["jpg", "jpeg", "png", "pdf"])
        if notebook:
            save_path = os.path.join(NOTEBOOK_DIR, f"{st.session_state.user_name}_{date}_{notebook.name}")
            with open(save_path, "wb") as f:
                f.write(notebook.read())
            st.success("Notebook uploaded successfully.")