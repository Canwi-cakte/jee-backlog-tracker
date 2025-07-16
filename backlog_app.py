import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta

# ---- AUTH ----
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS = Credentials.from_service_account_info(
    st.secrets["google_service_account"], scopes=SCOPES
)
client = gspread.authorize(CREDS)

# ---- CONFIG ----
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI/edit"
SHEET = client.open_by_url(SHEET_URL).sheet1

# ---- FUNCTIONS ----
def get_data():
    try:
        data = SHEET.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=["Subject", "Lectures", "Last Updated"])

def save_data(df):
    SHEET.clear()
    SHEET.append_row(["Subject", "Lectures", "Last Updated"])
    for _, row in df.iterrows():
        SHEET.append_row(list(row))

def auto_increment(df):
    today = datetime.now().date()
    is_sunday = today.weekday() == 6  # 6 = Sunday

    for idx, row in df.iterrows():
        last_updated = datetime.strptime(row["Last Updated"], "%Y-%m-%d").date()
        days_passed = (today - last_updated).days

        # Add +1 for each day passed, skip Sundays
        if days_passed > 0:
            increment_days = 0
            for i in range(1, days_passed + 1):
                if (last_updated + timedelta(days=i)).weekday() != 6:
                    increment_days += 1
            df.at[idx, "Lectures"] = int(row["Lectures"]) + increment_days
            df.at[idx, "Last Updated"] = str(today)

    return df

# ---- MAIN APP ----
st.set_page_config(page_title="📚 JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

df = get_data()

if not df.empty:
    df = auto_increment(df)
    save_data(df)

st.subheader("Add New Subject")
subject = st.text_input("Subject Name")
lectures = st.number_input("Number of Lectures", min_value=0, step=1)

if st.button("➕ Add Subject"):
    if subject.strip() == "":
        st.warning("Enter a subject name.")
    elif subject in df["Subject"].values:
        st.warning("Subject already exists.")
    else:
        new_row = pd.DataFrame([{
            "Subject": subject,
            "Lectures": int(lectures),
            "Last Updated": str(datetime.now().date())
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.success(f"Subject '{subject}' added!")

st.divider()
st.subheader("📈 Current Backlog")

if df.empty:
    st.info("No data yet. Add some subjects to get started!")
else:
    for _, row in df.iterrows():
        st.markdown(f"**{row['Subject']}** — `{row['Lectures']} lectures`")

