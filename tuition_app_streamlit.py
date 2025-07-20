import streamlit as st
import gspread
import json
import base64
from google.oauth2.service_account import Credentials

st.title("Google Sheet Connection Test 🧪")

try:
    # Step 1: Load credentials (same as your main app)
    st.info("Attempting to load credentials from Streamlit Secrets...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    st.info("✅ Credentials loaded and client authorized successfully.")

    # Step 2: Try to open ONLY ONE sheet (your STUDENT_SHEET)
    sheet_key = "10rC5yXLzeCzxOLaSbNc3tmHLiTS4RmO1G_PSpxRpSno" 
    st.info(f"Attempting to open Google Sheet with key: {sheet_key}")
    sheet = client.open_by_key(sheet_key).sheet1
    
    # If it reaches here, it worked!
    st.success("🎉 SUCCESS! Successfully connected to and opened the STUDENT_SHEET.")
    st.write(f"Data from cell A1: '{sheet.acell('A1').value}'")

except Exception as e:
    st.error("❌ AN ERROR OCCURRED:")
    st.exception(e)

