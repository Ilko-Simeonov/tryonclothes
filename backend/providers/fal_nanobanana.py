"""
MIT License — Try-On provider (FAL)
Uses FAL's REST run API for virtual try-on models.
"""

from __future__ import annotations
import os
import time
import httpx
import logging
from typing import Dict, Any, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

FAL_KEY = os.getenv("FAL_KEY", "")

# Try different API endpoints and models
FAL_ENDPOINTS = [
    "https://api.fal.ai/v1/run/google/nano-banana-edit",  # Based on the API docs
    "https://api.fal.ai/v1/run/fal-ai/nano-banana/edit",  # Original endpoint
    "https://api.fal.ai/v1/run/fal-ai/fashn/tryon/v1.5",  # Alternative try-on model
]

class FalError(Exception):
    pass

def build_prompt(category: Optional[str], extra: Optional[str]) -> str:
    base = (
        f"Replace the person's current {category or 'clothes'} with the garment shown in the second image. "
        "Preserve the person's identity, face, hairstyle, skin tone, body shape, pose and background. "
        "Make the fit realistic and natural with correct lighting and fabric drape. Keep hands and accessories intact. "
        "Avoid changing facial features."
    )
    if extra:
        base += f"\nExtra style guidance: {extra}"
    return base

async def try_on_with_fal_nanobanana(
    *,
    person_url: str,
    garment_url: str,
    category: Optional[str],
    prompt_extra: Optional[str],
    on_progress: Optional[Callable[[str], None]] = None,
    timeout_s: int = 120,
) -> Tuple[str, str, str]:
    if not FAL_KEY:
        raise FalError("FAL_KEY not configured")

    headers = {
        "Authorization": f"Bearer {FAL_KEY}",
        "Content-Type": "application/json",
    }

    # Try different endpoints until one works
    last_error = None
    for endpoint in FAL_ENDPOINTS:
        try:
            logger.info(f"Trying endpoint: {endpoint}")
            
            # Build payload based on endpoint
            if "nano-banana" in endpoint:
                # Nano-banana model payload (based on API docs)
                payload = {
                    "model": "google/nano-banana-edit",
                    "input": {
                        "image_urls": [person_url, garment_url],
                        "prompt": build_prompt(category, prompt_extra),
                    }
                }
            elif "fashn" in endpoint:
                # FASHN model payload
                payload = {
                    "input": {
                        "person_image_url": person_url,
                        "garment_image_url": garment_url,
                        "category": category or "top",
                        "prompt": build_prompt(category, prompt_extra),
                    }
                }
            else:
                # Generic payload
                payload = {
                    "input": {
                        "prompt": build_prompt(category, prompt_extra),
                        "image_urls": [person_url, garment_url],
                        "output_format": "jpeg",
                        "num_images": 1,
                    }
                }

            logger.info(f"Making request to: {endpoint}")
            logger.info(f"Payload: {payload}")

            async with httpx.AsyncClient(timeout=timeout_s) as client:
                r = await client.post(endpoint, headers=headers, json=payload)
                logger.info(f"Response status: {r.status_code}")
                
                if r.status_code >= 400:
                    logger.error(f"API error response: {r.text}")
                    last_error = f"Endpoint {endpoint} failed: {r.status_code} {r.text}"
                    continue

                data = r.json()
                logger.info(f"Response data: {data}")
                
                # Parse response
                images = []
                if "images" in data:
                    images = data["images"]
                elif "data" in data and "images" in data["data"]:
                    images = data["data"]["images"]
                elif "output" in data and "images" in data["output"]:
                    images = data["output"]["images"]
                
                if images:
                    first = images[0]
                    url = first.get("url")
                    if not url:
                        last_error = f"Endpoint {endpoint} response had no image url"
                        continue
                    
                    description = data.get("description") or data.get("data", {}).get("description") or ""
                    request_id = data.get("request_id") or data.get("requestId") or data.get("request", {}).get("id") or "unknown"
                    
                    logger.info(f"Success with endpoint {endpoint}, result URL: {url}")
                    return (url, description, request_id)
                
                # If no images, try polling
                status_url = data.get("status_url") or data.get("request", {}).get("status_url")
                if status_url:
                    logger.info(f"Polling status URL: {status_url}")
                    t0 = time.time()
                    while time.time() - t0 < timeout_s:
                        try:
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                sr = await client.get(status_url, headers=headers)
                                if sr.status_code >= 400:
                                    last_error = f"Status check failed: {sr.status_code} {sr.text}"
                                    break
                                sd = sr.json()

                                if on_progress:
                                    for log in (sd.get("logs") or []):
                                        msg = log.get("message")
                                        if msg:
                                            on_progress(msg)

                                images = sd.get("images") or sd.get("data", {}).get("images") or []
                                
                                if images:
                                    url = images[0].get("url")
                                    if not url:
                                        last_error = f"Status response had no image url"
                                        break
                                    description = sd.get("description") or sd.get("data", {}).get("description") or description
                                    request_id = sd.get("request_id") or sd.get("requestId") or sd.get("request", {}).get("id") or request_id
                                    logger.info(f"Success with endpoint {endpoint} after polling, result URL: {url}")
                                    return (url, description or "", request_id)

                                time.sleep(1.0)
                        except Exception as e:
                            logger.error(f"Error polling status: {e}")
                            last_error = f"Error polling status: {e}"
                            break
                    else:
                        last_error = f"Endpoint {endpoint} polling timed out"
                        continue
                else:
                    last_error = f"Endpoint {endpoint} did not return images or status_url"
                    continue
                    
        except httpx.ConnectError as e:
            logger.error(f"Connection error to {endpoint}: {e}")
            last_error = f"Failed to connect to {endpoint}: {e}"
            continue
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error to {endpoint}: {e}")
            last_error = f"Timeout connecting to {endpoint}: {e}"
            continue
        except Exception as e:
            logger.error(f"Unexpected error with {endpoint}: {e}")
            last_error = f"Unexpected error with {endpoint}: {e}"
            continue

    # If we get here, all endpoints failed
    raise FalError(f"All FAL endpoints failed. Last error: {last_error}")
