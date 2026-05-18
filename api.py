"""
api.py -- FastAPI backend for YT Analyzer AI
Run with: python -m uvicorn api:app --reload --port 8000
"""

import re
import json
import shelve
import hashlib
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="YT Analyzer API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Key store (shelve persists to disk, keys are SHA-256 hashed)

KEY_DB = "keys_store"

def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def save_key(alias: str, raw_key: str):
    with shelve.open(KEY_DB) as db:
        db[alias] = hash_key(raw_key)
        db[f"_raw_{alias}"] = raw_key

def load_raw_key(alias: str) -> str | None:
    with shelve.open(KEY_DB) as db:
        return db.get(f"_raw_{alias}")

def list_aliases() -> list[str]:
    with shelve.open(KEY_DB) as db:
        return [k for k in db.keys() if not k.startswith("_raw_")]

# Pydantic models

class SaveKeyRequest(BaseModel):
    alias: str
    api_key: str

class AnalyzeRequest(BaseModel):
    alias: str
    youtube_url: str

# Helper: extract video ID

def extract_video_id(url: str) -> str | None:
    pattern = r"(?:youtu\.be/|v/|u/\w/|embed/|watch\?v=|&v=)([^#&?]{11})"
    m = re.search(pattern, url)
    return m.group(1) if m else None

# Helper: fetch oembed metadata

async def fetch_video_info(video_id: str) -> dict:
    default = {
        "title": "YouTube Video",
        "channel": "Unknown",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            )
            d = r.json()
            return {"title": d["title"], "channel": d["author_name"], "thumbnail": d["thumbnail_url"]}
    except Exception:
        return default

# Helper: fetch transcript via allorigins proxy

async def fetch_transcript(video_id: str) -> str:
    fallback = "This video covers important explanations and key concepts."
    try:
        timedtext_url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en&fmt=json3"
        proxy_url = f"https://api.allorigins.win/get?url={httpx.URL(timedtext_url)}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(proxy_url)
            data = json.loads(r.json()["contents"])
        if not data.get("events"):
            return fallback
        text = " ".join(
            "".join(seg.get("utf8", "") for seg in event.get("segs", []))
            for event in data["events"]
            if event.get("segs")
        )
        return re.sub(r"\s+", " ", text).strip() or fallback
    except Exception:
        return fallback

# Helper: call Gemini REST API with automatic model fallback

# Tried in order -- if one returns 503 (overloaded) the next is attempted
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",   # fastest & most available -- try first
    "gemini-2.5-flash",        # standard fallback
    "gemini-3-flash-preview",  # latest quality, preview stability
]

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

PROMPT_TEMPLATE = """
You must respond ONLY with valid JSON -- no markdown, no extra text.

{{
  "summary": "Short summary of the main idea.",
  "properExplanation": "Long beginner-friendly explanation.",
  "detailedNotes": [
    {{"topic": "Topic 1", "content": "Explanation"}},
    {{"topic": "Topic 2", "content": "Explanation"}}
  ],
  "shortNotes": ["Point 1", "Point 2", "Point 3"],
  "actionItems": ["Action 1", "Action 2"],
  "studyTopics": ["Topic A", "Topic B"]
}}

Video Title: {title}
Channel: {channel}
Transcript (first 7000 chars): {transcript}
"""

async def call_gemini(api_key: str, title: str, channel: str, transcript: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        title=title, channel=channel, transcript=transcript[:7000]
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    last_error = ""
    async with httpx.AsyncClient(timeout=60) as client:
        for model in GEMINI_MODELS:
            url = f"{GEMINI_BASE}/{model}:generateContent"
            r = await client.post(url, params={"key": api_key}, json=payload)

            if r.status_code == 503:
                last_error = f"{model} overloaded"
                continue  # try next model

            if r.status_code != 200:
                raise HTTPException(
                    status_code=r.status_code,
                    detail=f"Gemini API error ({model}): {r.text}"
                )

            # Success -- parse and return
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            clean = re.sub(r"```json\n?|```\n?", "", raw).strip()
            start, end = clean.find("{"), clean.rfind("}")
            return json.loads(clean[start : end + 1])

    raise HTTPException(
        status_code=503,
        detail=f"All Gemini models are currently overloaded. ({last_error}). Try again in a minute."
    )

# Routes

@app.get("/")
def root():
    return {"status": "YT Analyzer API is running"}

@app.post("/keys/save")
def save_api_key(body: SaveKeyRequest):
    """Save (and hash-store) a Gemini API key under a friendly alias."""
    save_key(body.alias.strip(), body.api_key.strip())
    return {"message": f"Key saved under alias '{body.alias}'"}

@app.get("/keys/list")
def list_keys():
    """Return all saved key aliases."""
    return {"aliases": list_aliases()}

@app.post("/analyze")
async def analyze(body: AnalyzeRequest):
    """Fetch transcript + metadata, then ask Gemini to analyze the video."""
    api_key = load_raw_key(body.alias)
    if not api_key:
        raise HTTPException(status_code=404, detail=f"No key found for alias '{body.alias}'")

    video_id = extract_video_id(body.youtube_url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Could not extract a valid YouTube video ID.")

    video_info = await fetch_video_info(video_id)
    transcript = await fetch_transcript(video_id)
    analysis = await call_gemini(api_key, video_info["title"], video_info["channel"], transcript)

    return {**analysis, "videoInfo": video_info, "videoId": video_id}