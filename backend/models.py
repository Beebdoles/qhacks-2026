from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field
from typing import List


class SegmentType(str, Enum):
    silence = "silence"
    speech = "speech"
    singing = "singing"
    humming = "humming"
    beatboxing = "beatboxing"


class Segment(BaseModel):
    start: float = Field(description="Start time of the segment.")
    end: float = Field(description="End time of the segment.")
    type: SegmentType = Field(description="Type of the segment.")


class Segments(BaseModel):
    segments: List[Segment] = Field(description="List of segments.")


class JobStatus(BaseModel):
    id: str
    status: str  # pending | processing | complete | failed
    progress: int = 0
    segments: list[Segment] = []
    error: str | None = None
