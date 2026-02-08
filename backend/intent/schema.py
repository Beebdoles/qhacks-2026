from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ToolName(str, Enum):
    mp3_to_midi = "mp3_to_midi"
    switch_instrument = "switch_instrument"
    pitch_shift = "pitch_shift"
    progression_change = "progression_change"
    repeat_track = "repeat_track"


class AudioSegmentRef(BaseModel):
    index: int = Field(description="Segment index from the analysis.")
    type: str = Field(description="Segment type (humming, singing, beatboxing, etc.).")
    path: str = Field(description="File path to the sliced audio clip.")


class ToolCall(BaseModel):
    tool: ToolName = Field(description="Which tool to invoke.")
    instruction: str = Field(description="Natural language description of what to do.")
    audio_segment: AudioSegmentRef | None = Field(
        default=None,
        description="The audio segment this tool call references. Required for mp3_to_midi.",
    )
    params: dict = Field(
        default_factory=dict,
        description="Tool-specific parameters (instrument, semitones, times, etc.).",
    )


class ToolPickerOutput(BaseModel):
    """Top-level output from the tool picker — a list of tool calls."""
    tool_calls: list[ToolCall] = Field(description="Ordered list of tool calls to execute.")
