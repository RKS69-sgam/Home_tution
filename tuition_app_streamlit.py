import streamlit as st
import pandas as pd
import os
from datetime import date
from pathlib import Path
from docx import Document
import io

@st.cache_data
def load_students():
    df = pd.read_excel("StudentMaster.xlsx", engine="openpyxl")
    df.columns = df.columns.str.strip()
    return df

@st.cache_data
def load_teachers():
    df = pd.read_excel("TeacherMaster.xlsx", engine="openpyxl")
    df.columns = df.columns.str.strip()
    return df

def replace_placeholders_in_docx(template_path, replacements):
    doc = Document(template_path)
    for p in doc.paragraphs:
        full_text = "".join(run.text for run in p.runs)
        for key, value in replacements.items():
            full_text = full_text.replace(key, value)
        for run in p.runs:
            run.text = ""
        if p.runs:
            p.runs[0].text = full_text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text = cell.text
                for key, value in replacements.items():
                    full_text = full_text.replace(key, value)
                cell.text = full_text
    output_stream = io.BytesIO()
    doc.save(output_stream)
    output_stream.seek(0)
    return output_stream

df_students = load_students()
df_teachers = load_teachers()

st.title("Tuition Homework Portal")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "user_data" not in st.session_state:
    st.session_state.user_data = {}

if st.session_state.logged_in:
    st.sidebar.button("Logout", on_click=lambda: st.session_state.update({
        "logged_in": False,
        "user_data": {},
        "user_role": None
    }))
    if not st.session_state.logged_in:
        st.rerun()

if not st.session_state.logged_in:
    st.subheader("Login with Gmail & Password")
    gmail_input = st.text_input("Enter your Gmail ID")
    password_input = st.text_input("Enter your Password", type="password")

    if st.button("Login"):
        student_row = df_students[
            (df_students["Gmail ID"].str.lower() == gmail_input.lower()) &
            (df_students["Password"] == password_input)
        ]
        teacher_row = df_teachers[
            (df_teachers["Gmail ID"].str.lower() == gmail_input.lower()) &
            (df_teachers["Password"] == password_input)
        ]

        if not student_row.empty:
            student_name = student_row.iloc[0]["Student Name"]
            student_class = str(student_row.iloc[0]["Class"])
            st.session_state.logged_in = True
            st.session_state.user_role = "student"
            st.session_state.user_data = {
                "name": student_name,
                "class": student_class,
                "gmail": gmail_input
            }
            st.success(f"Login successful! Welcome, {student_name}")
            st.rerun()
        elif not teacher_row.empty:
            teacher_name = teacher_row.iloc[0]["Teacher Name"]
            st.session_state.logged_in = True
            st.session_state.user_role = "teacher"
            st.session_state.user_data = {
                "name": teacher_name,
                "gmail": gmail_input
            }
            st.success(f"Login successful! Welcome, {teacher_name}")
            st.rerun()
        else:
            st.error("Invalid Gmail ID or Password.")

# --- Student Panel ---
if st.session_state.logged_in and st.session_state.user_role == "student":
    student_name = st.session_state.user_data["name"]
    student_class = st.session_state.user_data["class"]
    st.success(f"Welcome, {student_name} (Class {student_class})")

    selected_date = st.date_input("Select Date", value=date.today())
    date_str = selected_date.strftime("%Y-%m-%d")

    st.subheader("📥 Download Homework")
    homework_path = f"HOMEWORK/{student_class}/{date_str}.docx"
    if os.path.exists(homework_path):
        replacements = {
            "[StudentName]": f"Student Name: {student_name}",
            "[HomeworkDate]": f"Date: {selected_date.strftime('%d-%m-%Y')}",
            "[Class]": f"STD - {student_class}"
        }
        modified_doc = replace_placeholders_in_docx(homework_path, replacements)
        download_name = f"{student_name}-{date_str}-Homework.docx"
        st.download_button("Download Homework", modified_doc, file_name=download_name)
    else:
        st.warning("Homework not uploaded yet for this date.")

    st.subheader("📤 Upload Completed Homework")
    uploaded_file = st.file_uploader("Upload your notebook image or PDF", type=["jpg", "jpeg", "png", "pdf"])
    if uploaded_file:
        upload_path = Path(f"uploads/{student_name}/{date_str}")
        upload_path.mkdir(parents=True, exist_ok=True)
        save_to = upload_path / uploaded_file.name
        with open(save_to, "wb") as f:
            f.write(uploaded_file.read())
        st.success(f"Uploaded successfully to {save_to}")

# --- Teacher Panel ---
if st.session_state.logged_in and st.session_state.user_role == "teacher":
    st.success(f"Welcome Teacher: {st.session_state.user_data['name']}")
    st.subheader("📤 Upload Homework for Class")

    # ✅ Updated Class Dropdown
    selected_class = st.selectbox("Select Class", ["6th", "7th", "8th", "9th", "10th", "11th", "12th"])

    selected_date = st.date_input("Homework Date", value=date.today())
    date_str = selected_date.strftime("%Y-%m-%d")

    homework_file = st.file_uploader("Upload Homework Word File (.docx)", type=["docx"])
    if homework_file:
        homework_dir = Path(f"HOMEWORK/{selected_class}")
        homework_dir.mkdir(parents=True, exist_ok=True)
        homework_path = homework_dir / f"{date_str}.docx"
        with open(homework_path, "wb") as f:
            f.write(homework_file.read())
        st.success(f"Homework uploaded for {selected_class} on {date_str}")