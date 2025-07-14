import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# Constants
STUDENT_MASTER = "StudentMaster.xlsx"
TEACHER_MASTER = "TeacherMaster.xlsx"
UPI_ID = "9303721909-2@ybl"
SUBSCRIPTION_DAYS = 30

# Create upload folders
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

# App setup
st.set_page_config(page_title="Tuition App", layout="wide")

# Session init
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
    st.session_state.user_role = ""

# Sidebar UI
st.sidebar.title("📚 Tuition App Menu")

if st.session_state.user_name:
    st.sidebar.markdown(f"👤 Logged in as **{st.session_state.user_name}**")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.experimental_rerun()

# Header
st.markdown("<h3 style='text-align: center;'>विद्या ददाति विनयं</h3>", unsafe_allow_html=True)
st.markdown("<h1 style='text-align: center;'>EXCELLENT PUBLIC SCHOOL</h1>", unsafe_allow_html=True)

# Role-based login menu
role = st.sidebar.selectbox("🔐 Login/Register", ["Student", "Teacher", "Register", "Admin"])

# Registration
if role == "Register":
    st.subheader("📝 New Student Registration")
    name = st.text_input("Full Name")
    gmail = st.text_input("Gmail ID")
    cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
    password = st.text_input("Create Password", type="password")

    st.markdown(f"### 💰 Pay ₹100 to register via UPI")
    st.code(f"upi://pay?pa={UPI_ID}&am=100", language="text")

    if st.button("✅ I have paid. Register me"):
        df = load_students()
        if gmail in df["Gmail ID"].values:
            st.error("Already registered.")
        else:
            new_row = {
                "Sr. No.": df.shape[0] + 1,
                "Student Name": name,
                "Gmail ID": gmail,
                "Class": cls,
                "Password": password,
                "Subscribed Till": (datetime.today() + timedelta(days=SUBSCRIPTION_DAYS)).date(),
                "Payment Confirmed": "No"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_students(df)
            st.success("Registered! Wait for admin to confirm your payment.")

# Student Login
elif role == "Student":
    st.subheader("🎓 Student Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("🔓 Login"):
        df = load_students()
        user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not user.empty:
            row = user.iloc[0]
            if row["Payment Confirmed"] == "Yes" and datetime.today().date() <= pd.to_datetime(row["Subscribed Till"]).date():
                st.session_state.user_name = row["Student Name"]
                st.session_state.user_role = "student"
                st.experimental_rerun()
            else:
                st.error("Subscription expired or payment not confirmed.")
        else:
            st.error("Invalid credentials")

# Teacher Login
elif role == "Teacher":
    st.subheader("👩‍🏫 Teacher Login")
    email = st.text_input("Gmail ID")
    password = st.text_input("Password", type="password")
    if st.button("🔓 Login"):
        df = load_teachers()
        user = df[(df["Gmail ID"] == email) & (df["Password"] == password)]
        if not user.empty:
            st.session_state.user_name = user.iloc[0]["Teacher Name"]
            st.session_state.user_role = "teacher"
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")

# Admin Login
elif role == "Admin":
    st.subheader("🔐 Admin Login")
    email = st.text_input("Admin Gmail ID")
    password = st.text_input("Admin Password", type="password")
    if st.button("Login as Admin"):
        df_admin = load_teachers()
        admin_user = df_admin[(df_admin["Gmail ID"] == email) & (df_admin["Password"] == password)]
        if not admin_user.empty:
            df = load_students()
            st.success("✅ Admin logged in")

            st.subheader("🟡 Pending Confirmations")
            pending = df[df["Payment Confirmed"] != "Yes"]
            for i, row in pending.iterrows():
                st.write(f"{row['Sr. No.']}. {row['Student Name']} - {row['Gmail ID']}")
                new_date = st.date_input("Valid Till", datetime.today() + timedelta(days=SUBSCRIPTION_DAYS), key=row['Gmail ID'])
                if st.button(f"Confirm Payment for {row['Student Name']}", key="confirm_" + row['Gmail ID']):
                    df.at[i, "Payment Confirmed"] = "Yes"
                    df.at[i, "Subscribed Till"] = new_date
                    save_students(df)
                    st.success(f"{row['Student Name']} confirmed.")
                    st.experimental_rerun()

            st.subheader("✏️ Edit Student Data")
            edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Save Changes"):
                save_students(edited)
                st.success("Student data updated.")

# Student Logged In
if st.session_state.user_name and st.session_state.user_role == "student":
    st.header(f"📥 Welcome {st.session_state.user_name}")
    cls = load_students().query("`Student Name` == @st.session_state.user_name")["Class"].values[0]
    today = datetime.today().date()
    file_path = f"uploaded_homeworks/{cls}_{today}.docx"
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            st.download_button("📥 Download Homework", f, file_name=os.path.basename(file_path))
    else:
        st.info("No homework uploaded yet.")

    st.subheader("📤 Upload Completed Notebook")
    notebook = st.file_uploader("Upload notebook image/pdf", type=["jpg", "jpeg", "png", "pdf"])
    if notebook:
        save_path = f"uploaded_notebooks/{st.session_state.user_name}_{today}_{notebook.name}"
        with open(save_path, "wb") as f:
            f.write(notebook.read())
        st.success("Notebook uploaded.")

# Teacher Logged In
if st.session_state.user_name and st.session_state.user_role == "teacher":
    st.subheader("📤 Upload Homework")
    cls = st.selectbox("Class", [f"{i}th" for i in range(6,13)])
    date = st.date_input("Date", datetime.today())
    uploaded = st.file_uploader("Upload Homework Word File", type=["docx"])
    if uploaded:
        path = f"uploaded_homeworks/{cls}_{date}.docx"
        with open(path, "wb") as f:
            f.write(uploaded.read())
        st.success("Homework uploaded.")