"""EduGenie — FastAPI backend. Run with: uvicorn main:app --reload"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (next to this file) — ensures the API key
# is available even when uvicorn is launched from a different directory.
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from explanation_module import explain_topic
from learning_path import get_learning_recommendations
from qna import answer_question_with_gemini
from quiz_module import generate_quiz
from summary_module import summarize_text

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="EduGenie", description="Google Gemini Powered Learning Assistant")


@app.on_event("startup")
async def _check_api_key():
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        print("[WARNING] GEMINI_API_KEY is not set!")
        print(f"   Looked for .env at: {_ENV_FILE}")
        print("   Copy .env.example -> .env and add your key.")
    else:
        print(f"[OK] GEMINI_API_KEY loaded ({len(key)} chars, ends with ...{key[-4:]})")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


# Q&A - GET API using Gemini
@app.get("/qa")
async def answer_question(question: str = Query(...)):
    answer = answer_question_with_gemini(question)
    return {"answer": answer}


# Explanation - POST API
@app.post("/explain/")
async def explain_api(request: Request):
    data = await request.json()
    topic = data.get("topic")
    if not topic:
        return JSONResponse(content={"error": "Please provide a topic."}, status_code=400)
    explanation = explain_topic(topic)
    return {"topic": topic, "explanation": explanation}


# Summarization - POST API
@app.post("/summarize/")
async def summarize_api(request: Request):
    data = await request.json()
    text = data.get("text")
    if not text:
        return JSONResponse(content={"error": "Please provide text to summarize."}, status_code=400)
    summary = summarize_text(text)
    return {"summary": summary}


# Quiz Generation - POST API
@app.post("/quiz")
async def quiz_api(request: Request):
    data = await request.json()
    text = data.get("text")
    if not text:
        return JSONResponse(content={"error": "Please provide text for quiz."}, status_code=400)
    quiz = generate_quiz(text)
    print("Generated quiz items:", len(quiz) if isinstance(quiz, list) else type(quiz))  # DEBUG
    return JSONResponse(content={"quiz": quiz})


# Learning Recommendations - GET API
@app.get("/learn/recommendations")
async def learning_recommendation_api(topic: str = Query(...)):
    recommendation = get_learning_recommendations(topic)
    return {"topic": topic, "recommendation": recommendation}
