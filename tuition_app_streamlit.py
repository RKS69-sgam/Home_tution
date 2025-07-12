import streamlit as st
import pandas as pd
from datetime import date
import shutil
from pathlib import Path
import os

# ---------- Config ----------
st.set_page_config("EXCELLENT PUBLIC SCHOOL - Tuition App", layout="centered")

# ---------- Load Data ----------
@st.cache_data
def load_students():
    return pd.read_excel("StudentMaster.xlsx", engine="openpyxl")

@st.cache_data
def load_teachers():
    return pd.read_excel("TeacherMaster.xlsx", engine="openpyxl")

# ---------- Save Uploaded Homework ----------
def save_teacher_homework(file, selected_class, selected_date):
    date_str = selected_date.strftime("%Y-%m-%d")
    path = Path(f"HOMEWORK/{selected_class}/{date_str}.docx")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(file.read())
    return path

# ---------- Save Uploaded Notebook ----------
def save_uploaded_notebook(uploaded_file, student_name, date_str):
    save_path = Path(f"NOTEBOOKS/{student_name}/{date_str}")
    save_path.mkdir(parents=True, exist_ok=True)
    file_path = save_path / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

# ---------- Login Section ----------
st.title("EXCELLENT PUBLIC SCHOOL - Tuition App")
role = st.radio("Login as", ["Student", "Teacher"])

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_class = ""
    st.session_state.role = ""

if not st.session_state.logged_in:
    with st.form("login_form"):
        st.subheader(f"{role} Login")
        email = st.text_input("Gmail ID")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        if role == "Student":
            df = load_students()
        else:
            df = load_teachers()
        if email in df["Gmail ID"].values:
            row = df[df["Gmail ID"] == email].iloc[0]
            if str(row["Password"]).strip() == password.strip():
                st.session_state.logged_in = True
                st.session_state.user_name = row["Name"]
                st.session_state.role = role
                if role == "Student":
                    st.session_state.user_class = str(row["Class"])
                st.rerun()
            else:
                st.error("Incorrect password")
        else:
            st.error("Gmail ID not found.")
else:
    st.success(f"Welcome, {st.session_state.user_name} ({st.session_state.role})")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

    # ---------- Teacher Panel ----------
    if st.session_state.role == "Teacher":
        st.subheader("Upload Daily Homework")
        selected_class = st.selectbox("Select Class", ["6th", "7th", "8th", "9th", "10th", "11th", "12th"])
        selected_date = st.date_input("Select Homework Date", value=date.today())
        uploaded_file = st.file_uploader("Upload Word File (.docx)", type=["docx"])
        if uploaded_file and st.button("Upload"):
            saved_path = save_teacher_homework(uploaded_file, selected_class, selected_date)
            st.success(f"Homework saved to: {saved_path}")

    # ---------- Student Panel ----------
    elif st.session_state.role == "Student":
        st.subheader("Download & Upload Homework")
        student_name = st.session_state.user_name
        student_class = st.session_state.user_class
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
            st.warning("Homework not available for selected date.")

        st.markdown("### Upload Completed Notebook")
        uploaded_notebook = st.file_uploader("Upload your notebook (image/pdf/word)", type=["png", "jpg", "jpeg", "pdf", "docx"])
        if uploaded_notebook:
            path = save_uploaded_notebook(uploaded_notebook, student_name, date_str)
            st.success(f"Notebook uploaded to: {path}")

        # Show Homework History
        st.markdown("### 📅 Homework History")
        history_dir = Path(f"HOMEWORK/{student_class}")
        if history_dir.exists():
            all_files = sorted(history_dir.glob("*.docx"))
            for f in all_files:
                st.write(f.name)
        else:
            st.info("No homework uploaded yet.")