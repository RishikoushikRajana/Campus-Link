import streamlit as st
import os
import json
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    st.error("❌ Google API key not found. Add GOOGLE_API_KEY to .env file")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# ✅ UPDATED FOR 2026: 
# gemini-1.5-flash and gemini-1.0-pro are retired (404).
# Use 'gemini-2.5-flash' for the best balance of speed and free quota.
MODEL_NAME = "gemini-2.5-flash"

# ---------------- GEMINI FUNCTION ----------------
def ask_gemini(prompt):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            return "⚠️ Quota exceeded. Please wait 30-60 seconds and try again."
        elif "404" in error_msg:
            return f"⚠️ Model '{MODEL_NAME}' not found. Please check latest model aliases."
        st.error(f"AI Error: {e}")
        return "⚠️ AI service error"

# ---------------- EXTRACT TEXT FROM PDF ----------------
@st.cache_data
def extract_resume_text(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return ""

# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="ATS Resume Scanner", layout="wide")
st.title("📄 ATS Resume Scanner")

# Sidebar for visibility
with st.sidebar:
    st.subheader("Model Status")
    st.info(f"Active Model: {MODEL_NAME}")
    if st.button("Refresh Models List"):
        try:
            available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            st.write("Available models:")
            st.write(available)
        except Exception as e:
            st.error(e)

job_description = st.text_area("📌 Paste Job Description", height=200, placeholder="Paste the job requirements here...")
uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

# Store resume text in session state
if uploaded_file:
    if "resume_text" not in st.session_state or st.session_state.get("filename") != uploaded_file.name:
        st.session_state.resume_text = extract_resume_text(uploaded_file)
        st.session_state.filename = uploaded_file.name
        st.success("✅ Resume processed successfully")

# Action Buttons
col1, col2, col3 = st.columns(3)
with col1:
    review_btn = st.button("📄 Resume Review", use_container_width=True)
with col2:
    skills_btn = st.button("🧠 Extract Skills", use_container_width=True)
with col3:
    match_btn = st.button("📊 ATS Match", use_container_width=True)

# ---------------- BUTTON LOGIC ----------------
resume_data = st.session_state.get("resume_text", "")

if review_btn:
    if not resume_data or not job_description:
        st.warning("Please provide both a Resume and a Job Description.")
    else:
        with st.spinner("Analyzing..."):
            prompt = f"Review this resume against the JD. JD: {job_description}\nResume: {resume_data}"
            st.subheader("📌 Evaluation")
            st.write(ask_gemini(prompt))

elif skills_btn:
    if not resume_data:
        st.warning("Please upload a resume first.")
    else:
        with st.spinner("Extracting..."):
            prompt = f"Extract Technical, Analytical, and Soft skills into JSON format from this resume: {resume_data}"
            result = ask_gemini(prompt)
            st.subheader("🧠 Skills Found")
            # Basic cleanup of AI markdown output
            clean_json = result.replace("```json", "").replace("```", "").strip()
            try:
                st.json(json.loads(clean_json))
            except:
                st.write(result)

elif match_btn:
    if not resume_data or not job_description:
        st.warning("Please provide both a Resume and a Job Description.")
    else:
        with st.spinner("Matching..."):
            prompt = f"Compare Resume to JD. Provide: 1. Match % 2. Missing Keywords 3. Improvement Tips. JD: {job_description}\nResume: {resume_data}"
            st.subheader("📊 ATS Match Result")
            st.write(ask_gemini(prompt))