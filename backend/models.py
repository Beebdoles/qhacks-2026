from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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
    audio_path: str | None = Field(default=None, exclude=True)
    midi_path: str | None = Field(default=None, exclude=True)


class GeminiAnalysis(BaseModel):
    segments: list[Segment] = Field(description="List of audio segments.")


class SegmentMidiResult(BaseModel):
    segment_index: int
    segment_type: SegmentType
    midi_path: str | None = None
    start_offset: float
    instrument: str
    error: str | None = None


class JobStatus(BaseModel):
    id: str
    status: str  # pending | processing | complete | failed
    progress: int = 0
    stage: str = ""
    segments: list[Segment] = []
    midi_path: str | None = None
    error: str | None = None
