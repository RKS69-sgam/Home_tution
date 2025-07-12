# engine_card_pass.py

import pandas as pd
from datetime import date
import streamlit as st
from generate_word import generate_word, download_word  # Adjust as per your codebase

def handle_engine_card_pass(letter_type):
    class_file = "Class-III (PWisDetails).xlsx"
    class_df = pd.read_excel(class_file, sheet_name="Sheet1")
    class_df["Display"] = class_df.apply(lambda r: f"{r['PF No.']} - {r['HRMS ID']} - {r.name+1} - {r['Employee Name']}", axis=1)

    st.subheader(f"{letter_type}")
    selected_emp = st.selectbox("Select Employee", class_df["Display"])
    letter_date = st.date_input("Letter Date", value=date.today(), key=letter_type)

    selected_row = class_df[class_df["Display"] == selected_emp].iloc[0]

    context = {
        "EmployeeName": selected_row["Employee Name"],
        "Designation": selected_row["Designation"],
        "PFNumber": selected_row["PF No."],
        "DOR": pd.to_datetime(selected_row["DOR"]).strftime("%d-%m-%Y") if pd.notnull(selected_row["DOR"]) else "",
        "LetterDate": letter_date
    }

    if st.button("Generate Letter"):
        if letter_type == "Engine Pass Letter":
            template_path = "assets/Engine Pass letter temp.docx"
            save_name = f"EnginePass-{context['EmployeeName'].strip()}.docx"
            col_to_update = "Engine Pass Renewal Application Date"
        else:
            template_path = "assets/Card Pass letter temp.docx"
            save_name = f"CardPass-{context['EmployeeName'].strip()}.docx"
            col_to_update = "Card Pass Renewal Application Date"

        word_path = generate_word(template_path, context, save_name)
        download_word(word_path)
        st.success("Letter generated successfully.")

        row_index = class_df[class_df["Display"] == selected_emp].index[0]
        class_df.at[row_index, col_to_update] = letter_date.strftime("%d-%m-%Y")
        class_df.drop(columns=["Display"], inplace=True, errors="ignore")
        class_df.to_excel(class_file, sheet_name="Sheet1", index=False)
        st.success("Register updated.")