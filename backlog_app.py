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

SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI"
wb = client.open_by_url(SHEET_URL)

# Backlog worksheet
try:
    ws = wb.worksheet("Backlog")
except gspread.exceptions.WorksheetNotFound:
    ws = wb.add_worksheet(title="Backlog", rows="100", cols="3")
    ws.update("A1:C1", [["Subject","Number of Lectures","Last Updated"]])

# History worksheet
try:
    hist_ws = wb.worksheet("History")
except gspread.exceptions.WorksheetNotFound:
    hist_ws = wb.add_worksheet(title="History", rows="365", cols="2")
    hist_ws.update("A1:B1", [["Date","Total Backlog"]])

# ==== DATA LOADING/SAVING ====
@st.cache_data(ttl=300)
def load_backlog():
    df = pd.DataFrame(ws.get_all_records())
    expected = ["Subject","Number of Lectures","Last Updated"]
    if list(df.columns) != expected:
        ws.update("A1:C1",[expected])
        return pd.DataFrame(columns=expected)
    return df

def save_backlog(df: pd.DataFrame):
    ws.clear()
    ws.update("A1:C1",[df.columns.tolist()])
    if not df.empty:
        ws.update("A2", df.values.tolist())

def load_history():
    h = pd.DataFrame(hist_ws.get_all_records())
    if list(h.columns) != ["Date","Total Backlog"]:
        hist_ws.update("A1:B1",[["Date","Total Backlog"]])
        return pd.DataFrame(columns=["Date","Total Backlog"])
    return h

def log_history_if_needed(total_backlog:int):
    today = datetime.date.today().strftime("%Y-%m-%d")
    hist = load_history()
    if hist.empty or hist["Date"].iloc[-1] != today:
        hist_ws.append_row([today, total_backlog])

# ==== BUSINESS LOGIC ====
def auto_increment_once(df: pd.DataFrame) -> pd.DataFrame:
    """Increment only once per day, skip Sundays."""
    today = datetime.date.today()
    did_write = False

    # check if we've already logged today in history → implies we synced today
    hist = load_history()
    if not hist.empty and hist["Date"].iloc[-1] == today.strftime("%Y-%m-%d"):
        return df  # already synced today

    if today.weekday() == 6:  # Sunday: no auto increment
        return df

    for i, row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"],"%Y-%m-%d").date()
        days = (today - last).days
        inc = sum(1 for d in range(1, days+1)
                  if (last + datetime.timedelta(days=d)).weekday() != 6)
        if inc>0:
            df.at[i,"Number of Lectures"] = int(row["Number of Lectures"]) + inc
            df.at[i,"Last Updated"] = today.strftime("%Y-%m-%d")
            did_write = True

    if did_write:
        save_backlog(df)
        total = df["Number of Lectures"].sum()
        log_history_if_needed(total)
    return df

def mark_done(df: pd.DataFrame, subject:str, done:int)->pd.DataFrame:
    today = datetime.date.today()
    idx = df.index[df["Subject"]==subject][0]
    curr = int(df.at[idx,"Number of Lectures"])
    if today.weekday()==6:       # Sunday
        new = max(0, curr - done)
    else:                        # Weekday
        net = done - 1
        new = max(0, curr - net)
    df.at[idx,"Number of Lectures"]=new
    df.at[idx,"Last Updated"]=today.strftime("%Y-%m-%d")
    save_backlog(df)
    # also log history after manual change
    total = df["Number of Lectures"].sum()
    log_history_if_needed(total)
    return df

def estimate(df:pd.DataFrame, pace:int)->dict:
    """
    Net weekly reduction = pace*7 - 6 (since 6 weekdays cost 1 extra each)
    days = ceil(backlog *7 / net_weekly)
    """
    net_weekly = pace*7 - 6
    out={}
    for _,r in df.iterrows():
        b=int(r["Number of Lectures"])
        if net_weekly<=0:
            days=math.inf
        else:
            days=math.ceil(b*7/net_weekly)
        out[r["Subject"]]=days
    return out

# ==== STREAMLIT UI ====
st.set_page_config(page_title="📚 JEE Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

# 1) Load & auto‑sync
data = load_backlog()
data = auto_increment_once(data)

# 2) Mark as Done
st.subheader("✅ Mark Lectures Done")
if data.empty:
    st.info("No subjects yet. Add one below.")
else:
    col1,col2,col3=st.columns([3,2,2])
    with col1:
        subject = st.selectbox("Subject", data["Subject"])
    with col2:
        done = st.number_input("Lectures done today", min_value=0, step=1, key="done")
    with col3:
        if st.button("Mark Done"):
            data = mark_done(data, subject, done)
            st.success(f"Updated {subject} by {done} lectures.")

st.markdown("---")

# 3) Force Sync
if st.button("🔄 Force Sync"):
    data = auto_increment_once(data)
    st.success("Forced sync applied.")

st.markdown("---")

# 4) Add Subject
st.subheader("➕ Add New Subject")
with st.form("add"):
    new_sub = st.text_input("Subject Name")
    new_back = st.number_input("Starting Backlog", min_value=0, step=1)
    if st.form_submit_button("Add"):
        if not new_sub.strip():
            st.warning("Enter a subject name.")
        elif new_sub in data["Subject"].values:
            st.warning("Subject exists.")
        else:
            today = datetime.date.today().strftime("%Y-%m-%d")
            row=[new_sub, int(new_back), today]
            ws.append_row(row)
            data = load_backlog()
            st.success(f"Added {new_sub}.")

st.markdown("---")

# 5) History Graph & ETA
hist = load_history()
if hist.empty:
    st.info("No history yet to plot.")
else:
    hist["Date"]=pd.to_datetime(hist["Date"])
    hist["Total Backlog"]=hist["Total Backlog"].astype(int)
    fig,ax=plt.subplots()
    ax.plot(hist["Date"], hist["Total Backlog"], marker="o")
    ax.set_title("Backlog Over Time")
    ax.set_xlabel("Date"); ax.set_ylabel("Lectures")
    st.pyplot(fig)

st.subheader("⏱ Estimated Time to Clear Backlog")
pace = st.slider("Daily pace (lectures/day)", 1, 10, 1)
est = estimate(data, pace)
est_df = pd.DataFrame([{"Subject":s,"Days Needed":d,"Weeks ~":d//7} for s,d in est.items()])
if not est_df.empty:
    st.table(est_df)
else:
    st.info("No subjects to estimate.")
