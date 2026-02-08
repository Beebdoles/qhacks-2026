import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from models import JobStatus
from pipeline.orchestrator import jobs, run_pipeline

router = APIRouter(prefix="/api")

_executor = ThreadPoolExecutor(max_workers=2)

ALLOWED_EXTENSIONS = {".mp3", ".webm"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload")
async def upload_audio(file: UploadFile):
    print(f"[upload] Received file: {file.filename}")

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
    print(f"[upload] File transfer complete: {len(content)} bytes")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    # Create job directory and save file
    job_id = str(uuid.uuid4())
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    job_dir = os.path.join(os.path.dirname(backend_dir), "jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)

    input_path = os.path.join(job_dir, f"input{ext}")
    with open(input_path, "wb") as f:
        f.write(content)
    print(f"[upload] File saved to {input_path}")

    # Initialize job
    jobs[job_id] = JobStatus(id=job_id, status="pending", progress=0)

    # Launch full pipeline in background
    _executor.submit(run_pipeline, job_id, input_path)

    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/instructions")
async def upload_instructions(job_id: str, file: UploadFile):
    """Save an instruction audio file to the job directory."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    # Find job directory from existing midi_path or reconstruct it
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    job_dir = os.path.join(os.path.dirname(backend_dir), "jobs", job_id)
    if not os.path.isdir(job_dir):
        raise HTTPException(status_code=404, detail="Job directory not found")

    # Increment filename: instructions_1.mp3, instructions_2.mp3, ...
    n = 1
    while os.path.exists(os.path.join(job_dir, f"instructions_{n}{ext}")):
        n += 1
    filename = f"instructions_{n}{ext}"
    path = os.path.join(job_dir, filename)
    with open(path, "wb") as f:
        f.write(content)

    print(f"[upload] Saved instruction audio: {path} ({len(content)} bytes)")
    return {"status": "ok", "filename": filename}


@router.get("/jobs/{job_id}/midi")
async def get_midi(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.midi_path or not os.path.isfile(job.midi_path):
        raise HTTPException(status_code=404, detail="MIDI not ready yet")
    return FileResponse(
        job.midi_path,
        media_type="audio/midi",
        filename="output.mid",
    )
