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
# Try different query endpoints
KIE_QUERY_URLS = [
    "https://api.kie.ai/api/v1/jobs/queryTask",  # Original
    "https://api.kie.ai/api/v1/jobs/getTask",    # Alternative 1
    "https://api.kie.ai/api/v1/jobs/task",       # Alternative 2
    "https://api.kie.ai/api/v1/task",            # Alternative 3
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
            
            # Try different query endpoints
            query_success = False
            for query_url in KIE_QUERY_URLS:
                try:
                    logger.info(f"Trying query endpoint: {query_url}")
                    
                    # Poll for completion
                    t0 = time.time()
                    while time.time() - t0 < timeout_s:
                        try:
                            # Try different query payload formats
                            query_payloads = [
                                {"taskId": task_id},
                                {"task_id": task_id},
                                {"id": task_id},
                                task_id  # Some APIs expect just the ID
                            ]
                            
                            query_success = False
                            for query_payload in query_payloads:
                                try:
                                    if isinstance(query_payload, str):
                                        # For GET requests with ID in URL
                                        url_with_id = f"{query_url}/{task_id}"
                                        sr = await client.get(url_with_id, headers=headers)
                                    else:
                                        # For POST requests with payload
                                        sr = await client.post(query_url, headers=headers, json=query_payload)
                                    
                                    logger.info(f"Query response status: {sr.status_code}")
                                    
                                    if sr.status_code == 404:
                                        logger.warning(f"Query endpoint {query_url} not found, trying next...")
                                        break
                                    
                                    if sr.status_code >= 400:
                                        logger.warning(f"Query failed with payload {query_payload}: {sr.status_code} {sr.text}")
                                        continue
                                    
                                    sd = sr.json()
                                    logger.info(f"Query response: {sd}")
                                    
                                    if sd.get("code") != 200:
                                        logger.warning(f"Query error: {sd.get('message', 'Unknown error')}")
                                        continue
                                    
                                    task_data = sd.get("data", {})
                                    state = task_data.get("state")
                                    
                                    if state == "success":
                                        # Parse result
                                        result_json = task_data.get("resultJson")
                                        if result_json:
                                            result_data = json.loads(result_json)
                                            result_urls = result_data.get("resultUrls", [])
                                            
                                            if result_urls:
                                                url = result_urls[0]
                                                description = f"Generated by Nano Banana via Kie.ai"
                                                request_id = task_id
                                                
                                                logger.info(f"Task completed successfully, result URL: {url}")
                                                return (url, description, request_id)
                                            else:
                                                raise FalError("No result URLs in successful response")
                                        else:
                                            raise FalError("No result JSON in successful response")
                                    
                                    elif state == "fail":
                                        fail_msg = task_data.get("failMsg", "Unknown error")
                                        raise FalError(f"Task failed: {fail_msg}")
                                    
                                    # Task still processing
                                    if on_progress:
                                        on_progress(f"Processing... (elapsed: {int(time.time() - t0)}s)")
                                    
                                    query_success = True
                                    break
                                
                                except Exception as e:
                                    logger.warning(f"Query attempt failed: {e}")
                                    continue
                            
                            if not query_success:
                                break
                            
                            await asyncio.sleep(2.0)  # Wait 2 seconds before next poll
                            
                        except Exception as e:
                            logger.error(f"Error polling task status: {e}")
                            raise FalError(f"Error polling task status: {e}")
                    
                    if query_success:
                        break
                        
                except Exception as e:
                    logger.warning(f"Query endpoint {query_url} failed: {e}")
                    continue
            
            if not query_success:
                raise FalError("All query endpoints failed")
            
            raise FalError("Task polling timed out")
            
    except httpx.ConnectError as e:
        logger.error(f"Connection error to Kie.ai API: {e}")
        raise FalError(f"Failed to connect to Kie.ai API: {e}")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error to Kie.ai API: {e}")
        raise FalError(f"Timeout connecting to Kie.ai API: {e}")
    except Exception as e:
        logger.error(f"Unexpected error calling Kie.ai API: {e}")
        raise FalError(f"Unexpected error: {e}")
