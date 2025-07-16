import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ---- AUTH SETUP ----
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS = Credentials.from_service_account_file("creds.json", scopes=SCOPES)
client = gspread.authorize(CREDS)

# ---- CONFIG ----
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jeooSyD_3NTroYkIQwL5upJh5hC4l3J4cGXw07352EI/edit"
sheet = client.open_by_url(SHEET_URL).sheet1

st.set_page_config(page_title="📚 JEE Backlog Tracker", layout="centered")

# ---- STYLING ----
st.markdown("""
    <style>
        .title {text-align: center; font-size: 32px; font-weight: bold;}
        .subtitle {text-align: center; font-size: 20px;}
        .stButton>button {width: 100%;}
        .css-18ni7ap {background-color: #f9f9f9;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="title">📘 JEE Backlog Tracker</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Track your Physics, Chemistry, and Maths backlog like a beast 💪</p>', unsafe_allow_html=True)

# ---- LOAD EXISTING DATA ----
@st.cache_data(ttl=60)
def load_data():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

df = load_data()

# ---- USER INPUT ----
with st.form("new_entry"):
    st.subheader("➕ Add New Topic")
    col1, col2 = st.columns(2)

    with col1:
        subject = st.selectbox("Subject", ["Physics", "Chemistry", "Maths"])
        topic = st.text_input("Topic Name")
    with col2:
        status = st.selectbox("Status", ["Not Started", "In Progress", "Completed"])
        deadline = st.date_input("Deadline")

    submitted = st.form_submit_button("📌 Add Topic")
    if submitted:
        if not topic.strip():
            st.warning("Topic name can't be empty, bro 😤")
        else:
            sheet.append_row([subject, topic, status, str(deadline)])
            st.success("Added to the backlog! Go crush it 🔥")
            st.cache_data.clear()

# ---- VIEW DATA ----
st.subheader("📋 Your Current Backlog")
if df.empty:
    st.info("No topics yet. Add some to get started!")
else:
    filtered_subject = st.selectbox("Filter by Subject", ["All"] + list(df["Subject"].unique()))
    filtered_status = st.selectbox("Filter by Status", ["All"] + list(df["Status"].unique()))

    display_df = df.copy()
    if filtered_subject != "All":
        display_df = display_df[display_df["Subject"] == filtered_subject]
    if filtered_status != "All":
        display_df = display_df[display_df["Status"] == filtered_status]

    st.dataframe(display_df, use_container_width=True)

# ---- FOOTER ----
st.markdown("---")
st.markdown("Built with 💙 by your boy and Gaurav's AI Wingman 🤖")
