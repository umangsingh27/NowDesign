"""Pydantic schemas for the NowPurchase Design Studio API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BriefInput(BaseModel):
    headline: str = Field(..., min_length=1, max_length=200)
    emotion: Literal[
        "inspiring", "professional", "urgent", "celebratory", "informative"
    ] = "professional"
    purpose: Literal[
        "product_feature", "testimonial", "announcement", "insight",
        "event", "case_study", "team", "product_launch"
    ] = "product_feature"
    body_copy: Optional[str] = Field(None, max_length=200)
    stat: Optional[str] = Field(None, max_length=50)
    attribution: Optional[str] = Field(None, max_length=100)
    cta: Optional[str] = Field(None, max_length=80)
    requested_by: Optional[str] = None
    logo_type: Literal["nowpurchase", "metalcloud", "combined"] = "nowpurchase"
    theme: Literal["dark", "light"] = "dark"


class StartSessionResponse(BaseModel):
    session_id: str
    status: Literal["generating", "dialogue"]
    questions: Optional[list[str]] = None


class AnswerInput(BaseModel):
    answers: list[str]


class FeedbackInput(BaseModel):
    message: str


class ApproveInput(BaseModel):
    user_rating: int = Field(default=3, ge=1, le=5)


class ApproveResponse(BaseModel):
    status: str
    final_image_url: str
    learning_agent_status: str


class KBAddInput(BaseModel):
    collection: Literal["brand_knowledge", "agent_memory"]
    content: str = Field(..., min_length=10)
    category: str
    topic: str


class SessionSummary(BaseModel):
    id: str
    created_at: Optional[datetime]
    state: str
    logo_type: Optional[str]
    theme: Optional[str]
    compliance_score: Optional[int]
    user_rating: Optional[int]
    requested_by: Optional[str]
    image_url: Optional[str]


class HealthResponse(BaseModel):
    status: str
    chromadb: str
    sqlite: str
    glass_renderer: str
