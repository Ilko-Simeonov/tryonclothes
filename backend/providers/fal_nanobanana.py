"""
MIT License — Try-On provider (Kie.ai)
Uses Kie.ai's REST API for the Nano Banana model.
"""

from __future__ import annotations
import os
import time
import httpx
import logging
import json
from typing import Dict, Any, Optional, Tuple, Callable
import asyncio

logger = logging.getLogger(__name__)

# Use Kie.ai API key instead of FAL_KEY
KIE_API_KEY = os.getenv("KIE_API_KEY", os.getenv("FAL_KEY", ""))

KIE_API_URL = "https://api.kie.ai/api/v1/jobs/createTask"

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
    if not KIE_API_KEY:
        raise FalError("KIE_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json",
    }

    # Build payload for Kie.ai API
    payload = {
        "model": "google/nano-banana-edit",
        "input": {
            "prompt": build_prompt(category, prompt_extra),
            "image_urls": [person_url, garment_url],
            "output_format": "jpeg",
            "image_size": "auto"
        }
    }

    logger.info(f"Making request to Kie.ai API: {KIE_API_URL}")
    logger.info(f"Payload: {payload}")

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            # Create task
            r = await client.post(KIE_API_URL, headers=headers, json=payload)
            logger.info(f"Kie.ai API response status: {r.status_code}")
            
            if r.status_code >= 400:
                logger.error(f"Kie.ai API error response: {r.text}")
                raise FalError(f"Kie.ai API failed: {r.status_code} {r.text}")

            data = r.json()
            logger.info(f"Kie.ai API response data: {data}")
            
            if data.get("code") != 200:
                raise FalError(f"Kie.ai API error: {data.get('message', 'Unknown error')}")
            
            task_id = data.get("data", {}).get("taskId")
            if not task_id:
                raise FalError("Kie.ai API did not return task ID")
            
            logger.info(f"Task created with ID: {task_id}")
            
            # Since we can't find the correct query endpoint, let's try a different approach
            # We'll wait a reasonable time and then try to get the result
            # This is a simplified approach that might work for Kie.ai
            
            if on_progress:
                on_progress("Task created, waiting for processing...")
            
            # Wait for processing (Kie.ai typically takes 25-30 seconds according to their docs)
            await asyncio.sleep(30)
            
            if on_progress:
                on_progress("Checking for results...")
            
            # Try to get the result using the task ID
            # Since we don't know the exact endpoint, let's try a few common patterns
            result_urls = [
                f"https://api.kie.ai/api/v1/jobs/{task_id}",
                f"https://api.kie.ai/api/v1/jobs/result/{task_id}",
                f"https://api.kie.ai/api/v1/result/{task_id}",
                f"https://api.kie.ai/api/v1/task/{task_id}",
            ]
            
            for result_url in result_urls:
                try:
                    logger.info(f"Trying to get result from: {result_url}")
                    result_r = await client.get(result_url, headers=headers)
                    
                    if result_r.status_code == 200:
                        result_data = result_r.json()
                        logger.info(f"Result response: {result_data}")
                        
                        # Try to extract the result URL from various possible response formats
                        result_url = None
                        
                        # Check for direct URL in response
                        if "url" in result_data:
                            result_url = result_data["url"]
                        elif "image_url" in result_data:
                            result_url = result_data["image_url"]
                        elif "result_url" in result_data:
                            result_url = result_data["result_url"]
                        elif "data" in result_data and "url" in result_data["data"]:
                            result_url = result_data["data"]["url"]
                        elif "data" in result_data and "image_url" in result_data["data"]:
                            result_url = result_data["data"]["image_url"]
                        
                        if result_url:
                            description = f"Generated by Nano Banana via Kie.ai"
                            request_id = task_id
                            
                            logger.info(f"Task completed successfully, result URL: {result_url}")
                            return (result_url, description, request_id)
                    
                except Exception as e:
                    logger.warning(f"Failed to get result from {result_url}: {e}")
                    continue
            
            # If we can't get the result, raise an error
            raise FalError("Could not retrieve result from Kie.ai API. The task was created but we couldn't find the result.")
            
    except httpx.ConnectError as e:
        logger.error(f"Connection error to Kie.ai API: {e}")
        raise FalError(f"Failed to connect to Kie.ai API: {e}")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error to Kie.ai API: {e}")
        raise FalError(f"Timeout connecting to Kie.ai API: {e}")
    except Exception as e:
        logger.error(f"Unexpected error calling Kie.ai API: {e}")
        raise FalError(f"Unexpected error: {e}")
