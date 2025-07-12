import streamlit as st
import pandas as pd
import os
import base64
from docx import Document
from datetime import date, timedelta
import datetime
from docx.shared import Inches
from generate_word import
handle_generate_word
from download_word
handle_download_word
os.makedirs("generated_homework",exist_ok=True)
template_files = {"STD-VI Homework": "Homework/6TH/date.today()",
                 "STD-VIII Homework": "Homework/8TH/date.today()",
                 "STD-IX Homework": "Homework/9TH/date.today()"}
# Date Input
homework_date = st.date_input("Select Date", date.today())
#student details from excel
student_file = "StudentMaster.xlsx"
homework_df = pd.read_excel(student_file, sheet_name="Sheet1")

