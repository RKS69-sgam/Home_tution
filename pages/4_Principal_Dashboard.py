import streamlit as st
import pandas as pd
import gspread
import json
import base64
import plotly.express as px

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Principal Dashboard")

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
    MASTER_ANSWER_SHEET = client.open_by_key("16poJSlKbTiezSG119QapoCVcjmAOicsJlyaeFpCKGd8").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(_sheet):
    """
    Loads all data from a Google Sheet and correctly assigns the first row as the header.
    """
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df.columns = df.columns.str.strip()
    df['Row ID'] = range(2, len(df) + 2)
    return df

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "principal":
    st.error("You must be logged in as a Principal to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === PRINCIPAL DASHBOARD UI ===
st.header("🏛️ Principal Dashboard")

# --- DEBUGGING CODE START ---
# This block will run first to show you what the app is reading.
st.warning("RUNNING DEBUG TEST FOR MASTER_ANSWER_SHEET")
try:
    df_answers_debug = load_data(MASTER_ANSWER_SHEET)
    st.write("Columns found in MASTER_ANSWER_SHEET:")
    st.write(list(df_answers_debug.columns))
except Exception as e:
    st.error("An error occurred while reading the sheet for debugging:")
    st.exception(e)
st.stop()
# --- DEBUGGING CODE END ---


# The real dashboard code is below.
# Once the error is fixed, you can remove the debugging block above.

tab1, tab2 = st.tabs(["Send Instructions to Teachers", "View Reports"])

with tab1:
    # ... (Send Instructions Logic) ...

with tab2:
    # ... (View Reports Logic) ...
