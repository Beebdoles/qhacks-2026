import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, UploadFile

from models import JobStatus
from pipeline.orchestrator import jobs, run_gemini_analysis

router = APIRouter(prefix="/api")

_executor = ThreadPoolExecutor(max_workers=2)

ALLOWED_EXTENSIONS = {".mp3", ".webm"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload")
async def upload_audio(file: UploadFile):
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: MP3, WebM.",
        )

    # Read file and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    # Create job directory and save file
    job_id = str(uuid.uuid4())
    job_dir = os.path.join("/tmp", "audio_midi_jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)

    input_path = os.path.join(job_dir, f"input{ext}")
    with open(input_path, "wb") as f:
        f.write(content)

    # Initialize job
    jobs[job_id] = JobStatus(id=job_id, status="pending", progress=0)

    # Launch Gemini analysis in background
    _executor.submit(run_gemini_analysis, job_id, input_path)

    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
