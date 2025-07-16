import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials

# ---- GOOGLE SHEETS SETUP ----
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDS = Credentials.from_service_account_file("creds.json", scopes=SCOPE)
client = gspread.authorize(CREDS)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI/edit"
sheet = client.open_by_url(SHEET_URL).sheet1

# ---- INITIALIZE SHEET IF EMPTY ----
def initialize_sheet():
    existing = sheet.get_all_records()
    if not existing:
        sheet.append_row(["Date", "Subject", "Total Backlog", "Completed Today"])

initialize_sheet()

# ---- STREAMLIT UI SETUP ----
st.set_page_config(page_title="📚 JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")
st.markdown("Track your daily progress and backlog automatically!")

# ---- USER INPUT ----
subject = st.text_input("Enter Subject")
total_backlog = st.number_input("Total backlog lectures", min_value=0, step=1)
completed_today = st.number_input("Lectures completed today", min_value=0, step=1)

# ---- TODAY'S DATE ----
today = datetime.date.today()
day_name = today.strftime('%A')

# ---- SUBMIT BUTTON ----
if st.button("➕ Add Entry"):
    if subject:
        sheet.append_row([str(today), subject, total_backlog, completed_today])
        st.success(f"Added progress for {subject}")
    else:
        st.error("Please enter a subject")

# ---- FETCH DATA ----
data = pd.DataFrame(sheet.get_all_records())
if not data.empty:
    data["Date"] = pd.to_datetime(data["Date"])
    st.subheader("📊 Your Progress")

    # Auto-Increase Backlog +1 each day (except Sunday)
    if day_name != "Sunday":
        for sub in data["Subject"].unique():
            today_entries = data[(data["Subject"] == sub) & (data["Date"] == pd.Timestamp(today))]
            if today_entries.empty:
                sheet.append_row([str(today), sub, 1, 0])  # +1 backlog, 0 done

    # Calculate remaining backlog per subject
    progress = data.groupby("Subject").agg({
        "Total Backlog": "sum",
        "Completed Today": "sum"
    })
    progress["Remaining"] = progress["Total Backlog"] - progress["Completed Today"]
    st.dataframe(progress)

    # ---- PLOT PROGRESS ----
    st.subheader("📈 Estimated Finish Time")
    fig, ax = plt.subplots()
    for subject in progress.index:
        remaining = progress.loc[subject, "Remaining"]
        if remaining <= 0:
            continue
        pace = data[data["Subject"] == subject]["Completed Today"].mean()
        pace = pace if pace > 0 else 1  # Avoid divide by zero
        days_left = int(remaining / pace)
        ax.bar(subject, days_left)
    ax.set_ylabel("Estimated Days to Finish Backlog")
    st.pyplot(fig)
else:
    st.info("Add your first entry to start tracking!")

st.markdown("---")
st.caption("Made with ❤️ by your AI bro who's totally not judging your backlog... much.")
