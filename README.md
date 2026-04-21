# ⚡ Veda AI — Viral Short-Form Clip Generator

Automated pipeline that turns 20–50 minute videos into viral 20–30 second clips for **TikTok**, **Instagram Reels**, and **YouTube Shorts**.

## Pipeline

```
Upload → Transcode → Transcribe → Scene Detect → Virality Score → Reframe → AI Suggestions → Caption
```

| Stage | Tool | What it does |
|---|---|---|
| **1. Transcode** | FFmpeg | Normalize to H.264 1080p 30fps |
| **2. Transcribe** | OpenAI Whisper | Word-level timestamps |
| **3. Scene Detect** | PySceneDetect | Find natural edit boundaries |
| **4. Virality Score** | Gemini Flash | Score 0–100, select top 5 |
| **5. Reframe** | MediaPipe + FFmpeg | Smart 9:16 face-tracked crop |
| **6. AI Suggestions** | Gemini Flash | Hooks, b-roll prompts, overlays |
| **7. Caption** | FFmpeg ASS | TikTok-style animated word captions |

## Quick Start

```bash
# 1. Copy env and add your API key
cp .env.example .env
# Edit .env — add your GEMINI_API_KEY

# 2. Start everything
docker compose up -d

# 3. Open the UI
open http://localhost:5173

# 4. MinIO console (to browse stored files)
open http://localhost:9001
# Login: minioadmin / minioadmin
```

## Services

| Service | URL |
|---|---|
| Frontend UI | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |
| Redis | localhost:6379 |

## Storage Layout (MinIO bucket: `veda-videos`)

```
uploads/{job_id}/original.{ext}
processed/{job_id}/transcoded.mp4
transcripts/{job_id}/transcript.json
thumbnails/{job_id}/scene_0001.jpg
clips/{job_id}/{clip_id}_tiktok.mp4
clips/{job_id}/{clip_id}_reels.mp4
clips/{job_id}/{clip_id}_shorts.mp4
```

## API Quick Reference

```
POST /api/upload                        Upload video → returns job_id
GET  /api/jobs/{job_id}/status          Poll pipeline progress
GET  /api/jobs/{job_id}                 Full job + scenes
GET  /api/clips/{job_id}                List clips with presigned URLs
GET  /api/clips/{job_id}/{clip_id}/url  Fresh presigned download URL
```

## Development (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000 &
celery -A worker.celery_app worker --loglevel=info &

# Frontend
cd frontend
npm install
npm run dev
```

## Configuration

Key settings in `.env`:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Required for virality scoring + AI suggestions |
| `WHISPER_MODEL` | `base` | `tiny`/`base`/`small`/`medium`/`large` |
| `VIRALITY_THRESHOLD` | `55` | Min score (0–100) to create a clip |
| `CLIP_MIN_DURATION` | `20` | Min clip length in seconds |
| `CLIP_MAX_DURATION` | `30` | Max clip length in seconds |
| `MINIO_*` | See `.env.example` | Object storage config |
# vedaAI-DEMO
