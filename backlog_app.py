import streamlit as st
import pandas as pd
import datetime
import math
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt

# ==== AUTH & SHEET SETUP ====
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CREDS = Credentials.from_service_account_info(
    st.secrets["google_service_account"], scopes=SCOPES
)
client = gspread.authorize(CREDS)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI"
wb = client.open_by_url(SHEET_URL)
try:
    ws = wb.worksheet("Backlog")
except gspread.exceptions.WorksheetNotFound:
    ws = wb.add_worksheet(title="Backlog", rows="100", cols="3")
    ws.update("A1:C1", [["Subject", "Number of Lectures", "Last Updated"]])

# ==== DATA I/O ====
@st.cache_data(ttl=60)
def load_data():
    df = pd.DataFrame(ws.get_all_records())
    # ensure correct columns
    expected = ["Subject", "Number of Lectures", "Last Updated"]
    if list(df.columns) != expected:
        ws.update("A1:C1", [expected])
        return pd.DataFrame(columns=expected)
    return df

def save_data(df: pd.DataFrame):
    ws.clear()
    ws.update("A1:C1", [list(df.columns)])
    if not df.empty:
        ws.update("A2", df.values.tolist())

# ==== BUSINESS LOGIC ====
def auto_increment(df: pd.DataFrame) -> pd.DataFrame:
    today = datetime.date.today()
    # skip Sundays entirely
    if today.weekday() == 6:
        return df
    for i, row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"], "%Y-%m-%d").date()
        delta = (today - last).days
        if delta > 0:
            inc = sum(1 for d in range(1, delta+1)
                      if (last + datetime.timedelta(days=d)).weekday() != 6)
            df.at[i, "Number of Lectures"] = int(row["Number of Lectures"]) + inc
            df.at[i, "Last Updated"] = today.strftime("%Y-%m-%d")
    return df

def mark_as_done(df: pd.DataFrame, subject: str, done: int) -> pd.DataFrame:
    today = datetime.date.today()
    idx = df.index[df["Subject"] == subject][0]
    curr = df.at[idx, "Number of Lectures"]
    if today.weekday() == 6:  # Sunday: full reduction
        new = max(0, curr - done)
    else:  # Weekday: need done-1 net to reduce by done-1
        net = done - 1
        new = max(0, curr - net)
    df.at[idx, "Number of Lectures"] = new
    df.at[idx, "Last Updated"] = today.strftime("%Y-%m-%d")
    return df

def estimate_days(df: pd.DataFrame, pace: int) -> dict:
    """
    Compute days needed per subject, given daily pace,
    using your logic: weekdays auto+1, sundays no auto, pace lectures per day.
    Effective weekly net = (pace-1)*6 + pace = 7*pace - 6
    Thus, days = ceil(backlog * 7 / net_weekly)
    """
    res = {}
    net_weekly = pace*7 - 6
    for _, row in df.iterrows():
        b = int(row["Number of Lectures"])
        if net_weekly <= 0:
            days = float('inf')
        else:
            days = math.ceil(b * 7 / net_weekly)
        res[row["Subject"]] = days
    return res

# ==== STREAMLIT UI ====
st.set_page_config(page_title="📚 JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

# 1) Load & auto-sync missed days
data = load_data()
data = auto_increment(data)
save_data(data)

# 2) Display & Mark as Done
st.subheader("✅ Mark Lectures Completed")
if not data.empty:
    col_subj, col_done, col_btn = st.columns([3,2,1])
    with col_subj:
        sub_sel = st.selectbox("Subject", data["Subject"])
    with col_done:
        done_input = st.number_input("Lectures done today", min_value=0, step=1)
    with col_btn:
        if st.button("Mark Done"):
            data = mark_as_done(data, sub_sel, done_input)
            save_data(data)
            st.success(f"{sub_sel}: reduced backlog by logic for {done_input} lectures.")
            st.experimental_rerun()
else:
    st.info("No subjects yet. Add one below!")

st.markdown("---")

# 3) Force Sync
if st.button("🔄 Force Sync Missed Days"):
    data = auto_increment(data)
    save_data(data)
    st.success("Force-sync complete!")
    st.experimental_rerun()

st.markdown("---")

# 4) Add New Subject
st.subheader("➕ Add New Subject")
with st.form("add"):
    new_sub = st.text_input("Subject Name")
    new_back = st.number_input("Starting Backlog Lectures", min_value=0, step=1)
    if st.form_submit_button("Add Subject"):
        if new_sub.strip()=="":
            st.warning("Enter a subject name.")
        elif new_sub in data["Subject"].values:
            st.warning("Subject already exists.")
        else:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            data = pd.concat([
                data,
                pd.DataFrame([[new_sub, new_back, today_str]],
                             columns=data.columns)
            ], ignore_index=True)
            save_data(data)
            st.success(f"Added subject '{new_sub}'.")
            st.experimental_rerun()

st.markdown("---")

# 5) Backlog Overview & ETA Graph
st.subheader("📈 Backlog Overview")

# Pace slider
pace = st.slider("Your daily pace (lectures/day)", 1, 10, 1)

# Estimate days per subject
days_needed = estimate_days(data, pace)
est_table = pd.DataFrame([
    {"Subject": s, "Days to Finish": d, "Weeks ~": f"{math.ceil(d/7)}"}
    for s, d in days_needed.items()
])
st.table(est_table)

# Bar chart
fig, ax = plt.subplots()
ax.bar(est_table["Subject"], est_table["Days to Finish"])
ax.set_ylabel("Days to Finish")
ax.set_title("Estimated Time to Clear Backlog")
st.pyplot(fig)
