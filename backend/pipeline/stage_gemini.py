import os
import time

from google import genai

from models import GeminiAnalysis
from pipeline.prompts import ANALYSIS_PROMPT

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def run_gemini_stage(job_id: str, audio_path: str) -> GeminiAnalysis:
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

    # Call Gemini with combined prompt + audio
    print(f"{tag} Analyzing audio...")
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[ANALYSIS_PROMPT, myfile],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": GeminiAnalysis.model_json_schema(),
        },
    )

    # Parse and validate
    result = GeminiAnalysis.model_validate_json(response.text)

    for seg in result.segments:
        print(f"{tag}   {seg.type.value}: {seg.start:.2f}-{seg.end:.2f}s")
    print(f"{tag} Done! {len(result.segments)} segments")

    return result
