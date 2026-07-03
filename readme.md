# ▶️ YT Analyzer AI (Python Edition)

Analyze any YouTube video with Gemini AI and get a summary, detailed notes, study topics, and action items in seconds.

## Stack

| Layer    | Library                                     |
| -------- | ------------------------------------------- |
| Backend  | FastAPI + uvicorn                           |
| Frontend | Streamlit                                   |
| AI       | Gemini 2.0 Flash                 |
| Storage  | Python `shelve`(keys hashed with SHA-256) |
| HTTP     | `httpx`                                   |

**That's it — only 5 pip packages total.**

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. In terminal 1 — start the API
uvicorn api:app --reload --port 8000

# 3. In terminal 2 — start the UI
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

---

## Usage

1. **Save your Gemini API key** in the sidebar → give it a short alias (e.g. `my-key`)
2. **Paste a YouTube URL** in the main input bar
3. **Pick your key alias** from the dropdown
4. Hit **▶ Analyze** — results appear in ~15 seconds

---

## Key Security

Keys are stored locally in `keys_store.db` (created automatically).

The hash visible in the DB is SHA-256 of your raw key; the raw key is stored separately under `_raw_<alias>` and never leaves your machine.

---

## File Structure

```
yt_analyzer/
├── api.py           ← FastAPI backend (all logic lives here)
├── app.py           ← Streamlit UI
├── requirements.txt
├── README.md
└── keys_store.db    ← auto-created on first key save
```
