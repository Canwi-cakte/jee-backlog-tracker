import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- Google Sheets Setup ---
SHEET_NAME = "JEE_Backlog_Tracker"  # Change if your sheet name is different

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Get or create sheet
try:
    sheet = client.open(SHEET_NAME).sheet1
except:
    sheet = client.create(SHEET_NAME).sheet1
    sheet.append_row(["Subject", "Backlog", "Completed", "Last Updated"])

# Convert sheet to DataFrame
def get_df():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_df(df):
    sheet.clear()
    sheet.append_row(["Subject", "Backlog", "Completed", "Last Updated"])
    for row in df.values.tolist():
        sheet.append_row(row)

# Auto increment backlog by 1 each day (except Sundays)
def auto_increment(df):
    today = datetime.now().date()
    for i in df.index:
        last = datetime.strptime(df.at[i, "Last Updated"], "%Y-%m-%d").date()
        days_passed = (today - last).days
        for j in range(days_passed):
            day = last + timedelta(days=j+1)
            if day.weekday() != 6:  # not Sunday
                df.at[i, "Backlog"] += 1
        df.at[i, "Last Updated"] = today.strftime("%Y-%m-%d")
    return df

# Initialize
st.set_page_config(page_title="📚 Backlog Tracker", page_icon="📈", layout="centered")
st.title("📚 JEE Backlog Tracker")
st.markdown("> Stay consistent. Clear backlogs. Become a topper. 🚀")

df = get_df()
if not df.empty:
    df = auto_increment(df)
    save_df(df)

# Add subject
with st.expander("➕ Add New Subject"):
    col1, col2 = st.columns(2)
    with col1:
        subject = st.text_input("Subject name")
    with col2:
        lectures = st.number_input("Initial backlog lectures", min_value=0, step=1)
    if st.button("Add Subject"):
        if subject.strip() == "" or subject in df["Subject"].values:
            st.warning("Enter a valid and unique subject.")
        else:
            new_row = pd.DataFrame([[subject, lectures, 0, datetime.now().date().strftime("%Y-%m-%d")]],
                                   columns=["Subject", "Backlog", "Completed", "Last Updated"])
            df = pd.concat([df, new_row], ignore_index=True)
            save_df(df)
            st.success(f"{subject} added with {lectures} backlog lectures.")

# Update progress
if not df.empty:
    st.subheader("📅 Update Daily Progress")
    col1, col2 = st.columns(2)
    with col1:
        subject = st.selectbox("Select Subject", df["Subject"])
    with col2:
        done = st.number_input("Lectures completed today", min_value=0, step=1)
    
    if st.button("Update Progress"):
        idx = df[df["Subject"] == subject].index[0]
        df.at[idx, "Completed"] += done
        df.at[idx, "Backlog"] = max(0, df.at[idx, "Backlog"] - done)
        df.at[idx, "Last Updated"] = datetime.now().date().strftime("%Y-%m-%d")
        save_df(df)
        st.success(f"{done} lecture(s) marked completed for {subject}.")

# Graph section
if not df.empty:
    st.subheader("📊 Time to Clear Backlogs")

    pace = st.slider("Select your daily lecture pace", 1, 10, 1)

    df["Days to Clear"] = df["Backlog"].apply(lambda b: (b // pace) + (1 if b % pace != 0 else 0))

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(df["Subject"], df["Days to Clear"], color='lightgreen')
    ax.set_ylabel("Estimated Days")
    ax.set_title("⏳ Backlog Completion Estimate")
    st.pyplot(fig)

    st.subheader("📋 Backlog Table")
    st.dataframe(df[["Subject", "Backlog", "Completed", "Last Updated"]], use_container_width=True)

else:
    st.info("No subjects added yet. Start by adding one above.")
