import streamlit as st
import base64, json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Google Auth Setup
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
decoded = base64.b64decode(st.secrets["google_service"]["base64_credentials"]).decode("utf-8")
credentials_dict = json.loads(decoded)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)

# Function to test Sheet Access
def generate_letter():
    try:
        sheet = client.open_by_key("1aCnuMxOlsJ3VkleK4wgTvMx2Sp-9pAMH")
        st.success("✅ Sheet Accessed Successfully")

        data = sheet.sheet1.get_all_records()
        df = pd.DataFrame(data)
        st.write("📋 Sheet Data:", df)

    except Exception as e:
        st.error(f"❌ Error: {e}")

# Streamlit Button
if st.button("Test Sheet Access"):
    generate_letter()