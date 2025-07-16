import streamlit as st
import pandas as pd
import datetime
import math
import os
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt

# ==== CONFIG ====
CSV_PATH = "/mnt/data/backlog.csv"
HIST_CSV = "/mnt/data/history.csv"
SHEET_ID = "1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI"

# ==== GOOGLE SHEETS CLIENT ====
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

# ==== LOCAL LOAD/SAVE ====
def ensure_csv():
    if not os.path.exists(CSV_PATH):
        df = pd.DataFrame(columns=["Subject","Number of Lectures","Last Updated"])
        df.to_csv(CSV_PATH, index=False)
    if not os.path.exists(HIST_CSV):
        h = pd.DataFrame(columns=["Date","Total Backlog"])
        h.to_csv(HIST_CSV, index=False)

def load_backlog():
    ensure_csv()
    return pd.read_csv(CSV_PATH)

def save_backlog(df):
    df.to_csv(CSV_PATH, index=False)
    # best‑effort sync to Google Sheets
    if ws:
        try:
            ws.clear()
            ws.append_row(list(df.columns))
            for row in df.itertuples(index=False, name=None):
                ws.append_row(list(row))
        except Exception as e:
            st.warning(f"⚠️ Sheets sync failed: {e}")

def load_history():
    ensure_csv()
    return pd.read_csv(HIST_CSV)

def log_history(total):
    h = load_history()
    today = datetime.date.today().strftime("%Y-%m-%d")
    if h.empty or h["Date"].iloc[-1] != today:
        h = pd.concat([h, pd.DataFrame([[today, total]], columns=h.columns)], ignore_index=True)
        h.to_csv(HIST_CSV, index=False)
        # sync to Sheets
        if hist_ws:
            try:
                hist_ws.clear()
                hist_ws.append_row(list(h.columns))
                for row in h.itertuples(index=False, name=None):
                    hist_ws.append_row(list(row))
            except:
                pass

# ==== BUSINESS LOGIC ====
def auto_increment(df):
    today = datetime.date.today()
    if today.weekday()==6: return df
    changed=False
    for i,row in df.iterrows():
        last=datetime.datetime.strptime(row["Last Updated"],"%Y-%m-%d").date()
        days=(today-last).days
        if days>0:
            inc=sum(1 for d in range(1,days+1)
                    if (last+datetime.timedelta(days=d)).weekday()!=6)
            if inc>0:
                df.at[i,"Number of Lectures"]=int(row["Number of Lectures"])+inc
                df.at[i,"Last Updated"]=today.strftime("%Y-%m-%d")
                changed=True
    if changed:
        save_backlog(df)
        log_history(df["Number of Lectures"].sum())
    return df

def mark_done(df,subject,done):
    today=datetime.date.today()
    idx=df.index[df["Subject"]==subject][0]
    curr=int(df.at[idx,"Number of Lectures"])
    if today.weekday()==6:
        new=max(0,curr-done)
    else:
        new=max(0,curr-(done-1))
    df.at[idx,"Number of Lectures"]=new
    df.at[idx,"Last Updated"]=today.strftime("%Y-%m-%d")
    save_backlog(df)
    log_history(df["Number of Lectures"].sum())
    return df

def estimate_days(df,pace):
    net_weekly=pace*7-6
    rows=[]
    for _,r in df.iterrows():
        b=int(r["Number of Lectures"])
        days=math.inf if net_weekly<=0 else math.ceil(b*7/net_weekly)
        rows.append({"Subject":r["Subject"],"Days":days,"Weeks~":days//7})
    return pd.DataFrame(rows)

# ==== STREAMLIT UI ====
st.set_page_config(page_title="Backlog Tracker", layout="centered")
st.title("📚 JEE Backlog Tracker")

# 1) Load & auto‑increment once
if "initialized" not in st.session_state:
    st.session_state.data = auto_increment(load_backlog())
    st.session_state.initialized = True
data = st.session_state.data

# 2) Mark Done
st.subheader("✅ Mark Lectures Done")
if data.empty:
    st.info("Add a subject below.")
else:
    c1,c2,c3=st.columns([3,2,2])
    subj=c1.selectbox("Subject",data["Subject"])
    done=c2.number_input("Lectures done",min_value=0,step=1)
    if c3.button("Mark Done"):
        st.session_state.data=mark_done(data,subj,done)
        st.success(f"{subj} updated by {done} lectures!")

st.markdown("---")

# 3) Force Sync (local only)
if st.button("🔄 Force Sync"):
    st.session_state.data=auto_increment(data)
    st.success("Auto‑increment applied!")

st.markdown("---")

# 4) Add Subject
st.subheader("➕ Add New Subject")
with st.form("add"):
    ns=st.text_input("Subject Name").strip()
    nb=st.number_input("Starting Backlog",min_value=0,step=1)
    if st.form_submit_button("Add"):
        if not ns:
            st.warning("Enter a subject.")
        elif ns in data["Subject"].tolist():
            st.warning("Subject exists.")
        else:
            today_str=datetime.date.today().strftime("%Y-%m-%d")
            new=pd.DataFrame([[ns,nb,today_str]],columns=data.columns)
            st.session_state.data=pd.concat([data,new],ignore_index=True)
            save_backlog(st.session_state.data)
            st.success(f"Added {ns}.")

st.markdown("---")

# 5) ETA & Graph
st.subheader("⏱ Estimated Time to Clear Backlog")
pace=st.slider("Daily pace",1,10,1)
est_df=estimate_days(st.session_state.data,pace)
if not est_df.empty:
    st.table(est_df)
else:
    st.info("Add subjects to estimate.")

# Backlog Trend
hist=load_history()
if not hist.empty:
    hist["Date"]=pd.to_datetime(hist["Date"])
    st.subheader("📊 Backlog Trend")
    fig,ax=plt.subplots()
    ax.plot(hist["Date"],hist["Total Backlog"],marker="o")
    st.pyplot(fig)
