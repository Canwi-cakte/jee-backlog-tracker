import streamlit as st
import pandas as pd
import datetime
import math
import os
import matplotlib.pyplot as plt

# ==== CONFIG & PATHS ====
BACKLOG_CSV = "backlog.csv"
HISTORY_CSV = "history.csv"

# ==== INITIALIZE CSV FILES ====
def ensure_files():
    if not os.path.exists(BACKLOG_CSV):
        pd.DataFrame(columns=["Subject","Number of Lectures","Last Updated"])\
          .to_csv(BACKLOG_CSV, index=False)
    if not os.path.exists(HISTORY_CSV):
        pd.DataFrame(columns=["Date","Total Backlog"])\
          .to_csv(HISTORY_CSV, index=False)

ensure_files()

# ==== LOAD / SAVE ====
def load_backlog():
    df = pd.read_csv(BACKLOG_CSV)
    return df

def save_backlog(df):
    df.to_csv(BACKLOG_CSV, index=False)

def load_history():
    return pd.read_csv(HISTORY_CSV)

def log_history(total):
    hist = load_history()
    today = datetime.date.today().strftime("%Y-%m-%d")
    if hist.empty or hist["Date"].iloc[-1] != today:
        hist = pd.concat([hist, pd.DataFrame([[today, total]], columns=hist.columns)], ignore_index=True)
        hist.to_csv(HISTORY_CSV, index=False)

# ==== BUSINESS LOGIC ====
def auto_increment(df):
    today = datetime.date.today()
    # Skip Sundays entirely
    if today.weekday() == 6:
        return df
    changed = False
    for i, row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"], "%Y-%m-%d").date()
        days_passed = (today - last).days
        if days_passed > 0:
            inc = sum(1 for d in range(1, days_passed+1)
                      if (last + datetime.timedelta(days=d)).weekday() != 6)
            if inc:
                df.at[i, "Number of Lectures"] = int(row["Number of Lectures"]) + inc
                df.at[i, "Last Updated"] = today.strftime("%Y-%m-%d")
                changed = True
    if changed:
        save_backlog(df)
        log_history(df["Number of Lectures"].sum())
    return df

def mark_done(df, subject, done):
    today = datetime.date.today()
    idx = df.index[df["Subject"] == subject][0]
    curr = int(df.at[idx, "Number of Lectures"])
    if today.weekday() == 6:
        new_val = max(0, curr - done)
    else:
        new_val = max(0, curr - (done - 1))
    df.at[idx, "Number of Lectures"] = new_val
    df.at[idx, "Last Updated"] = today.strftime("%Y-%m-%d")
    save_backlog(df)
    log_history(df["Number of Lectures"].sum())
    return df

def estimate_days(df, pace):
    net_weekly = pace*7 - 6
    rows = []
    for _, r in df.iterrows():
        backlog = int(r["Number of Lectures"])
        if net_weekly <= 0:
            days_needed = math.inf
        else:
            days_needed = math.ceil(backlog * 7 / net_weekly)
        rows.append({
            "Subject": r["Subject"],
            "Days to Finish": days_needed,
            "Weeks ~": days_needed // 7
        })
    return pd.DataFrame(rows)

# ==== STREAMLIT UI ====
st.set_page_config(page_title="JEE Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker (CSV Only)")

# 1) Load & auto‑increment once
if "initialized" not in st.session_state:
    st.session_state.df = auto_increment(load_backlog())
    st.session_state.initialized = True
df = st.session_state.df

# 2) Mark Lectures Done
st.subheader("✅ Mark Lectures Done")
if df.empty:
    st.info("No subjects yet. Add one below.")
else:
    c1, c2, c3 = st.columns([3,2,2])
    subj = c1.selectbox("Subject", df["Subject"])
    done = c2.number_input("Lectures done", min_value=0, step=1)
    if c3.button("Mark Done"):
        df = mark_done(df, subj, done)
        st.session_state.df = df
        st.success(f"{subj} updated by {done} lectures!")

st.markdown("---")

# 3) Force Sync
if st.button("🔄 Force Sync"):
    df = auto_increment(df)
    st.session_state.df = df
    st.success("Auto‑increment applied (excluded Sundays)!")

st.markdown("---")

# 4) Add or Update Subject
st.subheader("➕ Add or Update Subject")
with st.form("add_form"):
    new_sub = st.text_input("Subject Name").strip()
    new_back = st.number_input("Backlog Lectures", min_value=0, step=1)
    if st.form_submit_button("Add / Update Subject"):
        if not new_sub:
            st.warning("Enter a subject name.")
        else:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            if new_sub in df["Subject"].values:
                # Update existing subject
                df.loc[df["Subject"] == new_sub, "Number of Lectures"] = new_back
                df.loc[df["Subject"] == new_sub, "Last Updated"] = today_str
                st.success(f"Updated '{new_sub}' to {new_back} lectures.")
            else:
                # Add new subject
                new_row = pd.DataFrame([[new_sub, new_back, today_str]],
                                       columns=["Subject", "Number of Lectures", "Last Updated"])
                df = pd.concat([df, new_row], ignore_index=True)
                st.success(f"Added subject '{new_sub}' with {new_back} lectures.")

            save_backlog(df)
            log_history(df["Number of Lectures"].sum())
            st.session_state.df = df

st.markdown("---")

# 5) Estimated Time to Clear Backlog
st.subheader("⏱ Estimated Time to Clear Backlog")
pace = st.slider("Your daily pace (lectures/day)", 1, 10, 1)
est_df = estimate_days(df, pace)
if not est_df.empty:
    st.table(est_df)
else:
    st.info("Add subjects to get an estimate!")

# 6) Backlog Trend Graph
hist = load_history()
if not hist.empty:
    hist["Date"] = pd.to_datetime(hist["Date"])
    hist["Total Backlog"] = hist["Total Backlog"].astype(int)
    st.subheader("📊 Backlog Over Time")
    fig, ax = plt.subplots()
    ax.plot(hist["Date"], hist["Total Backlog"], marker="o", linestyle="-")
    ax.set_xlabel("Date"); ax.set_ylabel("Total Backlog")
    st.pyplot(fig)
