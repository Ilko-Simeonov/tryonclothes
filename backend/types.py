from pydantic import BaseModel, Field
from typing import Literal, Optional

Category = Literal["top", "dress", "outerwear", "bottom"]

class TryOnPayload(BaseModel):
    garmentUrl: str
    category: Optional[Category] = None
    promptExtra: Optional[str] = Field(default=None, max_length=400)

class TryOnResult(BaseModel):
    imageUrl: str
    description: str
    requestId: str
    ttlMinutes: int
