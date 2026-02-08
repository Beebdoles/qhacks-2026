from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class NoteEvent(BaseModel):
    pitch: int = Field(description="MIDI note number (0-127).")
    start: float = Field(description="Start time in seconds.")
    end: float = Field(description="End time in seconds.")
    velocity: int = Field(ge=0, le=127, description="Note velocity (0-127).")


class SegmentType(str, Enum):
    silence = "silence"
    speech = "speech"
    singing = "singing"
    humming = "humming"
    beatboxing = "beatboxing"


class Duration(str, Enum):
    w = "w"
    h = "h"
    q = "q"
    e = "e"
    s = "s"


class NoteData(BaseModel):
    s: int = Field(ge=0, le=6, description="Scale degree (0-6).")
    octave: int = Field(default=0, description="Octave offset.")
    duration: Duration = Field(default=Duration.q, description="Note duration code.")


class ChordData(BaseModel):
    degree: int = Field(ge=1, le=7, description="Chord degree (1-7).")
    duration_beats: float = Field(description="Duration in quarter-note beats.")
    instruments: dict[str, list[NoteData]] = Field(
        default_factory=dict,
        description="Per-instrument melody lines.",
    )


class Tonality(BaseModel):
    degree: int = Field(ge=1, le=7, description="Tonality root degree (1-7).")
    quality: Literal["M", "m"] = Field(description="Major (M) or minor (m).")


class SingingInstrument(str, Enum):
    piano = "piano"
    flute = "flute"


class Segment(BaseModel):
    start: float = Field(description="Start time of the segment.")
    end: float = Field(description="End time of the segment.")
    type: SegmentType = Field(description="Type of the segment.")
    chords: list[ChordData] = Field(
        default_factory=list,
        description="Chord progressions for this segment.",
    )


class GeminiAnalysis(BaseModel):
    tempo_bpm: int = Field(description="Tempo in BPM.")
    time_signature: list[int] = Field(description="Time signature as [beats, unit].")
    tonality: Tonality = Field(description="Key/tonality of the piece.")
    singing_instrument: SingingInstrument = Field(
        default=SingingInstrument.piano,
        description="Instrument for singing/humming tracks.",
    )
    segments: list[Segment] = Field(description="List of audio segments with chords.")


class JobStatus(BaseModel):
    id: str
    status: str  # pending | processing | complete | failed
    progress: int = 0
    stage: str = ""
    segments: list[Segment] = []
    midi_path: str | None = None
    error: str | None = None
