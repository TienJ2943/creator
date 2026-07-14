import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import trends

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

SEEDANCE_API_URL = os.getenv("SEEDANCE_API_URL", "https://api.seedance.example/v1/video/variations")
SEEDANCE_API_KEY = os.getenv("SEEDANCE_API_KEY", "")
PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL", "http://localhost:8000")

app = FastAPI(title="Video Studio API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=BASE_DIR), name="media")


class VideoAsset(BaseModel):
    id: str
    title: str
    prompt: str
    original_url: str
    variation_url: str
    status: str


class VariationResponse(BaseModel):
    job_id: str
    status: str
    original_url: str
    variation_url: str
    prompt: str
    notes: List[str]


class TrendRow(BaseModel):
    platform: str
    trend: str
    post_id: str
    post_url: str
    original_text: str
    keywords: List[str]
    hashtags: List[str]
    likes: int
    comments: int
    retweets: int
    quotes: int
    engagement_score: int
    created_at: str
    tracked_link: str
    rewritten_caption: str
    buffer_text: str
    tags: List[str]


SAMPLE_VIDEOS = [
    VideoAsset(
        id="launch-film",
        title="Launch Film",
        prompt="Cinematic product reveal with moody lighting",
        original_url="https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?auto=format&fit=crop&w=1200&q=80",
        variation_url="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
        status="ready",
    ),
    VideoAsset(
        id="fashion-cut",
        title="Fashion Cut",
        prompt="High-energy fashion edit with punchy transitions",
        original_url="https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=1200&q=80",
        variation_url="https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1200&q=80",
        status="processing",
    ),
    VideoAsset(
        id="travel-loop",
        title="Travel Loop",
        prompt="Warm travel montage with dreamy motion blur",
        original_url="https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80",
        variation_url="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
        status="ready",
    ),
]


@app.get("/api/videos", response_model=List[VideoAsset])
def list_videos() -> List[VideoAsset]:
    return SAMPLE_VIDEOS


@app.get("/api/health")
def health_check() -> dict:
    return {"ok": True, "seedanceConfigured": bool(SEEDANCE_API_KEY)}


@app.get("/api/trends/x", response_model=List[str])
def get_x_trending(woeid: str = "23424748", limit: int = 10) -> List[str]:
    if not trends.X_BEARER_TOKEN:
        raise HTTPException(status_code=503, detail="Missing X_BEARER_TOKEN")

    return trends.get_trending_topics(woeid=woeid, limit=limit)


@app.get("/api/trends/x/search", response_model=List[TrendRow])
def search_x_trends(
    query: str,
    base_link: str,
    campaign_name: str,
    max_results: int = 25,
    output_posts: int = 3,
    use_ai_rewrite: bool = True,
) -> List[TrendRow]:
    if not trends.X_BEARER_TOKEN:
        raise HTTPException(status_code=503, detail="Missing X_BEARER_TOKEN")

    return trends.build_x_rows(
        trend=query,
        base_link=base_link,
        campaign_name=campaign_name,
        posts_per_trend=max_results,
        output_posts_per_trend=output_posts,
        use_ai_rewrite=use_ai_rewrite,
    )


@app.get("/api/trends/instagram", response_model=List[TrendRow])
def search_instagram_trends(
    hashtag: str,
    base_link: str,
    campaign_name: str,
    max_results: int = 25,
    output_posts: int = 3,
    use_ai_rewrite: bool = True,
) -> List[TrendRow]:
    if not trends.IG_ACCESS_TOKEN or not trends.IG_BUSINESS_ACCOUNT_ID:
        raise HTTPException(status_code=503, detail="Missing IG_ACCESS_TOKEN or IG_BUSINESS_ACCOUNT_ID")

    return trends.build_meta_rows(
        platform="Instagram",
        query=hashtag,
        base_link=base_link,
        campaign_name=campaign_name,
        posts_per_query=max_results,
        output_posts_per_query=output_posts,
        use_ai_rewrite=use_ai_rewrite,
    )


@app.get("/api/trends/threads", response_model=List[TrendRow])
def search_threads_trends(
    keyword: str,
    base_link: str,
    campaign_name: str,
    max_results: int = 25,
    output_posts: int = 3,
    use_ai_rewrite: bool = True,
) -> List[TrendRow]:
    if not trends.THREADS_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="Missing THREADS_ACCESS_TOKEN")

    return trends.build_meta_rows(
        platform="Threads",
        query=keyword,
        base_link=base_link,
        campaign_name=campaign_name,
        posts_per_query=max_results,
        output_posts_per_query=output_posts,
        use_ai_rewrite=use_ai_rewrite,
    )


@app.post("/api/variations", response_model=VariationResponse)
async def create_variation(
    video: UploadFile = File(...),
    prompt: str = Form(...),
    style: Optional[str] = Form("Cinematic"),
) -> VariationResponse:
    job_id = str(uuid.uuid4())
    suffix = Path(video.filename or "input.mp4").suffix or ".mp4"
    input_path = UPLOADS_DIR / f"{job_id}{suffix}"
    output_path = OUTPUTS_DIR / f"{job_id}-variation.mp4"

    with input_path.open("wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    notes = [f"Style preset: {style}"]
    original_url = f"{PUBLIC_BACKEND_URL}/media/uploads/{input_path.name}"
    variation_url = f"{PUBLIC_BACKEND_URL}/media/outputs/{output_path.name}"

    if SEEDANCE_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                with input_path.open("rb") as source_file:
                    files = {"video": (input_path.name, source_file, video.content_type or "video/mp4")}
                    data = {"prompt": prompt, "style": style}
                    headers = {"Authorization": f"Bearer {SEEDANCE_API_KEY}"}
                    response = await client.post(SEEDANCE_API_URL, headers=headers, data=data, files=files)
                    response.raise_for_status()
                    payload = response.json()
                    remote_url = payload.get("output_url") or payload.get("video_url")
                    if remote_url:
                        download = await client.get(remote_url)
                        download.raise_for_status()
                        output_path.write_bytes(download.content)
                        notes.append("Generated with Seedance2.0 API")
                    else:
                        raise HTTPException(status_code=502, detail="Seedance API response missing output URL")
        except Exception as exc:
            notes.append(f"Seedance call failed, fallback preview created: {exc}")

    if not output_path.exists():
        ffmpeg_available = shutil.which("ffmpeg") is not None
        if ffmpeg_available:
            import subprocess

            command = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-vf",
                "eq=saturation=1.25:contrast=1.08,drawtext=text='AI Variation Preview':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-th-40",
                "-c:a",
                "copy",
                str(output_path),
            ]
            subprocess.run(command, check=False, capture_output=True)
            if output_path.exists():
                notes.append("Generated local FFmpeg preview variation")
        if not output_path.exists():
            shutil.copy2(input_path, output_path)
            notes.append("Returned original upload as placeholder variation")

    return VariationResponse(
        job_id=job_id,
        status="completed",
        original_url=original_url,
        variation_url=variation_url,
        prompt=prompt,
        notes=notes,
    )
