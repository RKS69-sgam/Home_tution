import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt
import os

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
HOMEWORK_DIR = "uploaded_homeworks"
UPI_ID = "9303721909-2@ybl"
SUBSCRIPTION_DAYS = 30
SUBSCRIPTION_AMOUNT = 100

os.makedirs(HOMEWORK_DIR, exist_ok=True)

# Load data
@st.cache_data
def load_students():
    return pd.read_excel(STUDENT_MASTER)

@st.cache_data
def load_teachers():
    return pd.read_excel(TEACHER_MASTER)

def save_students(df):
    df.to_excel(STUDENT_MASTER, index=False)

def insert_heading_and_placeholders(path_in, path_out):
    doc = Document(path_in)
    new_doc = Document()

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

def replace_placeholders(path_in, path_out, name, std_class, date_str):
    doc = Document(path_in)
    for p in doc.paragraphs:
        for run in p.runs:
            run.text = run.text.replace("[StudentName]", f"Student Name: {name}")
            run.text = run.text.replace("[Class]", f"STD - {std_class}")
            run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(path_out)

# UI Start
st.set_page_config("Tuition App", layout="wide")
st.sidebar.title("EXCELLENT PUBLIC SCHOOL")
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

if st.session_state.user:
    with st.sidebar:
        st.markdown(f"Welcome, {st.session_state.user}")
        if st.button("Logout"):
            st.session_state.user = None
            st.session_state.role = None
            st.rerun()

# Login/Registration
if not st.session_state.user:
    role = st.radio("Login as", ["Student", "Teacher", "New Student Registration"])

    if role == "Student":
        st.subheader("Student Login")
        email = st.text_input("Gmail ID")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            df = load_students()
            row = df[df["Gmail ID"] == email]
            if not row.empty and row.iloc[0]["Password"] == password:
                expiry = row.iloc[0]["Subscription Valid Till"]
                if pd.to_datetime(expiry) >= pd.to_datetime(datetime.today()):
                    st.session_state.user = row.iloc[0]["Student Name"]
                    st.session_state.role = "student"
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Subscription expired. Please renew.")
            else:
                st.error("Invalid credentials")

    elif role == "Teacher":
        st.subheader("Teacher Login")
        email = st.text_input("Gmail ID")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            df = load_teachers()
            row = df[df["Gmail ID"] == email]
            if not row.empty and row.iloc[0]["Password"] == password:
                st.session_state.user = row.iloc[0]["Teacher Name"]
                st.session_state.role = "teacher"
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

    elif role == "New Student Registration":
        st.subheader("New Student Registration")
        name = st.text_input("Student Name")
        email = st.text_input("Gmail ID")
        std_class = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
        password = st.text_input("Create Password", type="password")
        st.info(f"Please pay ₹{SUBSCRIPTION_AMOUNT} to UPI ID: {UPI_ID} and then press Register")

        if st.button("Register"):
            df = load_students()
            if email in df["Gmail ID"].values:
                st.error("This email is already registered.")
            else:
                today = datetime.today()
                new_entry = {
                    "Student Name": name,
                    "Gmail ID": email,
                    "Class": std_class,
                    "Password": password,
                    "Subscription Valid Till": today + timedelta(days=SUBSCRIPTION_DAYS)
                }
                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                save_students(df)
                st.success("Registration successful! Please login.")
                st.rerun()

# Main Panel
if st.session_state.user:
    if st.session_state.role == "teacher":
        st.header("Upload Homework")
        cls = st.selectbox("Select Class", [f"{i}th" for i in range(6, 13)])
        date_input = st.date_input("Homework Date", value=datetime.today())
        uploaded = st.file_uploader("Upload Word File", type=["docx"])
        if uploaded and st.button("Upload Homework"):
            date_str = date_input.strftime("%Y-%m-%d")
            temp_path = os.path.join(HOMEWORK_DIR, f"temp_{cls}_{date_str}.docx")
            final_path = os.path.join(HOMEWORK_DIR, f"{cls}_{date_str}.docx")
            with open(temp_path, "wb") as f:
                f.write(uploaded.read())
            insert_heading_and_placeholders(temp_path, final_path)
            st.success("Homework uploaded successfully.")

    elif st.session_state.role == "student":
        st.header("Download Homework")
        df = load_students()
        user_row = df[df["Student Name"] == st.session_state.user].iloc[0]
        std_class = user_row["Class"]
        date_input = st.date_input("Select Homework Date")
        date_str = date_input.strftime("%Y-%m-%d")
        source = os.path.join(HOMEWORK_DIR, f"{std_class}_{date_str}.docx")
        personal = os.path.join(HOMEWORK_DIR, f"{st.session_state.user}_{date_str}.docx")
        if os.path.exists(source):
            replace_placeholders(source, personal, st.session_state.user, std_class, date_str)
            with open(personal, "rb") as f:
                st.download_button("Download Homework", f, file_name=os.path.basename(personal))
        else:
            st.warning("Homework not uploaded for selected date.")