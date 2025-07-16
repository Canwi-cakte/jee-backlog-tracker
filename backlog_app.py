import streamlit as st
import pandas as pd
import datetime
import math
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt

# ==== AUTH & SHEET SETUP ====
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(CREDS)

SHEET_ID = "1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI"
wb = client.open_by_key(SHEET_ID)

# Backlog worksheet
try:
    ws = wb.worksheet("Backlog")
except gspread.exceptions.WorksheetNotFound:
    ws = wb.add_worksheet(title="Backlog", rows="100", cols="3")
    ws.append_row(["Subject","Number of Lectures","Last Updated"])

# History worksheet
try:
    hist_ws = wb.worksheet("History")
except gspread.exceptions.WorksheetNotFound:
    hist_ws = wb.add_worksheet(title="History", rows="365", cols="2")
    hist_ws.append_row(["Date","Total Backlog"])

# ==== DATA LOAD ====
@st.cache_data(ttl=0)
def load_backlog():
    df = pd.DataFrame(ws.get_all_records())
    # Ensure headers
    expected = ["Subject","Number of Lectures","Last Updated"]
    if list(df.columns) != expected:
        ws.batch_clear(["A1:C1"])
        ws.append_row(expected)
        return pd.DataFrame(columns=expected)
    return df

@st.cache_data(ttl=0)
def load_history():
    h = pd.DataFrame(hist_ws.get_all_records())
    expected = ["Date","Total Backlog"]
    if list(h.columns) != expected:
        hist_ws.batch_clear(["A1:B1"])
        hist_ws.append_row(expected)
        return pd.DataFrame(columns=expected)
    return h

def log_history_if_needed(total_backlog:int):
    today = datetime.date.today().strftime("%Y-%m-%d")
    hist = load_history()
    if hist.empty or hist["Date"].iloc[-1] != today:
        hist_ws.append_row([today, int(total_backlog)])
        st.cache_data.clear()

# ==== LOGIC ====
def auto_increment_once(df):
    today = datetime.date.today()
    hist = load_history()
    # Only once per day
    if not hist.empty and hist["Date"].iloc[-1] == today.strftime("%Y-%m-%d"):
        return df
    # Skip Sundays
    if today.weekday() == 6:
        return df

    for i, row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"], "%Y-%m-%d").date()
        days_passed = (today - last).days
        inc = sum(1 for d in range(1, days_passed+1)
                  if (last + datetime.timedelta(days=d)).weekday() != 6)
        if inc > 0:
            new_val = int(row["Number of Lectures"]) + inc
            # Update cells: Lectures (col B), Last Updated (col C)
            row_num = i + 2
            ws.update_cell(row_num, 2, new_val)
            ws.update_cell(row_num, 3, today.strftime("%Y-%m-%d"))
    # Log history after all updates
    df = load_backlog()
    log_history_if_needed(df["Number of Lectures"].sum())
    return df

def mark_done(df, subject, done):
    today = datetime.date.today()
    idx = df.index[df["Subject"] == subject][0]
    curr = int(df.at[idx, "Number of Lectures"])
    if today.weekday() == 6:   # Sunday
        new = max(0, curr - done)
    else:                      # Weekday
        new = max(0, curr - (done - 1))
    row_num = idx + 2
    ws.update_cell(row_num, 2, new)
    ws.update_cell(row_num, 3, today.strftime("%Y-%m-%d"))
    df = load_backlog()
    log_history_if_needed(df["Number of Lectures"].sum())
    st.cache_data.clear()
    st.success(f"{subject} updated by {done} lectures!")
    return df

def estimate(df, pace):
    net_weekly = pace*7 - 6
    out = {}
    for _, r in df.iterrows():
        b = int(r["Number of Lectures"])
        days = math.inf if net_weekly <= 0 else math.ceil(b*7 / net_weekly)
        out[r["Subject"]] = days
    return out

# ==== STREAMLIT UI ====
st.set_page_config(page_title="JEE Backlog", layout="centered")
st.title("📚 JEE Backlog Tracker")

# 1) Load & Auto‐Sync
data = load_backlog()
data = auto_increment_once(data)

# 2) Mark as Done
st.subheader("✅ Mark Lectures Done")
if data.empty:
    st.info("No subjects yet. Add one below.")
else:
    c1, c2, c3 = st.columns([3,2,2])
    sub = c1.selectbox("Subject", data["Subject"])
    done = c2.number_input("Lectures done", 0, step=1)
    if c3.button("Mark Done"):
        data = mark_done(data, sub, done)

st.markdown("---")

# 3) Force Sync
if st.button("🔄 Force Sync"):
    data = auto_increment_once(data)
    st.success("Force sync complete.")

st.markdown("---")

# 4) Add New Subject
st.subheader("➕ Add New Subject")
with st.form("add"):
    new_sub = st.text_input("Subject Name").strip()
    new_back = st.number_input("Starting Backlog", min_value=0, step=1)
    if st.form_submit_button("Add"):
        if not new_sub:
            st.warning("Enter a subject.")
        elif new_sub in data["Subject"].tolist():
            st.warning("Subject already exists.")
        else:
            today = datetime.date.today().strftime("%Y-%m-%d")
            ws.append_row([new_sub, int(new_back), today])
            st.success(f"Added {new_sub}.")
            st.cache_data.clear()

st.markdown("---")

# 5) History Graph & ETA
hist = load_history()
if hist.empty:
    st.info("No history to plot yet.")
else:
    hist["Date"] = pd.to_datetime(hist["Date"])
    hist["Total Backlog"] = hist["Total Backlog"].astype(int)
    fig, ax = plt.subplots()
    ax.plot(hist["Date"], hist["Total Backlog"], marker="o", linestyle="-")
    ax.set_title("Backlog Over Time")
    ax.set_xlabel("Date"); ax.set_ylabel("Lectures")
    st.pyplot(fig)

st.subheader("⏱ Estimated Time to Clear Backlog")
pace = st.slider("Daily pace (lectures/day)", 1, 10, 1)
est = estimate(data, pace)
if est:
    df_est = pd.DataFrame([{"Subject":s,"Days":d,"Weeks":d//7} for s,d in est.items()])
    st.table(df_est)
else:
    st.info("No subjects to estimate yet.")
