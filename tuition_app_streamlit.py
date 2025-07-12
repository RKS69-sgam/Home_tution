import streamlit as st
import pandas as pd
import os
from datetime import date
from pathlib import Path

# --- Load student data from Excel ---
@st.cache_data
def load_students():
    df = pd.read_excel("StudentMaster.xlsx", sheet_name("Sheet1"))
    df.columns = df.columns.str.strip()
    return df

df_students = load_students()

st.title("Tuition Homework Portal")

# --- Login Section ---
st.subheader("Login with Gmail")
gmail_input = st.text_input("Enter your Gmail ID")

# Match Gmail
student_row = df_students[df_students["Gmail ID"].str.lower() == gmail_input.lower()]

if not student_row.empty:
    student_name = student_row.iloc[0]["Student Name"]
    student_class = str(student_row.iloc[0]["Class"])
    st.success(f"Welcome, {student_name} (Class {student_class})")

    # Date picker
    selected_date = st.date_input("Select Date", value=date.today())
    date_str = selected_date.strftime("%Y-%m-%d")

    # Homework Download
    st.subheader("📥 Download Homework")
    homework_path = f"HOMEWORK/{student_class}/{date_str}.docx"

    if os.path.exists(homework_path):
        download_name = f"{student_name}-{date_str}-Homework.docx"
        with open(homework_path, "rb") as f:
            st.download_button("Download Homework", f, file_name=download_name)
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
else:
    if gmail_input:
        st.error("Gmail not found in StudentMaster.xlsx. Please check spelling or contact admin.")
