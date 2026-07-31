# Visionary Studio

Artlist-inspired AI video generation site with a React frontend and FastAPI backend.

## Stack

- Frontend: React + Vite
- Edge API: Cloudflare Worker proxy
- Backend: FastAPI
- Video tools: FFmpeg + Seedance2.0 API

## Features

- Upload video
- Apply prompt
- Generate variation
- Artlist-style cinematic landing page
- Pipeline overview for orchestration, evaluation, reward optimization, and final memo

## Run locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate 
py -3.13 -m venv .venv #(for Windows)
.\.venv\Scripts\Activate.ps1 #(for Windows)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE=http://localhost:8000` if needed.

## Environment

Copy `backend/.env.example` to `backend/.env` and set:

- `SEEDANCE_API_KEY`
- `SEEDANCE_API_URL`
- `PUBLIC_BACKEND_URL`

If the Seedance API is not configured, the backend falls back to a local FFmpeg preview transform, or returns the original file as a placeholder.

## Cloudflare Worker

The frontend production target is `https://creator.fintie.workers.dev`.
This Worker should proxy these routes to the backend origin:

- `GET /api/health`
- `GET /api/videos`
- `POST /api/variations`

Deploy from `cloudflare-worker/`:

```bash
cd cloudflare-worker
npm install
npm run deploy
```

Set Worker vars in `wrangler.toml` or via Cloudflare dashboard:

- `BACKEND_ORIGIN` (default `https://creator-backend.onrender.com`)
- `ALLOWED_ORIGIN` (default `https://creator.nextgenius.com.au`)
