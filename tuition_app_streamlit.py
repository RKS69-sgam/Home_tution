import streamlit as st
import json
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.title("Google File Permission Test 🕵️")

# --- IMPORTANT: Paste your Student Answer Sheet Template ID here ---
TEMPLATE_SHEET_ID = "YOUR_STUDENT_ANSWER_SHEET_TEMPLATE_ID_HERE" 

try:
    # 1. Load credentials
    st.info("Loading credentials...")
    scopes = ["https://www.googleapis.com/auth/drive"] 
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    drive_service = build("drive", "v3", credentials=credentials)
    st.success("✅ Credentials loaded.")

    # 2. Try to get the file's metadata and permissions
    st.info(f"Attempting to get permissions for file ID: {TEMPLATE_SHEET_ID}")
    
    file_metadata = drive_service.files().get(
        fileId=TEMPLATE_SHEET_ID,
        fields='permissions, owners',
        supportsAllDrives=True
    ).execute()

    st.success("🎉 SUCCESS! Successfully retrieved file metadata.")
    
    st.subheader("Permissions Found on This File:")
    permissions = file_metadata.get('permissions', [])
    owner = file_metadata.get('owners', [{}])[0].get('emailAddress')
    st.write(f"**File Owner:** {owner}")

    found_sa_permission = False
    for p in permissions:
        email = p.get('emailAddress')
        role = p.get('role')
        st.write(f"- **Email:** {email if email else 'Anyone with link'}, **Role:** {role}")
        
        if email == credentials.service_account_email:
            found_sa_permission = True
            if role == 'writer' or role == 'editor':
                st.success("✅ Correct 'Editor/Writer' permission found for your service account!")
            else:
                st.error(f"❌ WRONG PERMISSION: Service account has role '{role}', but needs 'Editor' or 'Writer'.")

    if not found_sa_permission and credentials.service_account_email != owner:
        st.error("❌ PERMISSION NOT FOUND: Your service account's email was not found in the sharing list for this file.")

except Exception as e:
    st.error("❌ TEST FAILED:")
    st.exception(e)
