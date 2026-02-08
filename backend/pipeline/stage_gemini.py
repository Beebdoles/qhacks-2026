from __future__ import annotations

import os
import time

from google import genai

from models import GeminiAnalysis, NoteEvent
from pipeline.prompts import ANALYSIS_PROMPT, format_extracted_notes

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def run_gemini_stage(
    job_id: str,
    audio_path: str,
    extracted_notes: list[NoteEvent] | None = None,
) -> GeminiAnalysis:
    """Upload audio to Gemini and return a validated GeminiAnalysis."""
    tag = f"[gemini:{job_id[:8]}]"

    # Upload file to Gemini Files API
    print(f"{tag} Uploading audio to Gemini...")
    myfile = client.files.upload(file=audio_path)

    # Wait for ACTIVE state
    while myfile.state.name == "PROCESSING":
        print(f"{tag} File still processing, waiting...")
        time.sleep(2)
        myfile = client.files.get(name=myfile.name)

    if myfile.state.name != "ACTIVE":
        raise RuntimeError(
            f"Gemini file processing failed with state: {myfile.state.name}"
        )

    # Build prompt with optional extracted notes
    prompt = ANALYSIS_PROMPT
    if extracted_notes:
        notes_section = format_extracted_notes(extracted_notes)
        prompt = prompt + notes_section
        print(f"{tag} Including {len(extracted_notes)} extracted notes in prompt")

    # Call Gemini with combined prompt + audio
    print(f"{tag} Analyzing audio...")
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[prompt, myfile],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": GeminiAnalysis.model_json_schema(),
        },
    )

    # Dump prompt and response to debug files
    job_dir = os.path.dirname(audio_path)
    with open(os.path.join(job_dir, "debug_gemini_prompt.txt"), "w") as f:
        f.write(prompt)
    with open(os.path.join(job_dir, "debug_gemini_response.txt"), "w") as f:
        f.write(response.text)
    print(f"{tag} Wrote debug files: debug_gemini_prompt.txt, debug_gemini_response.txt")

    # Parse and validate
    result = GeminiAnalysis.model_validate_json(response.text)

    for seg in result.segments:
        print(f"{tag}   {seg.type.value}: {seg.start:.2f}-{seg.end:.2f}s ({len(seg.chords)} chords)")
    print(f"{tag} Done! {len(result.segments)} segments, tempo={result.tempo_bpm}")

    return result
