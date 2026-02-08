from __future__ import annotations

import os

from models import Segment, SegmentType
from pydantic import ValidationError

from intent.prompts import TOOL_PICKER_PROMPT
from intent.schema import ToolPickerOutput

MODEL = "gemini-2.0-flash"

MUSICAL_TYPES = {SegmentType.singing, SegmentType.humming, SegmentType.beatboxing}

_client = None


def _get_client():
    """Lazy-initialize the Gemini client (avoids crash when API key is absent during tests)."""
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def _build_segment_table(segments: list[Segment]) -> str:
    """Build a markdown table of non-silence segments with index, type, path, and chords."""
    rows = []
    for i, seg in enumerate(segments):
        if seg.type == SegmentType.silence:
            continue
        if seg.type not in MUSICAL_TYPES:
            continue

        chords = ""
        if seg.chords:
            degrees = [str(c.degree) for c in seg.chords]
            chords = " → ".join(degrees)

        path = seg.audio_clip_path or ""
        rows.append(f"| {i} | {seg.type.value} | {path} | {chords} |")

    if not rows:
        return "(no musical segments)"

    header = "| index | type | path | chords |\n|---|---|---|---|"
    return header + "\n" + "\n".join(rows)


def pick_tools(instruction_doc: str, segments: list[Segment]) -> ToolPickerOutput:
    """Feed the full instruction doc + segment table to Gemini and get back tool calls.

    Args:
        instruction_doc: The interleaved timeline from stage_transcribe
            (speech transcriptions + musical segment summaries with file paths).
        segments: The full list of Segment objects from GeminiAnalysis.

    Returns:
        ToolPickerOutput with a list of ToolCall objects.
    """
    tag = "[tool-picker]"

    segment_table = _build_segment_table(segments)

    prompt = (
        f"{TOOL_PICKER_PROMPT}\n\n"
        f"## Timeline\n\n{instruction_doc}\n\n"
        f"## Segment reference table\n\n{segment_table}\n\n"
        f"Now output the tool_calls JSON."
    )

    print(f"{tag} Calling Gemini with full instruction doc ({len(instruction_doc)} chars)...")

    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=[prompt],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": ToolPickerOutput.model_json_schema(),
        },
    )

    print(f"{tag} Raw response: {response.text[:300]}")

    try:
        result = ToolPickerOutput.model_validate_json(response.text)
        print(f"{tag} Parsed {len(result.tool_calls)} tool call(s)")
        return result
    except ValidationError as e:
        print(f"{tag} Validation failed: {e}")
        return ToolPickerOutput(tool_calls=[])
