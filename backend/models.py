from __future__ import annotations

from pydantic import BaseModel


class Segment(BaseModel):
    start: float
    end: float
    type: str  # speech | humming | beatboxing | silence


class NoteEvent(BaseModel):
    pitch: int
    start: float
    end: float
    velocity: int


class DrumHit(BaseModel):
    time: float
    drum: str  # kick | snare | hihat


class Transcription(BaseModel):
    start: float
    end: float
    text: str


class JobStatus(BaseModel):
    id: str
    status: str  # pending | processing | complete | failed
    progress: int = 0
    segments: list[Segment] = []
    transcriptions: list[Transcription] = []
    midi_path: str | None = None
    error: str | None = None
