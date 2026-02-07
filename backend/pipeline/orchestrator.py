import os
import subprocess
import time
import traceback

from google import genai

from models import JobStatus, Segments

# In-memory job store
jobs: dict[str, JobStatus] = {}

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT = """Analyze the provided audio file and produce a timeline of non-overlapping segments that covers the entire duration from start to finish.

Classify each segment as one of the following types:
- "silence": No meaningful audio activity, background noise, or non-vocal sounds.
- "speech": Spoken words or talking with no melody. These will likely be instructions or conversations. Do not confuse with singing with lyrics.
- "singing": Vocal singing with lyrics. These will likely be songs or vocal performances. Do not confuse with speech or humming.
- "humming": Vocal humming — melodic, closed-mouth vocalization without words. Do not confuse with speech or singing with lyrics.
- "beatboxing": Vocal percussion or beatboxing — rhythmic sounds produced with the mouth, lips, tongue, and voice to imitate drums and other instruments.

Requirements:
- Provide start and end timestamps in seconds (decimals allowed).
- Segments must be contiguous with no gaps: each segment's start must equal the previous segment's end.
- The first segment must start at 0 and the last segment must end at the total audio duration.
- Segments must not overlap.
- If audio is ambiguous, classify it as the closest matching type. Use "silence" for background noise or any non-vocal audio that doesn't fit the other categories.
"""


def run_gemini_analysis(job_id: str, audio_path: str) -> None:
    """Analyze audio using Gemini API and update job state."""
    job = jobs[job_id]
    job.status = "processing"

    try:
        # Convert WebM to MP3 (Gemini's JSON output fails on WebM input)
        upload_path = audio_path
        if audio_path.endswith(".webm"):
            mp3_path = audio_path.rsplit(".", 1)[0] + ".mp3"
            print(f"[gemini:{job_id[:8]}] Converting WebM to MP3...")
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, mp3_path],
                capture_output=True, check=True,
            )
            upload_path = mp3_path

        # Upload file to Gemini
        print(f"[gemini:{job_id[:8]}] Uploading audio to Gemini...")
        job.progress = 10
        myfile = client.files.upload(file=upload_path)
        job.progress = 20

        # Wait for Gemini to finish processing the file
        while myfile.state.name == "PROCESSING":
            print(f"[gemini:{job_id[:8]}] File still processing, waiting...")
            time.sleep(2)
            myfile = client.files.get(name=myfile.name)

        if myfile.state.name != "ACTIVE":
            raise RuntimeError(f"Gemini file processing failed with state: {myfile.state.name}")

        # Call Gemini for analysis
        print(f"[gemini:{job_id[:8]}] Analyzing audio segments...")
        job.progress = 30
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[PROMPT, myfile],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": Segments.model_json_schema(),
            },
        )

        # Parse response
        print(f"[gemini:{job_id[:8]}] Processing results...")
        job.progress = 80
        result = Segments.model_validate_json(response.text)

        job.segments = result.segments
        job.progress = 100
        job.status = "complete"

        for seg in result.segments:
            print(f"[gemini:{job_id[:8]}]   {seg.type.value}: {seg.start:.2f}-{seg.end:.2f}s")
        print(f"[gemini:{job_id[:8]}] Done! Found {len(result.segments)} segments")

    except Exception as e:
        job.status = "failed"
        job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
