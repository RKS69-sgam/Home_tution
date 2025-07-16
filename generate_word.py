import streamlit as st

def generate_letter():
    try:
       sheet = client.open_by_key("1aCnuMxOlsJ3VkleK4wgTvMx2Sp-9pAMH")
       st.success("✅ Sheet Accessed Successfully")
except Exception as e:
    st.error(f"❌ Error: {e}")