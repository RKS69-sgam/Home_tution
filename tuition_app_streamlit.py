import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
UPI_ID = "9303721909-2@ybl"
SUBSCRIPTION_DAYS = 30

# Setup folders
os.makedirs("uploaded_homeworks", exist_ok=True)
os.makedirs("uploaded_notebooks", exist_ok=True)

# Load data
@st.cache_data
def load_students():
    return pd.read_excel(STUDENT_MASTER)

@st.cache_data
def load_teachers():
    return pd.read_excel(TEACHER_MASTER)

def save_students(df):
    df.to_excel(STUDENT_MASTER, index=False)

# App config
st.set_page_config(page_title="Tuition App", layout="wide")

# Session
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""

# Sidebar menu
st.sidebar.markdown("## 📚 Tuition App Menu")
role = st.sidebar.selectbox("🔐 Login As", ["Student", "Teacher", "Admin", "Register"])

email = st.sidebar.text_input("📧 Gmail ID", key="login_email")
password = st.sidebar.text_input("🔑 Password", type="password", key="login_pass")

if st.session_state.user_name:
    st.sidebar.success(f"👤 Welcome: {st.session_state.user_name}")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.experimental_rerun()

# Header
st.markdown("<h3 style='text-align: center; color:#4b8bbe;'>विद्या ददाति विनयं</h3>", unsafe_allow_html=True)
st.markdown("<h1 style='text-align: center;'>EXCELLENT PUBLIC SCHOOL</h1>", unsafe_allow_html=True)

# Registration logic
if role == "Register":
    st.header("📝 New Student Registration")
    name = st.text_input("Full Name")
    reg_email = st.text_input("Gmail ID (for login)")
    reg_cls = st.selectbox("Class", [f"{i}th" for i in range(6, 13)])
    reg_pass = st.text_input("Create Password", type="password")
    st.markdown("### 💳 Pay ₹100 via UPI below")
    st.code(f"upi://pay?pa={UPI_ID}&am=100", language="text")
    if st.button("✅ Register after Payment"):
        df = load_students()
        if reg_email in df["Gmail ID"].values:
            st.error("This email is already registered.")
        else:
            row = {
                "Sr. No.": df.shape[0]+1,
                "Student Name": name,
                "Gmail ID": reg_email,
                "Class": reg_cls,
                "Password": reg_pass,
                "Subscribed Till": (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).date(),
                "Payment Confirmed": "No"
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            save_students(df)
            st.success("Registered! Admin will confirm your payment shortly.")

# Login actions
if role == "Student" and st.sidebar.button("🎓 Login"):
    df = load_students()
    user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
    if not user.empty:
        row = user.iloc[0]
        if row["Payment Confirmed"] == "Yes" and datetime.today().date() <= pd.to_datetime(row["Subscribed Till"]).date():
            st.session_state.user_name = row["Student Name"]
            st.session_state.user_role = "student"
            st.experimental_rerun()
        else:
            st.error("❌ Payment not confirmed or subscription expired.")
    else:
        st.error("❌ Invalid credentials.")

if role == "Teacher" and st.sidebar.button("👩‍🏫 Login"):
    df = load_teachers()
    user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
    if not user.empty:
        st.session_state.user_name = user.iloc[0]["Teacher Name"]
        st.session_state.user_role = "teacher"
        st.experimental_rerun()
    else:
        st.error("❌ Invalid credentials.")

if role == "Admin" and st.sidebar.button("🔐 Admin Login"):
    df = load_teachers()
    admin = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
    if not admin.empty:
        st.session_state.user_name = "Admin"
        st.session_state.user_role = "admin"
        st.experimental_rerun()
    else:
        st.error("❌ Invalid admin credentials.")

# Admin Panel
if st.session_state.user_role == "admin":
    st.subheader("🛠 Admin Panel - Confirm Payments")
    df = load_students()
    for i, row in df[df["Payment Confirmed"] != "Yes"].iterrows():
        st.write(f"🔸 {row['Student Name']} - {row['Gmail ID']}")
        date_val = st.date_input("Extend Till", datetime.today() + timedelta(days=SUBSCRIPTION_DAYS), key=row['Gmail ID'])
        if st.button(f"✅ Confirm for {row['Student Name']}", key="btn"+row['Gmail ID']):
            df.at[i, "Payment Confirmed"] = "Yes"
            df.at[i, "Subscribed Till"] = date_val
            save_students(df)
            st.success(f"✅ {row['Student Name']} activated till {date_val}")
            st.experimental_rerun()

    st.subheader("📋 All Students")
    st.dataframe(df)

# Student Panel
if st.session_state.user_role == "student":
    st.header("🎓 Student Panel")
    df = load_students()
    student = df[df["Student Name"] == st.session_state.user_name].iloc[0]
    cls = student["Class"]
    date = st.date_input("📅 Homework Date", datetime.today())
    file_path = f"uploaded_homeworks/{cls}_{date}.docx"
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            st.download_button("📥 Download Homework", f, file_name=f"{cls}_{date}.docx")
    else:
        st.warning("📭 Homework not yet uploaded.")

    st.subheader("📤 Upload Completed Notebook")
    notebook = st.file_uploader("Upload JPG/PDF", type=["jpg", "jpeg", "png", "pdf"])
    if notebook:
        path = f"uploaded_notebooks/{st.session_state.user_name}_{date}_{notebook.name}"
        with open(path, "wb") as f:
            f.write(notebook.read())
        st.success("✅ Notebook uploaded.")

# Teacher Panel
if st.session_state.user_role == "teacher":
    st.header("📤 Teacher Panel")
    cls = st.selectbox("Select Class", [f"{i}th" for i in range(6,13)])
    date = st.date_input("📅 Date", datetime.today())
    file = st.file_uploader("Upload Word Homework", type=["docx"])
    if file and st.button("📥 Upload Homework"):
        path = f"uploaded_homeworks/{cls}_{date}.docx"
        with open(path, "wb") as f:
            f.write(file.read())
        st.success("📁 Homework uploaded.")