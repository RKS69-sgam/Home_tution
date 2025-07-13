import streamlit as st
import pandas as pd
from docx import Document
from datetime import datetime, timedelta
import os
from docx.shared import Pt
import base64

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
HOMEWORK_DIR = "uploaded_homeworks"
NOTEBOOK_UPLOAD_DIR = "uploaded_notebooks"
UPI_ID = "9303721909-2@ybl"
SUBSCRIPTION_DAYS = 30
SUBSCRIPTION_FEE = 100

os.makedirs(HOMEWORK_DIR, exist_ok=True)
os.makedirs(NOTEBOOK_UPLOAD_DIR, exist_ok=True)

@st.cache_data
def load_students():
    return pd.read_excel(STUDENT_MASTER)

@st.cache_data
def load_teachers():
    return pd.read_excel(TEACHER_MASTER)

def save_students(df):
    df.to_excel(STUDENT_MASTER, index=False)

def replace_placeholders_in_docx(path_in, path_out, student_name, student_class, date_str):
    doc = Document(path_in)
    for p in doc.paragraphs:
        for run in p.runs:
            run.text = run.text.replace("[StudentName]", f"Student Name: {student_name}")
            run.text = run.text.replace("[Class]", f"STD - {student_class}")
            run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(path_out)

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

# Sidebar logout and menu
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_role" not in st.session_state:
    st.session_state.user_role = ""

with st.sidebar:
    if st.session_state.user_name:
        st.write(f"Logged in as: {st.session_state.user_name}")
        if st.button("Logout"):
            st.session_state.user_name = ""
            st.session_state.user_role = ""
            st.experimental_rerun()

    st.markdown("### 📲 UPI Payment")
    st.markdown(f"Scan and pay ₹{SUBSCRIPTION_FEE} to continue:")
    st.image("https://chart.googleapis.com/chart?chs=200x200&cht=qr&chl=upi://pay?pa=" + UPI_ID + f"&pn=TuitionApp&am={SUBSCRIPTION_FEE}", width=200)

st.title("EXCELLENT PUBLIC SCHOOL - Advance Classes")
role = st.radio("Login as", ["Student", "Teacher", "New Student Registration"])

