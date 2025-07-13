import streamlit as st
import pandas as pd
import os
from datetime import datetime
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
HOMEWORK_DIR = "uploaded_homeworks"
UPLOAD_DIR = "notebook_uploads"
os.makedirs(HOMEWORK_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Load Data
@st.cache_data
def load_students():
    return pd.read_excel(STUDENT_MASTER)

@st.cache_data
def load_teachers():
    return pd.read_excel(TEACHER_MASTER)

# Insert Heading + Placeholders
def insert_heading_and_placeholders(path_in, path_out):
    doc = Document(path_in)
    new_doc = Document()

    p1 = new_doc.add_paragraph("EXCELLENT PUBLIC SCHOOL")
    p1.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    r1 = p1.runs[0]
    r1.bold = True
    r1.font.size = Pt(16)

    p2 = new_doc.add_paragraph("Barainiya, Bargawan Distt. Singrauli (MP)")
    p2.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    p3 = new_doc.add_paragraph("Advance Classes Daily Homework")
    p3.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    r3 = p3.runs[0]
    r3.bold = True
    r3.italic = True
    r3.font.size = Pt(14)

    new_doc.add_paragraph("[StudentName]")
    new_doc.add_paragraph("[Class]")
    new_doc.add_paragraph("[HomeworkDate]")

    for para in doc.paragraphs:
        new_doc.add_paragraph(para.text)

    new_doc.save(path_out)

# Replace placeholders
def replace_placeholders(doc_path, out_path, student_name, student_class, date_str):
    doc = Document(doc_path)
    for para in doc.paragraphs:
        for run in para.runs:
            run.text = run.text.replace("[StudentName]", f"Student Name: {student_name}")
            run.text = run.text.replace("[Class]", f"STD - {student_class}")
            run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(out_path)

# Sidebar Logout
with st.sidebar:
    if "user_name" in st.session_state:
        st.sidebar.markdown(f"**Logged in as:** {st.session_state.user_name}")
        if st.button("Logout"):
            st.session_state.clear()
            st.experimental_rerun()

# Title
st.title("EXCELLENT PUBLIC SCHOOL - Tuition App")

# Role selection
role = st.radio("Login as", ["Student", "Teacher"])

# Login Handling
if "user_name" not in st.session_state:
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if role == "Student":
            df = load_students()
            user = df[df["Gmail ID"] == email]
            if not user.empty and user.iloc[0]["Password"] == password:
                st.session_state.user_name = user.iloc[0]["Student Name"]
                st.session_state.role = "student"
                st.success("Login successful")
                st.experimental_rerun()
            else:
                st.error("Invalid student credentials")
        else:
            df = load_teachers()
            user = df[df["Gmail ID"] == email]
            if not user.empty and user.iloc[0]["Password"] == password:
                st.session_state.user_name = user.iloc[0]["Teacher Name"]
                st.session_state.role = "teacher"
                st.success("Login successful")
                st.experimental_rerun()
            else:
                st.error("Invalid teacher credentials")

# Main App
if "user_name" in st.session_state:
    st.markdown(f"### Welcome, {st.session_state.user_name}")

    # Teacher panel
    if st.session_state.role == "teacher":
        st.subheader("Upload Homework")
        cls = st.selectbox("Select Class", [f"{i}th" for i in range(6, 13)])
        hw_date = st.date_input("Homework Date", datetime.today())
        uploaded = st.file_uploader("Upload Word File", type=["docx"])
        if uploaded and st.button("Upload Homework"):
            temp_path = os.path.join(HOMEWORK_DIR, f"temp_{cls}_{hw_date}.docx")
            final_path = os.path.join(HOMEWORK_DIR, f"{cls}_{hw_date}.docx")
            with open(temp_path, "wb") as f:
                f.write(uploaded.read())
            insert_heading_and_placeholders(temp_path, final_path)
            os.remove(temp_path)
            st.success("Homework uploaded successfully.")

    # Student panel
    elif st.session_state.role == "student":
        df = load_students()
        row = df[df["Student Name"] == st.session_state.user_name].iloc[0]
        student_class = row["Class"]
        date_sel = st.date_input("Select Date")
        base_file = os.path.join(HOMEWORK_DIR, f"{student_class}_{date_sel}.docx")
        final_file = os.path.join(HOMEWORK_DIR, f"{st.session_state.user_name}_{date_sel}.docx")
        if os.path.exists(base_file):
            replace_placeholders(base_file, final_file, st.session_state.user_name, student_class, str(date_sel))
            with open(final_file, "rb") as f:
                st.download_button("Download Homework", f, file_name=os.path.basename(final_file))
        else:
            st.warning("Homework not available for this date.")

        # Upload notebook
        st.subheader("Upload Completed Homework Notebook")
        uploaded_hw = st.file_uploader("Upload your notebook (PDF, Image, ZIP)", type=["pdf", "jpg", "jpeg", "png", "zip"])
        if uploaded_hw and st.button("Upload Notebook"):
            fname = f"{st.session_state.user_name}_{date_sel}_{uploaded_hw.name}"
            with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
                f.write(uploaded_hw.read())
            st.success("Notebook uploaded successfully.")