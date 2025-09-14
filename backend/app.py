"""
MIT License — NanoBanana Try-On (FastAPI)
"""

import os
import io
import secrets
import asyncio
import logging
import httpx
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
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from backend.types import TryOnPayload, TryOnResult
from backend.providers.fal_nanobanana import try_on_with_fal_nanobanana, FalError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- Settings ----------------

class Settings(BaseSettings):
    PORT: int = 8787
    PUBLIC_BASE_URL: str = "https://tryonclothes.onrender.com"
    ALLOWED_ORIGINS: str = "https://sparkvision.tech"
    FAL_KEY: str = ""  # Keep for backward compatibility
    KIE_API_KEY: str = ""  # New Kie.ai API key
    MAX_UPLOAD_MB: int = 10
    DELETE_AFTER_MINUTES: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# ---------------- App & Middleware ----------------

app = FastAPI(title="NanoBanana Try-On (FastAPI)")

# Add CORS middleware FIRST to handle preflight requests properly
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
if not origins:
    origins = ["*"]  # Fallback to allow all origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add security middleware for proper HTTPS handling behind Render's proxy
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(HTTPSRedirectMiddleware)

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
    # Log configuration status
    logger.info(f"FAL_KEY configured: {bool(settings.FAL_KEY)}")
    logger.info(f"Allowed origins: {origins}")

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
    return {
        "ok": True,
        "fal_configured": bool(settings.FAL_KEY),
        "allowed_origins": origins
    }

@app.get("/test-connectivity")
async def test_connectivity():
    """Test network connectivity to external services"""
    results = {}
    
    # Test basic internet connectivity
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://httpbin.org/get")
            results["internet"] = {"status": "ok", "status_code": response.status_code}
    except Exception as e:
        results["internet"] = {"status": "error", "error": str(e)}
    
    # Test FAL API connectivity
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.fal.ai/health")
            results["fal_api"] = {"status": "ok", "status_code": response.status_code}
    except Exception as e:
        results["fal_api"] = {"status": "error", "error": str(e)}
    
    # Test DNS resolution
    import socket
    try:
        socket.gethostbyname("api.fal.ai")
        results["dns"] = {"status": "ok", "resolved": True}
    except Exception as e:
        results["dns"] = {"status": "error", "error": str(e)}
    
    return results

@app.get("/diagnose")
async def diagnose():
    """Comprehensive diagnostic information"""
    import os
    import socket
    import platform
    
    results = {
        "environment": {},
        "network": {},
        "dns": {},
        "render_info": {}
    }
    
    # Environment variables
    results["environment"] = {
        "FAL_KEY_set": bool(os.getenv("FAL_KEY")),
        "FAL_KEY_length": len(os.getenv("FAL_KEY", "")),
        "RENDER": os.getenv("RENDER", "false"),
        "PORT": os.getenv("PORT", "not_set"),
        "PYTHON_VERSION": platform.python_version(),
        "PLATFORM": platform.platform()
    }
    
    # Network information
    try:
        hostname = socket.gethostname()
        results["network"]["hostname"] = hostname
        results["network"]["local_ip"] = socket.gethostbyname(hostname)
    except Exception as e:
        results["network"]["error"] = str(e)
    
    # DNS tests
    dns_hosts = ["api.fal.ai", "google.com", "cloudflare.com", "render.com"]
    for host in dns_hosts:
        try:
            ip = socket.gethostbyname(host)
            results["dns"][host] = {"status": "ok", "ip": ip}
        except Exception as e:
            results["dns"][host] = {"status": "error", "error": str(e)}
    
    # Render-specific environment variables
    render_vars = [
        "RENDER", "RENDER_EXTERNAL_URL", "RENDER_EXTERNAL_HOSTNAME",
        "RENDER_SERVICE_ID", "RENDER_SERVICE_NAME", "RENDER_SERVICE_TYPE",
        "RENDER_GIT_BRANCH", "RENDER_GIT_COMMIT", "RENDER_GIT_REPO_SLUG"
    ]
    
    for var in render_vars:
        value = os.getenv(var)
        if value:
            results["render_info"][var] = value
    
    return results

@app.post("/api/tryon")
@limiter.limit("20/minute")
async def api_tryon(
    request: Request,
    person: UploadFile = File(...),
    garmentUrl: str = Form(...),
    category: Optional[str] = Form(None),
    promptExtra: Optional[str] = Form(None),
):
    try:
        logger.info(f"Try-on request from {request.client.host if request.client else 'unknown'}")
        
        # Check if FAL_KEY is configured
        if not settings.FAL_KEY:
            logger.error("FAL_KEY not configured")
            raise HTTPException(status_code=500, detail="Service not properly configured")
        
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
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            raise HTTPException(status_code=400, detail="Image processing failed")

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
        except Exception as e:
            logger.warning(f"EXIF rotation failed: {e}")

        img = _strip_exif(img)
        img = _resize_max(img, 1536)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92, optimize=True)
        buf.seek(0)

        # Save selfie to tmp and expose a public URL so FAL can fetch it
        name = _random_name("jpg")
        path = TMP_DIR / name
        try:
            with open(path, "wb") as f:
                f.write(buf.getvalue())
        except Exception as e:
            logger.error(f"Failed to save temp file: {e}")
            raise HTTPException(status_code=500, detail="Failed to process image")
            
        uploaded_index[name] = datetime.utcnow() + timedelta(minutes=settings.DELETE_AFTER_MINUTES)

        person_url = _public_tmp_url(name)
        logger.info(f"Processing try-on with person_url: {person_url}, garment_url: {garmentUrl}")

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
            logger.error(f"FAL provider error: {e}")
            raise HTTPException(status_code=502, detail=f"Upstream failure: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in FAL provider: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

        generated_index[url] = datetime.utcnow() + timedelta(minutes=settings.DELETE_AFTER_MINUTES)

        logger.info(f"Try-on completed successfully, result URL: {url}")
        return TryOnResult(
            imageUrl=url,
            description=desc or "Generated by NanoBanana",
            requestId=request_id,
            ttlMinutes=settings.DELETE_AFTER_MINUTES,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in try-on endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Root page (optional tiny check)
@app.get("/")
def root():
    return HTMLResponse("<h1>NanoBanana Try-On (FastAPI)</h1><p>See <code>/frontend/tryon-widget.js</code> and <code>/api/tryon</code>.</p>")
