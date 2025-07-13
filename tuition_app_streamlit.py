import streamlit as st
import pandas as pd
import os
from docx import Document
from docx.shared import Pt
from datetime import datetime
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
HOMEWORK_DIR = "uploaded_homeworks"
NOTEBOOK_DIR = "uploaded_notebooks"
os.makedirs(HOMEWORK_DIR, exist_ok=True)
os.makedirs(NOTEBOOK_DIR, exist_ok=True)

# Load Excel files
@st.cache_data
def load_students():
    return pd.read_excel(STUDENT_MASTER)

@st.cache_data
def load_teachers():
    return pd.read_excel(TEACHER_MASTER)

# Insert header & placeholders
def insert_heading_and_placeholders(path_in, path_out):
    doc = Document(path_in)
    new_doc = Document()

    h1 = new_doc.add_paragraph("EXCELLENT PUBLIC SCHOOL")
    h1.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    h1.runs[0].bold = True
    h1.runs[0].font.size = Pt(16)

    h2 = new_doc.add_paragraph("Barainiya, Bargawan Distt. Singrauli (MP)")
    h2.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    h3 = new_doc.add_paragraph("Advance Classes Daily Homework")
    h3.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    h3.runs[0].bold = True
    h3.runs[0].italic = True

    new_doc.add_paragraph("[StudentName]")
    new_doc.add_paragraph("[Class]")
    new_doc.add_paragraph("[HomeworkDate]")

    for para in doc.paragraphs:
        new_doc.add_paragraph(para.text)

    new_doc.save(path_out)

# Replace placeholders
def replace_placeholders(doc_path, save_path, student_name, student_class, date_str):
    doc = Document(doc_path)
    for para in doc.paragraphs:
        for run in para.runs:
            run.text = run.text.replace("[StudentName]", f"Student Name: {student_name}")
            run.text = run.text.replace("[Class]", f"STD - {student_class}")
            run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(save_path)

# Sidebar Logout
def sidebar_logout():
    with st.sidebar:
        st.title("Menu")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

# Session init
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# Role Selection
st.title("EXCELLENT PUBLIC SCHOOL - Tuition App")
role = st.radio("Login as", ["Student", "Teacher"])

# Login
if st.session_state.user_role is None:
    st.subheader(f"{role} Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if role == "Student":
            df = load_students()
            user = df[df["Gmail ID"] == email]
            if not user.empty and user.iloc[0]["Password"] == password:
                st.session_state.user_role = "student"
                st.session_state.user_name = user.iloc[0]["Student Name"]
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")
        else:
            df = load_teachers()
            user = df[df["Gmail ID"] == email]
            if not user.empty and user.iloc[0]["Password"] == password:
                st.session_state.user_role = "teacher"
                st.session_state.user_name = user.iloc[0]["Teacher Name"]
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

# Teacher Panel
elif st.session_state.user_role == "teacher":
    sidebar_logout()
    st.markdown(f"### Welcome, {st.session_state.user_name}")
    st.subheader("Upload Homework")

    cls = st.selectbox("Select Class", [f"{i}th" for i in range(6, 13)])
    hw_date = st.date_input("Homework Date", datetime.today())
    uploaded = st.file_uploader("Upload Word File", type=["docx"])

    if uploaded and st.button("Upload Homework"):
        file_name = f"{cls}_{hw_date}.docx"
        file_path = os.path.join(HOMEWORK_DIR, file_name)
        temp_path = os.path.join(HOMEWORK_DIR, f"temp_{file_name}")
        with open(temp_path, "wb") as f:
            f.write(uploaded.read())
        insert_heading_and_placeholders(temp_path, file_path)
        st.success(f"Uploaded: {file_name}")

# Student Panel
elif st.session_state.user_role == "student":
    sidebar_logout()
    st.markdown(f"### Welcome, {st.session_state.user_name}")
    df = load_students()
    row = df[df["Student Name"] == st.session_state.user_name].iloc[0]
    student_class = row["Class"]
    selected_date = st.date_input("Select Homework Date")
    file_name = f"{student_class}_{selected_date}.docx"
    download_path = f"{st.session_state.user_name}_{selected_date}.docx"
    full_path = os.path.join(HOMEWORK_DIR, file_name)
    out_path = os.path.join(HOMEWORK_DIR, download_path)

    if os.path.exists(full_path):
        replace_placeholders(full_path, out_path, st.session_state.user_name, student_class, str(selected_date))
        with open(out_path, "rb") as f:
            st.download_button("Download Homework", f, file_name=download_path)
    else:
        st.warning("Homework not available yet.")

    st.subheader("Upload Completed Notebook")
    uploaded_hw = st.file_uploader("Upload Your Notebook (Image/PDF)", type=["pdf", "png", "jpg", "jpeg"])
    if uploaded_hw and st.button("Submit Notebook"):
        notebook_path = os.path.join(NOTEBOOK_DIR, f"{st.session_state.user_name}_{selected_date}.{uploaded_hw.name.split('.')[-1]}")
        with open(notebook_path, "wb") as f:
            f.write(uploaded_hw.read())
        st.success("Notebook uploaded successfully.")