import streamlit as st
import pandas as pd
import os
from datetime import date
from pathlib import Path
from docx import Document
import io

# --- Load student data from Excel ---
@st.cache_data
def load_students():
    df = pd.read_excel("StudentMaster.xlsx", engine="openpyxl")
    df.columns = df.columns.str.strip()
    return df

# --- Replace placeholders in Word file 

def replace_placeholders_in_docx(template_path, replacements):
    doc = Document(template_path)

    # --- Replace in paragraphs ---
    for paragraph in doc.paragraphs:
        full_text = "".join(run.text for run in paragraph.runs)
        for key, value in replacements.items():
            if key in full_text:
                full_text = full_text.replace(key, value)
        for i in range(len(paragraph.runs)):
            paragraph.runs[i].text = ""
        if paragraph.runs:
            paragraph.runs[0].text = full_text

    # --- Replace in table cells ---
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text = cell.text
                for key, value in replacements.items():
                    if key in full_text:
                        full_text = full_text.replace(key, value)
                        cell.text = full_text

    # Return as BytesIO
    output_stream = io.BytesIO()
    doc.save(output_stream)
    output_stream.seek(0)
    return output_stream

# --- Load student data ---
df_students = load_students()
st.title("Tuition Homework Portal")

# --- Session Setup ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "student_data" not in st.session_state:
    st.session_state.student_data = {}

# --- Logout Button ---
if st.session_state.logged_in:
    st.sidebar.button("Logout", on_click=lambda: st.session_state.update({
        "logged_in": False,
        "student_data": {}
    }))
    if not st.session_state.logged_in:
        st.rerun()

# --- Login Section ---
if not st.session_state.logged_in:
    st.subheader("Login with Gmail")
    gmail_input = st.text_input("Enter your Gmail ID")

    if gmail_input:
        student_row = df_students[df_students["Gmail ID"].str.lower() == gmail_input.lower()]
        if not student_row.empty:
            student_name = student_row.iloc[0]["Student Name"]
            student_class = str(student_row.iloc[0]["Class"])
            st.session_state.logged_in = True
            st.session_state.student_data = {
                "name": student_name,
                "class": student_class,
                "gmail": gmail_input
            }
            st.success(f"Login successful! Welcome, {student_name}")
            st.rerun()
        else:
            st.error("Gmail not found in StudentMaster.xlsx. Please check spelling or contact admin.")

# --- Main App After Login ---
if st.session_state.logged_in:
    student_name = st.session_state.student_data["name"]
    student_class = st.session_state.student_data["class"]

    st.success(f"Welcome, {student_name} (Class {student_class})")

    # Date picker
    selected_date = st.date_input("Select Date", value=date.today())
    date_str = selected_date.strftime("%Y-%m-%d")

    # Homework Download
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

    # Homework Upload
    st.subheader("📤 Upload Completed Homework")
    uploaded_file = st.file_uploader("Upload your notebook image or PDF", type=["jpg", "jpeg", "png", "pdf"])

    if uploaded_file:
        upload_path = Path(f"uploads/{student_name}/{date_str}")
        upload_path.mkdir(parents=True, exist_ok=True)
        save_to = upload_path / uploaded_file.name

        with open(save_to, "wb") as f:
            f.write(uploaded_file.read())

        st.success(f"Uploaded successfully to {save_to}")