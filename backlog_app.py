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

# Ensure Backlog sheet exists with correct header
try:
    ws = wb.worksheet("Backlog")
except gspread.exceptions.WorksheetNotFound:
    ws = wb.add_worksheet("Backlog", rows="200", cols="3")
    ws.append_row(["Subject","Number of Lectures","Last Updated"])

# ==== HELPERS ====
def load_backlog() -> pd.DataFrame:
    df = pd.DataFrame(ws.get_all_records())
    expected = ["Subject","Number of Lectures","Last Updated"]
    if list(df.columns) != expected:
        ws.clear()
        ws.append_row(expected)
        return pd.DataFrame(columns=expected)
    return df

def save_backlog(df: pd.DataFrame):
    # Rewrite entire sheet from df
    ws.clear()
    ws.append_row(list(df.columns))
    for row in df.itertuples(index=False, name=None):
        ws.append_row(list(row))
    # clear cache so UI reloads fresh
    st.cache_data.clear()

# Sunday logic: +1 per missed non-Sunday day
def auto_increment(df: pd.DataFrame) -> pd.DataFrame:
    today = datetime.date.today()
    # Only increment if last updated < today and not Sunday
    if today.weekday() == 6:
        return df
    changed = False
    for i, row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"], "%Y-%m-%d").date()
        days = (today - last).days
        if days > 0:
            inc = sum(
                1 for d in range(1, days+1)
                if (last + datetime.timedelta(days=d)).weekday() != 6
            )
            if inc > 0:
                df.at[i, "Number of Lectures"] = int(row["Number of Lectures"]) + inc
                df.at[i, "Last Updated"] = today.strftime("%Y-%m-%d")
                changed = True
    if changed:
        save_backlog(df)
    return df

def mark_done(df: pd.DataFrame, subject: str, done: int) -> pd.DataFrame:
    today = datetime.date.today()
    idx = df.index[df["Subject"] == subject][0]
    curr = int(df.at[idx, "Number of Lectures"])
    # Sunday: full reduction
    if today.weekday() == 6:
        new = max(0, curr - done)
    else:
        # Weekday: need done-1 to reduce by 1
        new = max(0, curr - (done - 1))
    df.at[idx, "Number of Lectures"] = new
    df.at[idx, "Last Updated"] = today.strftime("%Y-%m-%d")
    save_backlog(df)
    return df

def estimate_days(df: pd.DataFrame, pace: int) -> pd.DataFrame:
    net_weekly = pace*7 - 6
    rows = []
    for _, r in df.iterrows():
        b = int(r["Number of Lectures"])
        days = math.inf if net_weekly <= 0 else math.ceil(b*7/net_weekly)
        rows.append({"Subject": r["Subject"], "Days": days, "Weeks~": days//7})
    return pd.DataFrame(rows)

# ==== STREAMLIT UI ====
st.set_page_config(page_title="JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

# 1) Load & Auto‑Increment
data = load_backlog()
data = auto_increment(data)

# 2) Mark Lectures Done
st.subheader("✅ Mark Lectures Done")
if data.empty:
    st.info("No subjects yet. Add one below.")
else:
    c1, c2, c3 = st.columns([3,2,2])
    subject = c1.selectbox("Subject", data["Subject"])
    done = c2.number_input("Lectures done", min_value=0, step=1)
    if c3.button("Mark Done"):
        data = mark_done(data, subject, done)
        st.success(f"{subject} updated by {done} lectures!")

st.markdown("---")

# 3) Force Sync
if st.button("🔄 Force Sync"):
    data = auto_increment(data)
    st.success("Auto‑increment applied (skip Sundays).")

st.markdown("---")

# 4) Add New Subject
st.subheader("➕ Add New Subject")
with st.form("add_form"):
    new_sub = st.text_input("Subject Name").strip()
    new_back = st.number_input("Starting Backlog", min_value=0, step=1)
    if st.form_submit_button("Add Subject"):
        if not new_sub:
            st.warning("Enter a subject name.")
        elif new_sub in data["Subject"].tolist():
            st.warning("Subject already exists.")
        else:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            # Create a new DF row and rewrite entire sheet
            new_row = pd.DataFrame(
                [[new_sub, new_back, today_str]],
                columns=data.columns
            )
            data = pd.concat([data, new_row], ignore_index=True)
            save_backlog(data)
            st.success(f"Added subject '{new_sub}'.")

st.markdown("---")

# 5) Estimated Clear Time & Graph
st.subheader("⏱ Estimated Time to Clear Backlog")
pace = st.slider("Your daily pace (lectures/day)", 1, 10, 1)
est_df = estimate_days(data, pace)
if not est_df.empty:
    st.table(est_df)
else:
    st.info("Add subjects to get an estimate.")

# Optional: plot backlog trend from History sheet
try:
    hist_ws = wb.worksheet("History")
    hist = pd.DataFrame(hist_ws.get_all_records())
    hist["Date"] = pd.to_datetime(hist["Date"])
    hist["Total Backlog"] = hist["Total Backlog"].astype(int)
    st.subheader("📊 Backlog Trend")
    fig, ax = plt.subplots()
    ax.plot(hist["Date"], hist["Total Backlog"], marker="o")
    ax.set_xlabel("Date"); ax.set_ylabel("Lectures"); ax.set_title("Trend")
    st.pyplot(fig)
except:
    pass
