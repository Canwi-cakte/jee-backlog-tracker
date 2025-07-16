import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ---- GOOGLE SHEETS SETUP ----
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials from Streamlit secrets
CREDS = Credentials.from_service_account_info(
    st.secrets["google_service_account"],
    scopes=SCOPES
)
client = gspread.authorize(CREDS)

# Your sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI/edit"
sheet = client.open_by_url(SHEET_URL).sheet1

# ---- STREAMLIT UI SETUP ----
st.set_page_config(page_title="📚 JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

# ---- HELPER FUNCTIONS ----
def fetch_data():
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def save_new_row(subject, topic, date, status):
    sheet.append_row([subject, topic, date, status])

def update_status(index, new_status):
    sheet.update_cell(index + 2, 4, new_status)  # +2 because of header row

def clear_all_rows():
    sheet.resize(rows=1)

# ---- MAIN TABS ----
tabs = st.tabs(["➕ Add Backlog", "📋 View & Update", "🗑 Clear All"])

# ---- TAB 1: ADD BACKLOG ----
with tabs[0]:
    st.header("➕ Add New Backlog Topic")
    subj = st.selectbox("Subject", ["Physics", "Chemistry", "Maths"])
    topic = st.text_input("Topic")
    date = st.date_input("Date", value=datetime.now()).strftime("%Y-%m-%d")
    status = st.selectbox("Status", ["Pending", "Completed"])

    if st.button("✅ Add to Tracker"):
        if topic.strip() == "":
            st.warning("Topic name can't be empty!")
        else:
            save_new_row(subj, topic, date, status)
            st.success("Backlog added!")

# ---- TAB 2: VIEW / UPDATE ----
with tabs[1]:
    st.header("📋 Your Backlog")
    df = fetch_data()

    if df.empty:
        st.info("No backlog yet. Add something first!")
    else:
        df_display = df.copy()
        status_options = ["Pending", "Completed"]

        edited_rows = []
        for i in range(len(df)):
            col1, col2, col3, col4 = st.columns([2, 4, 3, 3])
            with col1:
                st.text(df["Subject"][i])
            with col2:
                st.text(df["Topic"][i])
            with col3:
                st.text(df["Date"][i])
            with col4:
                new_status = st.selectbox(
                    f"Status {i+1}", status_options, index=status_options.index(df["Status"][i]), key=f"status_{i}"
                )
                if new_status != df["Status"][i]:
                    edited_rows.append((i, new_status))

        if st.button("💾 Save Changes"):
            for idx, new_stat in edited_rows:
                update_status(idx, new_stat)
            st.success("Changes saved!")

# ---- TAB 3: CLEAR ALL ----
with tabs[2]:
    st.header("⚠️ Clear All Backlogs")
    if st.button("🗑 Clear All Data"):
        clear_all_rows()
        st.success("All backlog data cleared.")
