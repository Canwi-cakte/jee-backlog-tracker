import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import datetime
import matplotlib.pyplot as plt

# ---- GOOGLE SHEETS AUTH ----
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(CREDS)

# ---- CONFIG ----
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI/edit"
SHEET = client.open_by_url(SHEET_URL)
DATA_SHEET = SHEET.worksheet("Backlog")
LOG_SHEET = SHEET.worksheet("Log")

# ---- INIT ----
def init_sheets():
    if DATA_SHEET.row_count < 2:
        DATA_SHEET.append_row(["Subject", "Lectures", "Last Updated"])
    if LOG_SHEET.row_count < 2:
        LOG_SHEET.append_row(["Date", "Total Backlog", "Lectures Done"])

init_sheets()

# ---- FETCH DATA ----
def fetch_data():
    data = DATA_SHEET.get_all_records()
    return pd.DataFrame(data)

def save_data(df):
    DATA_SHEET.clear()
    DATA_SHEET.append_row(["Subject", "Lectures", "Last Updated"])
    DATA_SHEET.append_rows(df.values.tolist())

# ---- AUTO SYNC ----
def sync_backlog(df):
    today = datetime.date.today()
    for i in range(len(df)):
        last = datetime.datetime.strptime(df.loc[i, "Last Updated"], "%Y-%m-%d").date()
        missed_days = [last + datetime.timedelta(days=x+1) for x in range((today - last).days)]
        missed_days = [d for d in missed_days if d.weekday() != 6]  # exclude Sundays
        df.loc[i, "Lectures"] += len(missed_days)
        df.loc[i, "Last Updated"] = str(today)
    return df

# ---- MARK AS DONE ----
def mark_done(subject, df):
    today = datetime.date.today()
    lectures_done = st.session_state.get(f"done_{subject}", 0)
    for i in range(len(df)):
        if df.loc[i, "Subject"] == subject:
            if today.weekday() == 6:  # Sunday
                df.loc[i, "Lectures"] = max(0, df.loc[i, "Lectures"] - lectures_done)
            else:
                df.loc[i, "Lectures"] = max(0, df.loc[i, "Lectures"] - max(0, lectures_done - 1))
            break
    log_today(lectures_done)
    return df

# ---- FORCE SYNC ----
def force_sync(df):
    return sync_backlog(df)

# ---- LOGGING ----
def log_today(lectures_done):
    today = str(datetime.date.today())
    backlog = fetch_data()["Lectures"].sum()
    LOG_SHEET.append_row([today, backlog, lectures_done])

# ---- ESTIMATE ----
def estimate_days():
    log_df = pd.DataFrame(LOG_SHEET.get_all_records())
    if len(log_df) < 2:
        return "Need more data to estimate!"
    
    # compute total lectures done, excluding zeros
    total_done = log_df["Lectures Done"].sum()
    total_days = len(log_df)

    if total_days == 0 or total_done == 0:
        return "No lectures logged yet!"

    avg_per_day = total_done / total_days
    backlog = fetch_data()["Lectures"].sum()

    # Calculate effective reduction rate:
    # Weekdays: need 2 to reduce by 1
    # Sundays: 1:1
    # Assuming 1 Sunday in every 7 days
    sunday_ratio = 1 / 7
    weekday_ratio = 6 / 7
    effective_rate = (sunday_ratio * avg_per_day) + (weekday_ratio * (avg_per_day - 1) / 2)

    if effective_rate <= 0:
        return "Backlog increasing! 🫠"
    days_needed = backlog / effective_rate
    return f"At current pace: {int(days_needed)} days (~{int(days_needed//7)} weeks)"

# ---- GRAPH ----
def plot_graph():
    df = pd.DataFrame(LOG_SHEET.get_all_records())
    if df.empty:
        st.warning("No data to show yet!")
        return

    df["Date"] = pd.to_datetime(df["Date"])
    df["Backlog"] = df["Total Backlog"]
    df = df.sort_values("Date")

    plt.figure(figsize=(10, 4))
    plt.plot(df["Date"], df["Backlog"], marker='o')
    plt.title("Backlog Over Time")
    plt.xlabel("Date")
    plt.ylabel("Total Backlog")
    st.pyplot(plt)

# ---- UI ----
st.title("📚 JEE Backlog Tracker")

data = fetch_data()
data = sync_backlog(data)

# Add Subject
with st.form("add_form"):
    sub = st.text_input("📌 Subject Name")
    lec = st.number_input("🎥 No. of Lectures", min_value=1, step=1)
    submitted = st.form_submit_button("Add Subject")
    if submitted:
        if not data.empty and "Subject" in data.columns and sub in data["Subject"].values:
            # subject exists — update it
            idx = data.index[data["Subject"] == sub][0]
            data.at[idx, "Lectures"] = int(data.at[idx, "Lectures"]) + lectures
        else:
            # new subject — add it
            data.loc[len(data)] = [sub, lectures, today.strftime("%Y-%m-%d")]


# Display Subjects
for i in range(len(data)):
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    with col1:
        st.write(f"📘 {data.loc[i, 'Subject']}")
    with col2:
        st.write(f"📊 {int(data.loc[i, 'Lectures'])} lectures")
    with col3:
        st.number_input("✅ Lectures done", min_value=0, key=f"done_{data.loc[i, 'Subject']}")
    with col4:
        if st.button("Mark as Done", key=f"btn_{data.loc[i, 'Subject']}"):
            data = mark_done(data.loc[i, "Subject"], data)

# Force Sync
if st.button("🔄 Force Sync"):
    data = force_sync(data)
    st.success("Synced!")

save_data(data)

# Graph & ETA
st.subheader("📈 Backlog History")
plot_graph()

st.subheader("⏳ Estimated Time to Clear Backlog")
st.info(estimate_days())
