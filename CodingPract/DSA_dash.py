import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.express as px

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["DSA_code_app_db"]
collection = db["submissions"]

def fetch_data(username):
    cursor = collection.find({"username": username})
    return pd.DataFrame(list(cursor))

st.header("📊 DSA Submission Overview")

username = st.text_input("Enter Username")

if username:
    df = fetch_data(username)

    if df.empty:
        st.warning("No submissions found")
        st.stop()

    st.write(f"Total Submissions: {len(df)}")

    # ---- SAFE TIMESTAMP HANDLING (NO KeyError possible) ----
    if "timestamp" in df.columns:
        ts = df["timestamp"]
    elif "created_at" in df.columns:
        ts = df["created_at"]
    elif "submitted_at" in df.columns:
        ts = df["submitted_at"]
    else:
        # MongoDB ObjectId fallback (ALWAYS exists)
        ts = df["_id"].apply(lambda x: x.generation_time)

    df["date"] = pd.to_datetime(ts).dt.date

    # ---- DATE-WISE SUBMISSIONS ----
    date_counts = (
        df["date"]
        .value_counts()
        .sort_index()
        .reset_index()
        .rename(columns={"index": "Date", "date": "Submission Count"})
    )

    st.subheader("📅 Submissions Over Time")
    st.plotly_chart(
        px.line(date_counts, x="Date", y="Submission Count", markers=True),
        use_container_width=True
    )

    # ---- DIFFICULTY ----
    if "difficulty" in df.columns:
        diff_counts = df["difficulty"].value_counts().reset_index()
        diff_counts.columns = ["Difficulty", "Count"]
        st.subheader("🎯 Difficulty-wise")
        st.plotly_chart(px.pie(diff_counts, names="Difficulty", values="Count"))

    # ---- TOPICS ----
    if "topics" in df.columns:
        topic_counts = (
            df.explode("topics")["topics"]
            .value_counts()
            .reset_index()
            .rename(columns={"index": "Topic", "topics": "Count"})
        )
        st.subheader("📚 Topic-wise")
        st.plotly_chart(px.bar(topic_counts, x="Topic", y="Count"))

    # ---- LANGUAGE ----
    if "coding_lang" in df.columns:
        lang_counts = df["coding_lang"].value_counts().reset_index()
        lang_counts.columns = ["Language", "Count"]
        st.subheader("💻 Coding Language")
        st.plotly_chart(px.pie(lang_counts, names="Language", values="Count"))
