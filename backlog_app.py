import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import matplotlib.pyplot as plt

# ---- GOOGLE SHEETS AUTH ----
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Your sheet URL — already shared with your service account
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI/edit"
sheet = client.open_by_url(SHEET_URL).sheet1

# ---- STREAMLIT UI SETUP ----
st.set_page_config(page_title="📚 JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

# ---- LOAD DATA ----
try:
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
except:
    df = pd.DataFrame(columns=["Date", "Subject", "Completed"])

# ---- INPUT FORM ----
st.subheader("➕ Log Today's Progress")
subject = st.selectbox("Subject", ["Physics", "Chemistry", "Maths"])
completed = st.number_input("Lectures completed today", min_value=0, step=1)

if st.button("Submit"):
    today = datetime.date.today().isoformat()
    sheet.append_row([today, subject, completed])
    st.success(f"Progress saved: {subject} - {completed} lectures on {today}")

# ---- PROGRESS GRAPH ----
st.subheader("📈 Lecture Progress Over Time")

if not df.empty:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df_grouped = df.groupby("Date")["Completed"].sum().reset_index()

    fig, ax = plt.subplots()
    ax.plot(df_grouped["Date"], df_grouped["Completed"], marker="o", linestyle="-", color="teal")
    ax.set_title("Total Lectures Completed Per Day")
    ax.set_xlabel("Date")
    ax.set_ylabel("Lectures Completed")
    ax.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(fig)
else:
    st.info("No progress data yet. Log something above to see your graph!")

# ---- FOOTER ----
st.markdown("---")
st.caption("Built with ❤️ by you and your AI bro 🚀")
