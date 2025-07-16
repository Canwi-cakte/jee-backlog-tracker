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

# Ensure sheets exist
def ensure_sheets():
    try:
        b = wb.worksheet("Backlog")
    except:
        b = wb.add_worksheet("Backlog", rows="200", cols="3")
        b.append_row(["Subject","Number of Lectures","Last Updated"])
    try:
        h = wb.worksheet("History")
    except:
        h = wb.add_worksheet("History", rows="365", cols="2")
        h.append_row(["Date","Total Backlog"])
ensure_sheets()
ws = wb.worksheet("Backlog")
hist_ws = wb.worksheet("History")

# ==== I/O ====
def load_backlog():
    df = pd.DataFrame(ws.get_all_records())
    df.columns = ["Subject","Number of Lectures","Last Updated"]
    return df

def save_backlog(df: pd.DataFrame):
    ws.clear()
    ws.append_row(["Subject","Number of Lectures","Last Updated"])
    for r in df.itertuples(index=False, name=None):
        ws.append_row(list(r))

def load_history():
    h = pd.DataFrame(hist_ws.get_all_records())
    h.columns = ["Date","Total Backlog"]
    return h

def log_history(total):
    today = datetime.date.today().strftime("%Y-%m-%d")
    hist = load_history()
    if hist.empty or hist["Date"].iloc[-1] != today:
        hist_ws.append_row([today, int(total)])

# ==== LOGIC ====
def auto_increment(df):
    today = datetime.date.today()
    hist = load_history()
    if not hist.empty and hist["Date"].iloc[-1] == today.strftime("%Y-%m-%d"):
        return df
    if today.weekday() == 6:
        return df
    for i,row in df.iterrows():
        last = datetime.datetime.strptime(row["Last Updated"],"%Y-%m-%d").date()
        days=(today-last).days
        inc=sum(1 for d in range(1,days+1)
                if (last+datetime.timedelta(days=d)).weekday()!=6)
        if inc>0:
            df.at[i,"Number of Lectures"]=int(row["Number of Lectures"])+inc
            df.at[i,"Last Updated"]=today.strftime("%Y-%m-%d")
    save_backlog(df)
    log_history(df["Number of Lectures"].sum())
    return df

def mark_done(df,subject,done):
    today = datetime.date.today()
    idx = df.index[df["Subject"]==subject][0]
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

def estimate(df,pace):
    net_weekly=pace*7-6
    rows=[]
    for _,r in df.iterrows():
        b=int(r["Number of Lectures"])
        days=math.inf if net_weekly<=0 else math.ceil(b*7/net_weekly)
        rows.append({"Subject":r["Subject"],"Days":days,"Weeks":days//7})
    return pd.DataFrame(rows)

# ==== UI ====
st.set_page_config(page_title="Backlog",layout="centered")
st.title("📚 JEE Backlog Tracker")

# Load and auto-increment once per session
if "loaded" not in st.session_state:
    st.session_state.data = load_backlog()
    st.session_state.data = auto_increment(st.session_state.data)
    st.session_state.loaded = True

data = st.session_state.data

# Mark Done
st.subheader("✅ Mark Lectures Done")
if data.empty:
    st.info("Add a subject below.")
else:
    c1,c2,c3=st.columns([3,2,2])
    sub=c1.selectbox("Subject",data["Subject"])
    done=c2.number_input("Lectures done",min_value=0,step=1)
    if c3.button("Mark Done"):
        st.session_state.data = mark_done(data,sub,done)
        st.success(f"{sub} updated by {done} lectures!")

st.markdown("---")

# Force Sync
if st.button("🔄 Force Sync"):
    st.session_state.data = auto_increment(st.session_state.data)
    st.success("Auto-increment applied!")

st.markdown("---")

# Add Subject
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
            today=datetime.date.today().strftime("%Y-%m-%d")
            new=pd.DataFrame([[ns,nb,today]],columns=data.columns)
            st.session_state.data=pd.concat([data,new],ignore_index=True)
            save_backlog(st.session_state.data)
            st.success(f"Added {ns}.")

st.markdown("---")

# ETA & Graph
st.subheader("⏱ Estimated Time to Clear Backlog")
pace=st.slider("Daily pace",1,10,1)
est_df=estimate(st.session_state.data,pace)
if not est_df.empty:
    st.table(est_df)
else:
    st.info("No subjects.")

hist=load_history()
if not hist.empty:
    hist["Date"]=pd.to_datetime(hist["Date"])
    hist["Total Backlog"]=hist["Total Backlog"].astype(int)
    st.subheader("📊 Backlog Trend")
    fig,ax=plt.subplots()
    ax.plot(hist["Date"],hist["Total Backlog"],marker="o")
    st.pyplot(fig)
