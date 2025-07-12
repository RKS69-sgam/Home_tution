import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import shutil
import os

# ---------- Load Excel ----------
@st.cache_data
def load_students():
    return pd.read_excel("StudentMaster.xlsx", engine="openpyxl")

@st.cache_data
def load_teachers():
    return pd.read_excel("TeacherMaster.xlsx", engine="openpyxl")

# ---------- Add header + placeholders to Word ----------
def insert_heading_and_placeholders(doc):
    def add_centered(text, bold=False, italic=False, size=12):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(size)

    add_centered("EXCELLENT PUBLIC SCHOOL", bold=True, size=16)
    add_centered("Barainiya, Bargawan Distt. Singrauli (MP)", size=12)
    add_centered("Advance Classes Daily Homework", bold=True, italic=True, size=14)

    doc.add_paragraph("Student Name: [StudentName]").runs[0].font.size = Pt(12)
    doc.add_paragraph("STD - [Class]").runs[0].font.size = Pt(12)
    doc.add_paragraph("Date: [HomeworkDate]").runs[0].font.size = Pt(12)
    return doc

# ---------- Save uploaded teacher homework ----------
def process_homework_upload(uploaded_file, selected_class, date_str):
    filename = f"{date_str}.docx"
    temp_path = f"temp_{filename}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.read())
    doc = Document(temp_path)
    doc = insert_heading_and_placeholders(doc)
    output_path = Path(f"HOMEWORK/{selected_class}")
    output_path.mkdir(parents=True, exist_ok=True)
    final_path = output_path / filename
    doc.save(final_path)
    os.remove(temp_path)
    return final_path

# ---------- Save uploaded notebook ----------
def save_uploaded_notebook(uploaded_file, student_name, date_str):
    save_path = Path(f"NOTEBOOKS/{student_name}/{date_str}")
    save_path.mkdir(parents=True, exist_ok=True)
    file_path = save_path / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

# ---------- App Layout ----------
st.set_page_config("Tuition App", layout="centered")
st.title("EXCELLENT PUBLIC SCHOOL - Tuition App")

role = st.radio("Login as", ["Student", "Teacher"])

if role == "Student":
    df_students = load_students()
    with st.form("student_login"):
        st.subheader("Student Login")
        email = st.text_input("Gmail ID")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        if email in df_students["Gmail"].values:
            row = df_students[df_students["Gmail"] == email].iloc[0]
            if str(row["Password"]).strip() == password.strip():
                st.session_state["logged_in"] = True
                st.session_state["user_role"] = "student"
                st.session_state["student_name"] = row["Name"]
                st.session_state["student_class"] = str(row["Class"])
                st.success(f"Welcome, {row['Name']} (Class {row['Class']})")
            else:
                st.error("Incorrect password")
        else:
            st.error("Email not found")

    if st.session_state.get("logged_in") and st.session_state.get("user_role") == "student":
        st.subheader("Student Homework Panel")

        student_name = st.session_state["student_name"]
        student_class = st.session_state["student_class"]

        selected_date = st.date_input("Select Homework Date", value=date.today())
        date_str = selected_date.strftime("%Y-%m-%d")

        st.markdown("### Download Homework")
        homework_path = Path(f"HOMEWORK/{student_class}/{date_str}.docx")

        if homework_path.exists():
            renamed_name = f"{student_name}_{date_str}.docx"
            renamed_path = Path(f"temp/{renamed_name}")
            renamed_path.parent.mkdir(exist_ok=True)
            shutil.copy(homework_path, renamed_path)

            with open(renamed_path, "rb") as f:
                st.download_button(
                    label=f"Download {renamed_name}",
                    data=f,
                    file_name=renamed_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        else:
            st.warning("Homework not available for this date.")

        st.markdown("### Upload Completed Notebook")
        uploaded_notebook = st.file_uploader("Upload notebook file", type=["png", "jpg", "jpeg", "pdf", "docx"])

        if uploaded_notebook:
            path = save_uploaded_notebook(uploaded_notebook, student_name, date_str)
            st.success(f"Notebook uploaded successfully: {path}")

elif role == "Teacher":
    df_teachers = load_teachers()
    with st.form("teacher_login"):
        st.subheader("Teacher Login")
        email = st.text_input("Gmail ID")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        if email in df_teachers["Gmail"].values:
            row = df_teachers[df_teachers["Gmail"] == email].iloc[0]
            if str(row["Password"]).strip() == password.strip():
                st.session_state["logged_in"] = True
                st.session_state["user_role"] = "teacher"
                st.session_state["teacher_name"] = row["Name"]
                st.success(f"Welcome, {row['Name']}")
            else:
                st.error("Incorrect password")
        else:
            st.error("Email not found")

    if st.session_state.get("logged_in") and st.session_state.get("user_role") == "teacher":
        st.subheader("Upload Homework")

        selected_class = st.selectbox("Select Class", ["6th", "7th", "8th", "9th", "10th", "11th", "12th"])
        selected_date = st.date_input("Select Homework Date", value=date.today())
        date_str = selected_date.strftime("%Y-%m-%d")

        uploaded_file = st.file_uploader("Upload Word File (.docx)", type=["docx"])

        if uploaded_file:
            path = process_homework_upload(uploaded_file, selected_class, date_str)
            st.success(f"✅ Homework saved: {path}")