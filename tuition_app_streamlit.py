
import streamlit as st
import pandas as pd
from docx import Document
from datetime import datetime
import os
import shutil

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
HOMEWORK_DIR = "uploaded_homeworks"
os.makedirs(HOMEWORK_DIR, exist_ok=True)

# Utility functions
@st.cache_data
def load_students():
    return pd.read_excel(STUDENT_MASTER)

@st.cache_data
def load_teachers():
    return pd.read_excel(TEACHER_MASTER)

def replace_placeholders_in_docx(path_in, path_out, student_name, student_class, date_str):
    doc = Document(path_in)

    for p in doc.paragraphs:
        for run in p.runs:
            if "[StudentName]" in run.text:
                run.text = run.text.replace("[StudentName]", f"Student Name: {student_name}")
            if "[Class]" in run.text:
                run.text = run.text.replace("[Class]", f"STD - {student_class}")
            if "[HomeworkDate]" in run.text:
                run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(path_out)

def insert_heading_and_placeholders(path_in, path_out):
    doc = Document(path_in)
    new_doc = Document()

    # Heading
    h1 = new_doc.add_paragraph("EXCELLENT PUBLIC SCHOOL")
    h1.alignment = 1
    h1.runs[0].bold = True
    h1.runs[0].font.size = Pt(16)

    h2 = new_doc.add_paragraph("Barainiya, Bargawan Distt. Singrauli (MP)")
    h2.alignment = 1

    h3 = new_doc.add_paragraph("Advance Classes Daily Homework")
    h3.alignment = 1
    h3.runs[0].bold = True
    h3.runs[0].italic = True

    new_doc.add_paragraph("[StudentName]")
    new_doc.add_paragraph("[Class]")
    new_doc.add_paragraph("[HomeworkDate]")

    for para in doc.paragraphs:
        new_doc.add_paragraph(para.text)

    new_doc.save(path_out)

# Login Page
st.title("EXCELLENT PUBLIC SCHOOL - Tuition App")
role = st.radio("Login as", ["Student", "Teacher"])

if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = ""

if role == "Student":
    st.subheader("Student Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df_students = load_students()
        user = df_students[df_students["Gmail ID"] == email]
        if not user.empty and user.iloc[0]["Password"] == password:
            st.session_state.user_name = user.iloc[0]["Student Name"]
            st.session_state.user_role = "student"
            st.success("Login successful")
        else:
            st.error("Invalid credentials")

elif role == "Teacher":
    st.subheader("Teacher Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df_teachers = load_teachers()
        user = df_teachers[df_teachers["Gmail ID"] == email]
        if not user.empty and user.iloc[0]["Password"] == password:
            st.session_state.user_name = user.iloc[0]["Teacher Name"]
            st.session_state.user_role = "teacher"
            st.success("Login successful")
        else:
            st.error("Invalid credentials")

# Main App
if st.session_state.user_name:
    st.markdown(f"### Welcome, {st.session_state.user_name}")
    if st.button("Logout"):
        st.session_state.user_name = ""
        st.session_state.user_role = ""
        st.experimental_rerun()

    if st.session_state.user_role == "teacher":
        st.subheader("Upload Homework")
        cls = st.selectbox("Select Class", [f"{i}th" for i in range(6, 13)])
        hw_date = st.date_input("Homework Date", datetime.today())
        uploaded = st.file_uploader("Upload Word File", type=["docx"])
        if uploaded and st.button("Upload Homework"):
            file_path = os.path.join(HOMEWORK_DIR, f"{cls}_{hw_date}.docx")
            temp_path = os.path.join(HOMEWORK_DIR, f"temp_{cls}_{hw_date}.docx")
            with open(temp_path, "wb") as f:
                f.write(uploaded.read())
            insert_heading_and_placeholders(temp_path, file_path)
            st.success(f"Homework uploaded for {cls} on {hw_date}")

    elif st.session_state.user_role == "student":
        df_students = load_students()
        student_row = df_students[df_students["Student Name"] == st.session_state.user_name].iloc[0]
        student_class = student_row["Class"]
        student_email = student_row["Gmail ID"]
        date_selected = st.date_input("Select Date")
        file_to_get = os.path.join(HOMEWORK_DIR, f"{student_class}_{date_selected}.docx")
        download_file = os.path.join(HOMEWORK_DIR, f"{st.session_state.user_name}_{date_selected}.docx")
        if os.path.exists(file_to_get):
            replace_placeholders_in_docx(file_to_get, download_file, st.session_state.user_name, student_class, str(date_selected))
            with open(download_file, "rb") as f:
                st.download_button(f"Download Homework for {date_selected}", f, file_name=os.path.basename(download_file))
        else:
            st.warning("Homework not yet uploaded for this date.")