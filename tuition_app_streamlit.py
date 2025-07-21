import streamlit as st
import json
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

st.title("Google Drive Upload Test 🔬")

# --- IMPORTANT: Paste your ACTUAL Homework Folder ID here ---
HOMEWORK_FOLDER_ID = "1cwEA6Gi1RIV9EymVYcwNy02kmGzFLSOe" 

try:
    # 1. Load credentials
    st.info("Loading credentials...")
    scopes = ["https://www.googleapis.com/auth/drive"] 
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    drive_service = build("drive", "v3", credentials=credentials)
    st.success("✅ Credentials loaded.")

    # 2. Try to create and upload a simple text file
    st.info(f"Attempting to upload a test file to folder: {HOMEWORK_FOLDER_ID}")
    
    file_metadata = {
        'name': 'test_upload.txt',
        'parents': [HOMEWORK_FOLDER_ID]
    }
    
    file_content = b'This is a test file from Streamlit.'
    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    st.success(f"🎉 SUCCESS! Test file uploaded with ID: {file.get('id')}")
    st.balloons()
    st.info("Please check your 'Homework' folder in Google Drive to see 'test_upload.txt'.")

except Exception as e:
    st.error("❌ UPLOAD FAILED:")
    st.exception(e)
