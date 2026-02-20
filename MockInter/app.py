# ===================== IMPORTS =====================
import streamlit as st
import os
import time
import cv2
import speech_recognition as sr
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, RTCConfiguration
import google.generativeai as genai

# ===================== ENV & GEMINI CONFIG =====================
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ===================== MONGODB =====================
client = MongoClient("mongodb://localhost:27017/")
db = client["mock_interviews"]
feedback_collection = db["feedbacks"]
face_log_collection = db["face_logs"]

# ===================== DB LOGGING =====================
def store_face_log(student_id, message):
    face_log_collection.insert_one({
        "student_id": student_id,
        "violation": message,
        "timestamp": datetime.now()
    })

# ===================== SAFE RERUN =====================
def rerun_app():
    st.rerun()

# ===================== NEXT QUESTION CALLBACK =====================
def next_question_callback():
    interview = st.session_state.current_interview
    idx = st.session_state.question_index

    feedback = process_answer(
        interview["questions"][idx],
        st.session_state.current_answer
    )

    feedback_collection.insert_one({
        "username": interview["username"],
        "question": interview["questions"][idx],
        "answer": st.session_state.current_answer,
        "feedback": feedback,
        "timestamp": datetime.now()
    })

    interview["responses"].append(feedback)
    st.session_state.current_answer = ""
    st.session_state.question_index += 1

# ===================== IMPROVED VIDEO PROCTORING =====================
class VideoTransformer(VideoTransformerBase):
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )
        self.student_id = None
        self.proctoring_enabled = False
        self.last_log_time = 0
        self.log_interval = 2
        self.prev_time = time.time()

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(gray, 1.2, 5)
        status = "OK"
        color = (0, 255, 0)

        if self.proctoring_enabled:
            if len(faces) == 0:
                status = "NO FACE"
                color = (0, 0, 255)
            elif len(faces) > 1:
                status = "MULTIPLE FACES"
                color = (0, 0, 255)
            else:
                (x, y, w, h) = faces[0]
                roi = gray[y:y+h, x:x+w]
                eyes = self.eye_cascade.detectMultiScale(roi, 1.1, 5)
                if len(eyes) < 2:
                    status = "NOT LOOKING"
                    color = (0, 255, 255)

            if status != "OK" and time.time() - self.last_log_time > self.log_interval:
                self.last_log_time = time.time()
                if self.student_id:
                    store_face_log(self.student_id, status)

        # Draw face boxes
        for (x, y, w, h) in faces:
            cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)

        # FPS counter
        now = time.time()
        fps = int(1 / (now - self.prev_time)) if now != self.prev_time else 0
        self.prev_time = now

        # Overlay text
        cv2.putText(img, f"Status: {status}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(img, f"Faces: {len(faces)}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img, f"FPS: {fps}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return img

# ===================== WEBRTC CONFIG =====================
RTC_CONFIGURATION = RTCConfiguration({
    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
})

# ===================== GEMINI FUNCTIONS =====================
def get_gemini_questions(job_role, tech_stack, experience):
    try:
        response = genai.generate_text(
            model="models/text-bison-001",
            prompt=f"Generate 5 interview questions for {job_role} using {tech_stack}",
            max_output_tokens=300
        )
        return [q for q in response.result.split("\n") if q.strip()]
    except:
        return [
            "Explain a core concept.",
            "Describe a project you worked on.",
            "How do you debug issues?",
            "Explain performance optimization.",
            "Common mistakes developers make?"
        ]

def process_answer(question, answer):
    try:
        response = genai.generate_text(
            model="models/text-bison-001",
            prompt=f"Evaluate answer:\nQ:{question}\nA:{answer}",
            max_output_tokens=200
        )
        return response.result
    except:
        return "Score: 6/10\nImprove explanation."

# ===================== SESSION STATE =====================
if "current_interview" not in st.session_state:
    st.session_state.current_interview = None
if "question_index" not in st.session_state:
    st.session_state.question_index = 0
if "current_answer" not in st.session_state:
    st.session_state.current_answer = ""

# ===================== SIDEBAR CAMERA =====================
with st.sidebar:
    st.title("📷 Live Proctoring Camera")
    camera = webrtc_streamer(
        key="camera",
        video_transformer_factory=VideoTransformer,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True
    )

# ===================== MAIN UI =====================
st.title("🤖 AI Mock Interview")

if st.session_state.current_interview is None:
    with st.form("interview_form"):
        username = st.text_input("Username")
        job_role = st.text_input("Job Role")
        tech_stack = st.text_input("Tech Stack")
        experience = st.number_input("Experience (years)", 0, 40)
        start = st.form_submit_button("Start Interview")

        if start:
            questions = get_gemini_questions(job_role, tech_stack, experience)
            st.session_state.current_interview = {
                "username": username,
                "questions": questions,
                "responses": []
            }
            st.session_state.question_index = 0
            st.session_state.current_answer = ""

            if camera and camera.video_transformer:
                camera.video_transformer.proctoring_enabled = True
                camera.video_transformer.student_id = username

            rerun_app()

else:
    interview = st.session_state.current_interview
    idx = st.session_state.question_index

    if idx < len(interview["questions"]):
        st.subheader(f"Question {idx + 1}")
        st.write(interview["questions"][idx])
        st.text_area("Your Answer", key="current_answer")
        st.button("Next", on_click=next_question_callback)
    else:
        st.success("🎉 Interview Completed")

    username = interview["username"]

    st.header("📊 Interview Results")

    # Fetch feedback records
    records = list(feedback_collection.find({"username": username}))

    total_score = 0
    count = 0

    for rec in records:
        st.markdown("---")
        st.subheader(f"❓ {rec['question']}")
        st.write(f"**Your Answer:** {rec['answer']}")
        st.write(f"**AI Feedback:**")
        st.info(rec["feedback"])

        # Extract score if present
        if "Score" in rec["feedback"]:
            try:
                score = int(rec["feedback"].split("/")[0].split(":")[-1].strip())
                total_score += score
                count += 1
            except:
                pass

    # ================= SCORE SUMMARY =================
    if count > 0:
        avg_score = total_score / count
    else:
        avg_score = 0

    st.markdown("## 🏆 Overall Performance")

    if avg_score >= 8:
        st.success(f"Excellent Performance ⭐ ({avg_score:.1f}/10)")
    elif avg_score >= 6:
        st.warning(f"Good Performance 👍 ({avg_score:.1f}/10)")
    else:
        st.error(f"Needs Improvement 📈 ({avg_score:.1f}/10)")

    # ================= FACE VIOLATIONS =================
    st.markdown("## 🚨 Proctoring Report")

    violations = list(face_log_collection.find({"student_id": username}))

    if violations:
        for v in violations:
            st.error(f"{v['violation']} at {v['timestamp'].strftime('%H:%M:%S')}")
    else:
        st.success("No violations detected ✅")

    # ================= CLOSE =================
    if st.button("Close Interview"):
        st.session_state.current_interview = None
        st.session_state.question_index = 0
        st.session_state.current_answer = ""
        rerun_app()