if role == "New Student Registration":
    st.subheader("Student Registration")
    name = st.text_input("Full Name")
    gmail = st.text_input("Gmail ID")
    student_class = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
    password = st.text_input("Set Password", type="password")
    paid = st.checkbox("I have paid ₹100 via UPI")

    if st.button("Register"):
        df = load_students()
        if gmail in df["Gmail ID"].values:
            st.warning("This Gmail ID is already registered.")
        elif not paid:
            st.warning("Please confirm payment before registering.")
        else:
            today = datetime.today()
            new_row = {
                "Sr. No.": len(df)+1,
                "Student Name": name,
                "Gmail ID": gmail,
                "Class": student_class,
                "Password": password,
                "Subscription Date": today.strftime("%Y-%m-%d"),
                "Subscription Valid Till": (today + timedelta(days=SUBSCRIPTION_DAYS)).strftime("%Y-%m-%d"),
                "Notebook Upload Path": ""
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_students(df)
            st.success("Registration successful. You can now login as Student.")

elif role == "Student":
    st.subheader("Student Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df_students = load_students()
        user = df_students[df_students["Gmail ID"] == email]
        if not user.empty and user.iloc[0]["Password"] == password:
            valid_till = datetime.strptime(user.iloc[0]["Subscription Valid Till"], "%Y-%m-%d")
            if datetime.today() > valid_till:
                st.error("Subscription expired. Please renew.")
            else:
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
        date_selected = st.date_input("Select Date")
        file_to_get = os.path.join(HOMEWORK_DIR, f"{student_class}_{date_selected}.docx")
        download_file = os.path.join(HOMEWORK_DIR, f"{st.session_state.user_name}_{date_selected}.docx")

        if os.path.exists(file_to_get):
            replace_placeholders_in_docx(file_to_get, download_file, st.session_state.user_name, student_class, str(date_selected))
            with open(download_file, "rb") as f:
                st.download_button(f"Download Homework for {date_selected}", f, file_name=os.path.basename(download_file))
        else:
            st.warning("Homework not yet uploaded for this date.")

        st.subheader("Upload Completed Notebook")
        uploaded = st.file_uploader("Upload Completed Homework (image/pdf)", type=["jpg", "png", "jpeg", "pdf"])
        if uploaded:
            notebook_path = os.path.join(NOTEBOOK_UPLOAD_DIR, f"{st.session_state.user_name}_{date_selected}_{uploaded.name}")
            with open(notebook_path, "wb") as f:
                f.write(uploaded.read())
            df_students.loc[df_students["Student Name"] == st.session_state.user_name, "Notebook Upload Path"] = notebook_path
            save_students(df_students)
            st.success("Notebook uploaded successfully.")
 streamlit as st
import pandas as pd
from docx import Document
from datetime import datetime, timedelta
import os
import shutil
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
HOMEWORK_DIR = "uploaded_homeworks"
NOTEBOOK_DIR = "uploaded_notebooks"
os.makedirs(HOMEWORK_DIR, exist_ok=True)
os.makedirs(NOTEBOOK_DIR, exist_ok=True)

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
            run.text = run.text.replace("[StudentName]", f"Student Name: {student_name}")
            run.text = run.text.replace("[Class]", f"STD - {student_class}")
            run.text = run.text.replace("[HomeworkDate]", f"Date: {date_str}")
    doc.save(path_out)

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

def is_subscription_valid(reg_date):
    return (datetime.today().date() - reg_date.date()).days <= 30

# UI Layout
st.set_page_config(layout="wide")
col1, col2 = st.columns([1, 8])

with col1:
    if st.session_state.get("user_name"):
        if st.button("Logout"):
            st.session_state.clear()
            st.experimental_rerun()

st.title("EXCELLENT PUBLIC SCHOOL - Tuition App")

# Role selection and login/registration
role = st.radio("Login as", ["Student", "Teacher", "New Registration"])

if role == "Student":
    st.subheader("Student Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        df_students = load_students()
        user = df_students[df_students["Gmail ID"] == email]
        if not user.empty and user.iloc[0]["Password"] == password:
            reg_date = pd.to_datetime(user.iloc[0]["Subscription Date"])
            if is_subscription_valid(reg_date):
                st.session_state.user_name = user.iloc[0]["Student Name"]
                st.session_state.user_role = "student"
                st.success("Login successful")
            else:
                st.error("Subscription expired. Please renew to continue.")
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

elif role == "New Registration":
    st.subheader("Student Registration (₹100 for 30 days)")
    name = st.text_input("Student Name")
    gmail = st.text_input("Gmail ID")
    password = st.text_input("Password")
    cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
    if st.button("Pay ₹100 via UPI & Register"):
        st.info("Pay ₹100 to 9303721909-2@ybl via PhonePe/UPI and then click Confirm")
        if st.button("Confirm Payment"):
            df = load_students()
            sr_no = df["Sr. No."].max() + 1 if not df.empty else 1
            today = datetime.today().strftime("%Y-%m-%d")
            new_entry = {"Sr. No.": sr_no, "Student Name": name, "Gmail ID": gmail, "Class": cls, "Password": password, "Subscription Date": today}
            df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
            df.to_excel(STUDENT_MASTER, index=False)
            st.success("Registration successful. You can now login.")

# Main App
if st.session_state.get("user_name"):
    st.markdown(f"### Welcome, {st.session_state.user_name}")

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

        st.subheader("Download Homework")
        date_selected = st.date_input("Select Date")
        file_to_get = os.path.join(HOMEWORK_DIR, f"{student_class}_{date_selected}.docx")
        download_file = os.path.join(HOMEWORK_DIR, f"{st.session_state.user_name}_{date_selected}.docx")
        if os.path.exists(file_to_get):
            replace_placeholders_in_docx(file_to_get, download_file, st.session_state.user_name, student_class, str(date_selected))
            with open(download_file, "rb") as f:
                st.download_button(f"Download Homework for {date_selected}", f, file_name=os.path.basename(download_file))
        else:
            st.warning("Homework not yet uploaded for this date.")

        st.subheader("Upload Completed Notebook")
        uploaded_notebook = st.file_uploader("Upload your completed notebook (image/docx/pdf)", type=["jpg", "jpeg", "png", "pdf", "docx"])
        if uploaded_notebook and st.button("Upload Notebook"):
            date_str = datetime.today().strftime("%Y-%m-%d")
            nb_path = os.path.join(NOTEBOOK_DIR, f"{st.session_state.user_name}_{date_str}_{uploaded_notebook.name}")
            with open(nb_path, "wb") as f:
                f.write(uploaded_notebook.read())
            st.success("Notebook uploaded successfully.")
