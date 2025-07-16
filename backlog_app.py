import streamlit as st
import pandas as pd
import datetime
import math
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt

# ==== AUTH & SHEET SETUP ====
SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
CREDS = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(CREDS)
SHEET_ID = "1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI"
wb = client.open_by_key(SHEET_ID)

# Backlog sheet
try:
    ws = wb.worksheet("Backlog")
except gspread.exceptions.WorksheetNotFound:
    ws = wb.add_worksheet("Backlog", rows="100", cols="3")
    ws.append_row(["Subject","Number of Lectures","Last Updated"])

# History sheet
try:
    hist_ws = wb.worksheet("History")
except gspread.exceptions.WorksheetNotFound:
    hist_ws = wb.add_worksheet("History", rows="365", cols="2")
    hist_ws.append_row(["Date","Total Backlog"])

# ==== DATA LOAD/SAVE ====
@st.cache_data(ttl=0)
def load_backlog():
    df = pd.DataFrame(ws.get_all_records())
    expected = ["Subject","Number of Lectures","Last Updated"]
    if list(df.columns) != expected:
        ws.clear()
        ws.append_row(expected)
        return pd.DataFrame(columns=expected)
    return df

def save_backlog(df: pd.DataFrame):
    ws.clear()
    ws.append_row(list(df.columns))
    if not df.empty:
        ws.append_rows(df.values.tolist())
    st.cache_data.clear()

@st.cache_data(ttl=0)
def load_history():
    h = pd.DataFrame(hist_ws.get_all_records())
    expected = ["Date","Total Backlog"]
    if list(h.columns) != expected:
        hist_ws.clear()
        hist_ws.append_row(expected)
        return pd.DataFrame(columns=expected)
    return h

def log_history_if_needed(total: int):
    today = datetime.date.today().strftime("%Y-%m-%d")
    h = load_history()
    if h.empty or h["Date"].iloc[-1] != today:
        hist_ws.append_row([today, total])
        st.cache_data.clear()

# ==== BUSINESS LOGIC ====
def auto_increment_once(df: pd.DataFrame) -> pd.DataFrame:
    today = datetime.date.today()
    hist = load_history()
    # only once per day
    if not hist.empty and hist["Date"].iloc[-1] == today.strftime("%Y-%m-%d"):
        return df
    if today.weekday() == 6:  # Sunday
        return df

    changed = False
    for i, row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"], "%Y-%m-%d").date()
        days = (today - last).days
        inc = sum(1 for d in range(1, days+1)
                  if (last + datetime.timedelta(days=d)).weekday() != 6)
        if inc > 0:
            df.at[i, "Number of Lectures"] = int(row["Number of Lectures"]) + inc
            df.at[i, "Last Updated"] = today.strftime("%Y-%m-%d")
            changed = True

    if changed:
        save_backlog(df)
        log_history_if_needed(df["Number of Lectures"].sum())
    return df

def mark_done(df: pd.DataFrame, subject: str, done: int) -> pd.DataFrame:
    today = datetime.date.today()
    idx = df.index[df["Subject"] == subject][0]
    curr = int(df.at[idx, "Number of Lectures"])
    if today.weekday() == 6:  # Sunday: full
        new = max(0, curr - done)
    else:                     # Weekday: need done-1
        new = max(0, curr - (done - 1))
    df.at[idx, "Number of Lectures"] = new
    df.at[idx, "Last Updated"] = today.strftime("%Y-%m-%d")
    save_backlog(df)
    log_history_if_needed(df["Number of Lectures"].sum())
    st.success(f"{subject} updated by {done} lectures!")
    return df

def estimate(df: pd.DataFrame, pace: int) -> dict:
    net_weekly = pace * 7 - 6
    out = {}
    for _, r in df.iterrows():
        b = int(r["Number of Lectures"])
        days = math.inf if net_weekly <= 0 else math.ceil(b * 7 / net_weekly)
        out[r["Subject"]] = days
    return out

# ==== STREAMLIT UI ====
st.set_page_config(page_title="JEE Backlog", layout="centered")
st.title("📚 JEE Backlog Tracker")

# 1) Load & Sync
data = load_backlog()
data = auto_increment_once(data)

# 2) Mark Done
st.subheader("✅ Mark Lectures Done")
if data.empty:
    st.info("No subjects yet. Add below.")
else:
    c1, c2, c3 = st.columns([3,2,2])
    sub = c1.selectbox("Subject", data["Subject"])
    done = c2.number_input("Lectures done", min_value=0, step=1)
    if c3.button("Mark Done"):
        data = mark_done(data, sub, done)

st.markdown("---")

# 3) Force Sync
if st.button("🔄 Force Sync"):
    data = auto_increment_once(data)
    st.success("Force sync done!")

st.markdown("---")

# 4) Add Subject
st.subheader("➕ Add New Subject")
with st.form("add_form"):
    new_sub = st.text_input("Subject Name").strip()
    new_back = st.number_input("Starting Backlog", min_value=0, step=1)
    if st.form_submit_button("Add"):
        if not new_sub:
            st.warning("Enter a subject.")
        elif new_sub in data["Subject"].tolist():
            st.warning("Subject exists.")
        else:
            today = datetime.date.today().strftime("%Y-%m-%d")
            data = data.append({"Subject":new_sub, "Number of Lectures":int(new_back),
                                "Last Updated":today}, ignore_index=True)
            save_backlog(data)
            st.success(f"Added {new_sub}.")

st.markdown("---")

# 5) Graph & ETA
hist = load_history()
if hist.empty:
    st.info("No history yet.")
else:
    hist["Date"] = pd.to_datetime(hist["Date"])
    hist["Total Backlog"] = hist["Total Backlog"].astype(int)
    fig, ax = plt.subplots()
    ax.plot(hist["Date"], hist["Total Backlog"], marker="o")
    ax.set_title("Backlog Over Time"); ax.set_xlabel("Date"); ax.set_ylabel("Lectures")
    st.pyplot(fig)

st.subheader("⏱ Estimated Time to Clear Backlog")
pace = st.slider("Daily pace",1,10,1)
est = estimate(data, pace)
if est:
    df_est = pd.DataFrame([{"Subject":s,"Days":d,"Weeks":d//7} for s,d in est.items()])
    st.table(df_est)
else:
    st.info("Add subjects to estimate.")
