import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt

# ---- AUTH ----
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CREDS = Credentials.from_service_account_info(
    st.secrets["google_service_account"], scopes=SCOPES
)
client = gspread.authorize(CREDS)

# ---- CONFIG ----
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI"
sheet = client.open_by_url(SHEET_URL)

# Worksheet: Main data
try:
    ws = sheet.worksheet("Backlog")
except:
    ws = sheet.add_worksheet(title="Backlog", rows="100", cols="3")
    ws.update("A1:C1", [["Subject", "Number of Lectures", "Last Updated"]])

# Worksheet: History for graph
try:
    hist_ws = sheet.worksheet("History")
except:
    hist_ws = sheet.add_worksheet(title="History", rows="1000", cols="2")
    hist_ws.update("A1:B1", [["Date", "Total Backlog"]])

def load_data():
    data = pd.DataFrame(ws.get_all_records())
    return data

def save_data(df):
    ws.update("A2", df.values.tolist())

def auto_increment(df):
    today = datetime.date.today()
    if today.weekday() == 6:  # Sunday (0=Monday, ..., 6=Sunday)
        return df  # No increment on Sundays

    for i in range(len(df)):
        last_update = datetime.datetime.strptime(df.loc[i, "Last Updated"], "%Y-%m-%d").date()
        days_missed = (today - last_update).days
        missed_days = [
            last_update + datetime.timedelta(days=x+1)
            for x in range(days_missed)
        ]
        inc_count = sum(1 for d in missed_days if d.weekday() != 6)
        df.loc[i, "Number of Lectures"] += inc_count
        df.loc[i, "Last Updated"] = today.strftime("%Y-%m-%d")

    return df

def log_history(df):
    today = datetime.date.today().strftime("%Y-%m-%d")
    total = df["Number of Lectures"].sum()
    hist_df = pd.DataFrame(hist_ws.get_all_records())
    if hist_df.empty or hist_df["Date"].iloc[-1] != today:
        hist_ws.append_row([today, total])

def estimate_days_left(df, hist_df):
    if hist_df.shape[0] < 2:
        return "Insufficient data for estimate"

    # Calculate average lectures reduced per day
    hist_df["Total Backlog"] = hist_df["Total Backlog"].astype(int)
    hist_df["Date"] = pd.to_datetime(hist_df["Date"])
    hist_df = hist_df.sort_values("Date")

    days = (hist_df["Date"].iloc[-1] - hist_df["Date"].iloc[0]).days
    if days == 0:
        return "Insufficient time span"

    reduced = hist_df["Total Backlog"].iloc[0] - hist_df["Total Backlog"].iloc[-1]
    avg_per_day = reduced / days if days > 0 else 0.00001  # prevent div0

    remaining = df["Number of Lectures"].sum()
    if avg_per_day == 0:
        return "No progress yet"

    est_days = int(remaining / avg_per_day)
    est_weeks = est_days // 7
    return f"At current pace, approx. {est_days} days ({est_weeks} weeks) to clear backlog."

# --- UI ---
st.title("📚 JEE Backlog Tracker")
data = load_data()
data = auto_increment(data)
save_data(data)
log_history(data)

st.subheader("Your Subjects")
for i in range(len(data)):
    col1, col2, col3 = st.columns([3, 3, 4])
    with col1:
        st.text(data.loc[i, "Subject"])
    with col2:
        st.text(f'📈 {data.loc[i, "Number of Lectures"]} lectures')
    with col3:
        if st.button(f"✅ Mark as Done ({data.loc[i, 'Subject']})", key=f"done_{i}"):
            today = datetime.date.today()
            if today.weekday() == 6:  # Sunday
                data.loc[i, "Number of Lectures"] = max(data.loc[i, "Number of Lectures"] - 1, 0)
            else:
                data.loc[i, "Number of Lectures"] = max(data.loc[i, "Number of Lectures"] - 2, 0)
            data.loc[i, "Last Updated"] = today.strftime("%Y-%m-%d")
            save_data(data)
            st.experimental_rerun()

# Force Sync
if st.button("🔁 Force Sync"):
    data = auto_increment(data)
    save_data(data)
    log_history(data)
    st.success("Synced successfully!")
    st.experimental_rerun()

# Add subject
st.subheader("➕ Add New Subject")
with st.form("add_subject"):
    new_sub = st.text_input("Subject Name")
    new_lectures = st.number_input("Starting Backlog", min_value=0, value=0)
    submitted = st.form_submit_button("Add")
    if submitted:
        today = datetime.date.today().strftime("%Y-%m-%d")
        if new_sub in data["Subject"].values:
            st.warning("Subject already exists.")
        else:
            new_row = pd.DataFrame([[new_sub, int(new_lectures), today]], columns=["Subject", "Number of Lectures", "Last Updated"])
            data = pd.concat([data, new_row], ignore_index=True)
            save_data(data)
            st.success("Subject added!")
            st.experimental_rerun()

# Graph
st.subheader("📊 Backlog Over Time")
hist_data = pd.DataFrame(hist_ws.get_all_records())
if not hist_data.empty:
    hist_data["Date"] = pd.to_datetime(hist_data["Date"])
    hist_data["Total Backlog"] = hist_data["Total Backlog"].astype(int)
    fig, ax = plt.subplots()
    ax.plot(hist_data["Date"], hist_data["Total Backlog"], marker="o", linestyle="-", color="blue")
    ax.set_xlabel("Date")
    ax.set_ylabel("Total Backlog")
    ax.set_title("Backlog Trend")
    st.pyplot(fig)

# Estimate
st.subheader("📅 Estimated Time to Clear Backlog")
estimate = estimate_days_left(data, hist_data)
st.info(estimate)
