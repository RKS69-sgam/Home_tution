import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from docx import Document
from docx.shared import Pt

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
HOMEWORK_DIR = "uploaded_homeworks"
NOTEBOOK_DIR = "uploaded_notebooks"
UPI_ID = "9685840429@pnb"
SUBSCRIPTION_DAYS = 30
LOGO_PATH = "logo.png"  # Your fixed Saraswati logo file

# Ensure folders
os.makedirs(HOMEWORK_DIR, exist_ok=True)
os.makedirs(NOTEBOOK_DIR, exist_ok=True)

# Loaders and savers
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

    new_doc.add_picture(LOGO_PATH, width=Pt(180))

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

def replace_placeholders(path_in, path_out, name, cls, date_str):
    doc = Document(path_in)
    for p in doc.paragraphs:
        for run in p.runs:
            run.text = run.text.replace("[StudentName]", f"Student Name: {name}")
            run.text = run.text.replace("[Class]", f"STD - {cls}")
            run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(path_out)

# UI Layout
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .sidebar .sidebar-content { background-color: #f0f8ff; padding-top: 20px; }
    .sidebar .css-ng1t4o { font-weight: bold; color: #003366; font-size: 20px; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.title("📚 Tuition Menu")
st.sidebar.markdown("---")

# Logo and header
col1, col2 = st.columns([1, 4])
with col1:
    st.image(LOGO_PATH, width=100)
with col2:
    st.markdown("### विद्या ददाति विनयं")
    st.markdown("## **EXCELLENT PUBLIC SCHOOL**")
    st.markdown("### Barainiya, Bargawan Distt. Singrauli (MP)")

# Session
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.experimental_rerun()

# Login selection
role = st.sidebar.radio("Login as", ["Student", "Teacher", "Register", "Admin"])

# Registration
if role == "Register":
    st.subheader("New Student Registration")
    name = st.text_input("Student Name")
    gmail = st.text_input("Gmail ID")
    cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
    password = st.text_input("Create Password", type="password")

    st.subheader("Pay ₹100 Subscription")
    st.code(f"upi://pay?pa={UPI_ID}&am=100", language="text")

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
                "Subscribed Till": datetime.today() + timedelta(days=SUBSCRIPTION_DAYS),
                "Payment Confirmed": "No"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_students(df)
            st.success("Registered successfully. Wait for admin to confirm.")

# Student login
elif role == "Student":
    st.subheader("Student Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df = load_students()
        user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not user.empty:
            row = user.iloc[0]
            if row["Payment Confirmed"] == "Yes" and datetime.today() <= pd.to_datetime(row["Subscribed Till"]):
                st.session_state.user_name = row["Student Name"]
                st.session_state.user_role = "student"
                st.success("Login successful")
                st.experimental_rerun()
            else:
                st.error("Payment not confirmed or subscription expired.")
        else:
            st.error("Invalid credentials.")

# Teacher login
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
            st.experimental_rerun()
        else:
            st.error("Invalid credentials.")

# Admin login
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

            if "Subscribed Till" not in df.columns:
                df["Subscribed Till"] = ""
            if "Payment Confirmed" not in df.columns:
                df["Payment Confirmed"] = "No"

            pending = df[df["Payment Confirmed"] != "Yes"]
            for i, row in pending.iterrows():
                st.write(f"{row['Sr. No.']}. {row['Student Name']} ({row['Gmail ID']})")
                try:
                    current_date = pd.to_datetime(row["Subscribed Till"]).date()
                except:
                    current_date = datetime.today().date()
                new_date = st.date_input(f"Subscribed Till for {row['Student Name']}", current_date, key=row["Gmail ID"])
                if st.button(f"Confirm Payment for {row['Student Name']}", key="btn_"+row["Gmail ID"]):
                    df.at[i, "Payment Confirmed"] = "Yes"
                    df.at[i, "Subscribed Till"] = new_date
                    save_students(df)
                    st.success(f"{row['Student Name']} confirmed till {new_date}")
                    st.experimental_rerun()

            st.subheader("All Students")
            editable_df = df.copy()
            editable_df["Subscribed Till"] = editable_df["Subscribed Till"].astype(str)
            edited_df = st.data_editor(editable_df, num_rows="dynamic", key="admin_table")
            if st.button("Save Changes"):
                edited_df["Subscribed Till"] = pd.to_datetime(edited_df["Subscribed Till"], errors='coerce')
                save_students(edited_df)
                st.success("Student data updated.")

# Panel after login
if st.session_state.user_name:
    st.sidebar.success(f"Welcome {st.session_state.user_name}")
    role = st.session_state.user_role

    if role == "teacher":
        st.subheader("Upload Homework")
        cls = st.selectbox("Select Class", [f"{i}th" for i in range(6, 13)])
        date = st.date_input("Homework Date", datetime.today())
        file = st.file_uploader("Upload Word File", type=["docx"])
        if file and st.button("Upload Homework"):
            temp_path = os.path.join(HOMEWORK_DIR, f"temp_{cls}_{date}.docx")
            final_path = os.path.join(HOMEWORK_DIR, f"{cls}_{date}.docx")
            with open(temp_path, "wb") as f:
                f.write(file.read())
            insert_heading_and_placeholders(temp_path, final_path)
            st.success("Homework uploaded.")

    elif role == "student":
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
            st.warning("Homework not uploaded yet.")

        st.subheader("Upload Completed Notebook")
        notebook = st.file_uploader("Upload your notebook", type=["jpg", "jpeg", "png", "pdf"])
        if notebook:
            save_path = os.path.join(NOTEBOOK_DIR, f"{st.session_state.user_name}_{date}_{notebook.name}")
            with open(save_path, "wb") as f:
                f.write(notebook.read())
            st.success("Notebook uploaded.")