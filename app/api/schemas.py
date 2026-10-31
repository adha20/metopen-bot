from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    text: str = Field(..., description="Pesan teks mentah yang akan dianalisis")
    author_id: str | None = Field(default=None, description="Discord User ID pengirim")
    author_name: str | None = Field(default=None, description="Username pengirim")
    channel_id: str | None = Field(default=None, description="ID Channel pesan")
    guild_id: str | None = Field(default=None, description="ID Server/Guild Discord")


class PredictionResponse(BaseModel):
    raw_text: str
    cleaned_text: str
    latency_ms: float
    is_violation: bool
    severity: str
    action: str
    strike_points: int
    violation_category: str
    victim_mentions: list[str]
    active_labels: list[str]
    probabilities: dict[str, float]
    thresholds: dict[str, float]


class HealthResponse(BaseModel):
    status: str
    service: str
    device: str
    model_loaded: bool

