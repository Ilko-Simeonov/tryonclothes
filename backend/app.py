"""
MIT License — NanoBanana Try-On (FastAPI)
"""

import os
import io
import secrets
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from PIL import Image, ExifTags, UnidentifiedImageError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
from starlette.middleware.security import SecurityMiddleware

from backend.types import TryOnPayload, TryOnResult
from backend.providers.fal_nanobanana import try_on_with_fal_nanobanana, FalError

# ---------------- Settings ----------------

class Settings(BaseSettings):
    PORT: int = 8787
    PUBLIC_BASE_URL: str = "http://localhost:8787"
    ALLOWED_ORIGINS: str = ""
    FAL_KEY: str = ""
    MAX_UPLOAD_MB: int = 10
    DELETE_AFTER_MINUTES: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# ---------------- App & Middleware ----------------

app = FastAPI(title="NanoBanana Try-On (FastAPI)")

# Add security middleware for proper HTTPS handling behind Render's proxy
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(
    SecurityMiddleware,
    hsts_max_age=31536000,
    hsts_include_subdomains=True,
    hsts_preload=True
)

origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Static serving
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
TMP_DIR = Path(".tmp")
TMP_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=False), name="frontend")

# Track generated URLs and tmp files TTL
generated_index: dict[str, datetime] = {}
uploaded_index: dict[str, datetime] = {}

# ---------------- Utilities ----------------

def _strip_exif(img: Image.Image) -> Image.Image:
    # Recreate image to drop EXIF safely
    data = list(img.getdata())
    out = Image.new(img.mode, img.size)
    out.putdata(data)
    return out

def _resize_max(img: Image.Image, max_side: int = 1536) -> Image.Image:
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
    return img

def _random_name(ext: str = "jpg") -> str:
    return f"{secrets.token_hex(8)}.{ext}"

def _basic_guard(filename: str):
    name = filename.lower()
    if "nude" in name or "nsfw" in name:
        raise HTTPException(status_code=422, detail="Content rejected by policy")

def _public_tmp_url(name: str) -> str:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/tmp/{name}"

# Async cleaner
async def _ttl_cleaner():
    while True:
        now = datetime.utcnow()
        # purge temp selfie files
        to_delete = [k for k, exp in uploaded_index.items() if exp < now]
        for k in to_delete:
            try:
                (TMP_DIR / k).unlink(missing_ok=True)
            except Exception:
                pass
            uploaded_index.pop(k, None)
        # purge generated index map (FAL URLs are remote; map is for tracking only)
        for k in list(generated_index.keys()):
            if generated_index[k] < now:
                generated_index.pop(k, None)
        await asyncio.sleep(60)

@app.on_event("startup")
async def _startup():
    asyncio.create_task(_ttl_cleaner())

# Serve tmp files (publicly fetchable by FAL)
@app.get("/tmp/{name}")
def serve_tmp(name: str):
    p = TMP_DIR / name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Not found")
    # Cache a bit, but not long
    return FileResponse(str(p), media_type="image/jpeg")

# ---------------- Routes ----------------

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/tryon")
@limiter.limit("20/minute")
async def api_tryon(
    request: Request,
    person: UploadFile = File(...),
    garmentUrl: str = Form(...),
    category: Optional[str] = Form(None),
    promptExtra: Optional[str] = Form(None),
):
    # Validate file size (FastAPI streams, but we can rely on server/client limits)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    if person.filename is None:
        raise HTTPException(status_code=400, detail="Missing 'person' file")

    _basic_guard(person.filename)

    content = await person.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    # Validate image, rotate by EXIF, strip EXIF, resize
    try:
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    # Best-effort autorotate
    try:
        exif = img.getexif()
        orient = exif.get(0x0112)  # Orientation
        if orient == 3:
            img = img.rotate(180, expand=True)
        elif orient == 6:
            img = img.rotate(270, expand=True)
        elif orient == 8:
            img = img.rotate(90, expand=True)
    except Exception:
        pass

    img = _strip_exif(img)
    img = _resize_max(img, 1536)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    buf.seek(0)

    # Save selfie to tmp and expose a public URL so FAL can fetch it
    name = _random_name("jpg")
    path = TMP_DIR / name
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    uploaded_index[name] = datetime.utcnow() + timedelta(minutes=settings.DELETE_AFTER_MINUTES)

    person_url = _public_tmp_url(name)

    # Call FAL provider
    try:
        progress_logs: list[str] = []
        url, desc, request_id = await try_on_with_fal_nanobanana(
            person_url=person_url,
            garment_url=garmentUrl,
            category=category,
            prompt_extra=promptExtra,
            on_progress=lambda m: progress_logs.append(m),
        )
    except FalError as e:
        raise HTTPException(status_code=502, detail=f"Upstream failure: {e}")

    generated_index[url] = datetime.utcnow() + timedelta(minutes=settings.DELETE_AFTER_MINUTES)

    return TryOnResult(
        imageUrl=url,
        description=desc or "Generated by NanoBanana",
        requestId=request_id,
        ttlMinutes=settings.DELETE_AFTER_MINUTES,
    )

# Root page (optional tiny check)
@app.get("/")
def root():
    return HTMLResponse("<h1>NanoBanana Try-On (FastAPI)</h1><p>See <code>/frontend/tryon-widget.js</code> and <code>/api/tryon</code>.</p>")
