import streamlit as st
import pandas as pd
import re
import subprocess
import os
from datetime import datetime
from streamlit_ace import st_ace
from pymongo import MongoClient
import time

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/') 
db = client['DSA_code_app_db']  
collection = db['submissions']  

# Streamlit app setup
st.set_page_config(page_title="DSA Practice", page_icon="🧩", layout="wide") 

# --- HELPER FUNCTIONS ---
def fetch_user_submissions(username):
    submissions = collection.find({"username": username})
    submission_data = {entry["qid"]: {"status": entry["status"], "time_taken": entry["time_taken"]}
                       for entry in submissions}
    return submission_data

def clean_html(raw_html):
    html_entities = {"&nbsp;": " ", "&quot;": '"', "&gt;": ">", "&lt;": "<", "&amp;": "&"}
    for entity, replacement in html_entities.items():
        raw_html = raw_html.replace(entity, replacement)
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

def extract_test_cases(description):
    test_cases = []
    input_pattern = re.compile(r'Input:\s*(.+?)\n', re.IGNORECASE)
    output_pattern = re.compile(r'Output:\s*(.+?)\n', re.IGNORECASE)
    inputs = input_pattern.findall(description)
    outputs = output_pattern.findall(description)
    for i in range(min(len(inputs), len(outputs))):
        test_cases.append({"input": inputs[i].strip(), "output": outputs[i].strip()})
    return test_cases

def get_language_structure(language):
    structures = {
        "Python": "def function_name(param1, param2):\n    # Your code here\n    return output\n",
        "Java": "public class Solution {\n    public static void main(String[] args) {\n    }\n}",
        "C": "#include <stdio.h>\nint main() {\n    return 0;\n}",
        "C++": "#include <iostream>\nusing namespace std;\nint main() {\n    return 0;\n}"
    }
    return structures.get(language, "")

def format_time(seconds):
    hours, rem = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def store_submission_data(username, qid, difficulty, cleaned_topics, code_lang, time_taken):
    submission_data = {
        "username": username, "qid": qid, "difficulty": difficulty,
        "topics": cleaned_topics, "coding_lang": code_lang,
        "time_taken": time_taken, "status": "submitted", "timestamp": datetime.now()
    }
    collection.insert_one(submission_data)
    st.success("Data stored successfully!")

# --- DATA LOADING ---
QUESTIONS_FILE = "question_details.csv"
questions_df = pd.read_csv(QUESTIONS_FILE)
questions_df["topics"] = questions_df["topics"].fillna("[]").apply(
    lambda x: x.strip("[]").replace("'", "").replace('"', "").split(",")
)

# --- NAVIGATION LOGIC ---
query_params = st.query_params
selected_qid = query_params.get("qid")

# User login
username = st.sidebar.text_input("Enter your username", value=st.session_state.get('username', ''))
if username:
    st.session_state['username'] = username
    st.session_state['submissions'] = fetch_user_submissions(username)

# --- PAGE ROUTING ---
if selected_qid:
    # 1. QUESTION DETAIL VIEW
    qid_int = int(selected_qid)
    
    # Add a Back Button to return to the list
    if st.button("⬅️ Back to Question List"):
        st.query_params.clear()
        st.rerun()

    question_data = questions_df[questions_df['QID'] == qid_int]
    
    if not question_data.empty:
        row = question_data.iloc[0]
        st.header(f"🚀 {row['title']}")
        description = clean_html(row['Body'])
        test_cases = extract_test_cases(description)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("Description")
            st.write(description.split("Example")[0].strip())
            with st.expander("Test Cases"):
                for tc in test_cases:
                    st.code(f"Input: {tc['input']}\nOutput: {tc['output']}")

        with col2:
            st.subheader("Code Editor")
            language = st.selectbox("Language", ["Python", "Java", "C", "C++"])
            code = st_ace(language=language.lower() if language != "C++" else "c_cpp", theme='monokai', height=300)
            
            if st.button("Submit Solution"):
                # Simplified for demonstration - logic from your original file
                st.info("Validating test cases...")
                # (Your execute_code and store_submission_data calls go here)

else:
    # 2. MAIN QUESTION LIST VIEW
    st.header("📋 Question List")
    
    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        diff_filter = st.selectbox("Difficulty", ["All"] + list(questions_df["difficulty"].unique()))
    with col_f2:
        all_topics = sorted(set([t.strip() for sublist in questions_df["topics"] for t in sublist]))
        topic_filter = st.selectbox("Topic", ["All"] + all_topics)

    # Apply Filtering
    filtered = questions_df[questions_df["isPaidOnly"] == False]
    if diff_filter != "All":
        filtered = filtered[filtered["difficulty"] == diff_filter]
    if topic_filter != "All":
        filtered = filtered[filtered["topics"].apply(lambda t: topic_filter in [x.strip() for x in t])]

    # Table Display
    if filtered.empty:
        st.warning("No questions found.")
    else:
        # Header Row
        h1, h2, h3, h4, h5 = st.columns([1, 3, 2, 2, 2])
        h1.write("**QID**")
        h2.write("**Title**")
        h3.write("**Difficulty**")
        h4.write("**Status**")
        h5.write("**Action**")
        
        for idx, row in filtered.iterrows():
            c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 2, 2])
            qid = row['QID']
            sub_info = st.session_state.get('submissions', {}).get(qid, {"status": "Pending"})
            
            c1.write(qid)
            c2.write(row['title'])
            c3.write(row['difficulty'])
            c4.write(sub_info['status'])
            
            # THE FIX: Use a relative URL so it works on any port
            # This points to the same server but adds the qid parameter
            c5.markdown(f"[Solve Question ➡️](/?qid={qid})")