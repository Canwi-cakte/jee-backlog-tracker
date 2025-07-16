import streamlit as st
import pandas as pd
import datetime
import math
import os
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt

# ==== CONFIG ====
# Use relative paths so parent directory always exists
CSV_PATH = "backlog.csv"
HIST_CSV = "history.csv"
SHEET_ID = "1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI"

# ==== GOOGLE SHEETS SETUP ====
def get_gsheets_client():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["google_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception:
        return None

gs_client = get_gsheets_client()
if gs_client:
    try:
        wb = gs_client.open_by_key(SHEET_ID)
        ws = wb.worksheet("Backlog")
        hist_ws = wb.worksheet("History")
    except Exception:
        ws = hist_ws = None
else:
    ws = hist_ws = None

# ==== LOCAL CSV PERSISTENCE ====
def ensure_csv():
    # Create blank CSVs if they don't exist
    if not os.path.exists(CSV_PATH):
        pd.DataFrame(columns=["Subject","Number of Lectures","Last Updated"]).to_csv(CSV_PATH, index=False)
    if not os.path.exists(HIST_CSV):
        pd.DataFrame(columns=["Date","Total Backlog"]).to_csv(HIST_CSV, index=False)

def load_backlog():
    ensure_csv()
    return pd.read_csv(CSV_PATH)

def save_backlog(df: pd.DataFrame):
    df.to_csv(CSV_PATH, index=False)
    # Try syncing to Google Sheets
    if ws:
        try:
            ws.clear()
            ws.append_row(list(df.columns))
            for r in df.itertuples(index=False, name=None):
                ws.append_row(list(r))
        except Exception as e:
            st.warning(f"⚠️ Google Sheets sync failed: {e}")

def load_history():
    ensure_csv()
    return pd.read_csv(HIST_CSV)

def log_history(total: int):
    h = load_history()
    today = datetime.date.today().strftime("%Y-%m-%d")
    if h.empty or h["Date"].iloc[-1] != today:
        h = pd.concat([h, pd.DataFrame([[today, total]], columns=h.columns)], ignore_index=True)
        h.to_csv(HIST_CSV, index=False)
        # Sync to Sheets
        if hist_ws:
            try:
                hist_ws.clear()
                hist_ws.append_row(list(h.columns))
                for r in h.itertuples(index=False, name=None):
                    hist_ws.append_row(list(r))
            except:
                pass

# ==== BUSINESS LOGIC ====
def auto_increment(df: pd.DataFrame) -> pd.DataFrame:
    today = datetime.date.today()
    if today.weekday() == 6:  # Sunday
        return df
    changed = False
    for i, row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"], "%Y-%m-%d").date()
        days = (today - last).days
        if days > 0:
            inc = sum(
                1
                for d in range(1, days + 1)
                if (last + datetime.timedelta(days=d)).weekday() != 6
            )
            if inc:
                df.at[i, "Number of Lectures"] = int(row["Number of Lectures"]) + inc
                df.at[i, "Last Updated"] = today.strftime("%Y-%m-%d")
                changed = True
    if changed:
        save_backlog(df)
        log_history(df["Number of Lectures"].sum())
    return df

def mark_done(df: pd.DataFrame, subject: str, done: int) -> pd.DataFrame:
    today = datetime.date.today()
    idx = df.index[df["Subject"] == subject][0]
    curr = int(df.at[idx, "Number of Lectures"])
    if today.weekday() == 6:  # Sunday
        new = max(0, curr - done)
    else:  # Weekday
        new = max(0, curr - (done - 1))
    df.at[idx, "Number of Lectures"] = new
    df.at[idx, "Last Updated"] = today.strftime("%Y-%m-%d")
    save_backlog(df)
    log_history(df["Number of Lectures"].sum())
    return df

def estimate_days(df: pd.DataFrame, pace: int) -> pd.DataFrame:
    net_weekly = pace * 7 - 6
    rows = []
    for _, r in df.iterrows():
        b = int(r["Number of Lectures"])
        if net_weekly <= 0:
            days = math.inf
        else:
            days = math.ceil(b * 7 / net_weekly)
        rows.append({"Subject": r["Subject"], "Days": days, "Weeks~": days // 7})
    return pd.DataFrame(rows)

# ==== STREAMLIT APP ====
st.set_page_config(page_title="JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

# 1) Load & auto‑increment once per session
if "initialized" not in st.session_state:
    st.session_state.data = auto_increment(load_backlog())
    st.session_state.initialized = True
data = st.session_state.data

# 2) Mark Lectures Done
st.subheader("✅ Mark Lectures Done")
if data.empty:
    st.info("Add a subject below.")
else:
    c1, c2, c3 = st.columns([3, 2, 2])
    subj = c1.selectbox("Subject", data["Subject"])
    done = c2.number_input("Lectures done", min_value=0, step=1)
    if c3.button("Mark Done"):
        st.session_state.data = mark_done(data, subj, done)
        st.success(f"{subj} updated by {done} lectures!")

st.markdown("---")

# 3) Force Sync (local + Sheets)
if st.button("🔄 Force Sync"):
    st.session_state.data = auto_increment(data)
    st.success("Auto‑increment applied!")

st.markdown("---")

# 4) Add New Subject
st.subheader("➕ Add New Subject")
with st.form("add_form"):
    ns = st.text_input("Subject Name").strip()
    nb = st.number_input("Starting Backlog", min_value=0, step=1)
    if st.form_submit_button("Add"):
        if not ns:
            st.warning("Enter a subject.")
        elif ns in data["Subject"].tolist():
            st.warning("Subject exists.")
        else:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            new = pd.DataFrame([[ns, nb, today_str]], columns=data.columns)
            st.session_state.data = pd.concat([data, new], ignore_index=True)
            save_backlog(st.session_state.data)
            st.success(f"Added {ns}.")

st.markdown("---")

# 5) Estimated Time & Trend
st.subheader("⏱ Estimated Time to Clear Backlog")
pace = st.slider("Daily pace (lectures/day)", 1, 10, 1)
est_df = estimate_days(st.session_state.data, pace)
if not est_df.empty:
    st.table(est_df)

hist = load_history()
if not hist.empty:
    hist["Date"] = pd.to_datetime(hist["Date"])
    hist["Total Backlog"] = hist["Total Backlog"].astype(int)
    st.subheader("📊 Backlog Trend")
    fig, ax = plt.subplots()
    ax.plot(hist["Date"], hist["Total Backlog"], marker="o")
    st.pyplot(fig)
