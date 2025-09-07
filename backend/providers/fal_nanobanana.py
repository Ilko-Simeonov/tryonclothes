"""
MIT License — NanoBanana Try-On provider (FAL)
Uses FAL's REST run API for the model "fal-ai/nano-banana/edit".
We provide generic polling. Adjust if your FAL plan exposes a different schema.
"""

from __future__ import annotations
import os
import time
import httpx
from typing import Dict, Any, Optional, Tuple, Callable

FAL_KEY = os.getenv("FAL_KEY", "")

FAL_RUN_URL = "https://api.fal.ai/v1/run/fal-ai/nano-banana/edit"

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

    payload = {
        "input": {
            "prompt": build_prompt(category, prompt_extra),
            "image_urls": [person_url, garment_url],
            "output_format": "jpeg",
            "num_images": 1,
        }
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(FAL_RUN_URL, headers=headers, json=payload)
        if r.status_code >= 400:
            raise FalError(f"FAL run failed: {r.status_code} {r.text}")

        data = r.json()
        # Best effort: either immediate image list or a request we need to poll.
        images = (data.get("images") or data.get("data", {}).get("images")) or []
        description = data.get("description") or data.get("data", {}).get("description") or ""
        request_id = data.get("request_id") or data.get("requestId") or data.get("request", {}).get("id") or "unknown"

        if images:
            first = images[0]
            url = first.get("url")
            if not url:
                raise FalError("FAL response had no image url")
            return (url, description, request_id)

        # If the provider returns a status URL, poll it (schema may differ; this is a generic fallback).
        status_url = data.get("status_url") or data.get("request", {}).get("status_url")
        if not status_url:
            # Some variants return a queue + stream log endpoint. Without it, we can only fail gracefully.
            raise FalError("FAL did not return images or a status_url; adjust provider integration")

        t0 = time.time()
        while time.time() - t0 < timeout_s:
            sr = await client.get(status_url, headers=headers)
            if sr.status_code >= 400:
                raise FalError(f"FAL status failed: {sr.status_code} {sr.text}")
            sd = sr.json()

            if on_progress:
                for log in (sd.get("logs") or []):
                    msg = log.get("message")
                    if msg:
                        on_progress(msg)

            images = (sd.get("images") or sd.get("data", {}).get("images")) or []
            description = sd.get("description") or sd.get("data", {}).get("description") or description

            if images:
                url = images[0].get("url")
                if not url:
                    raise FalError("FAL status response had no image url")
                return (url, description or "", request_id)

            time.sleep(1.0)

        raise FalError("FAL polling timed out")
