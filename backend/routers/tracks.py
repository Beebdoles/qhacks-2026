import os
import glob

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api")

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_TRACKS_DIR = os.path.join(_BACKEND_DIR, "saved_tracks")


@router.get("/tracks")
async def list_tracks():
    """Return a list of all saved MIDI tracks."""
    os.makedirs(SAVED_TRACKS_DIR, exist_ok=True)
    tracks = []
    for path in sorted(glob.glob(os.path.join(SAVED_TRACKS_DIR, "*.mid"))):
        filename = os.path.basename(path)
        tracks.append({
            "filename": filename,
            "url": f"/api/tracks/{filename}/midi",
        })
    return tracks


@router.get("/tracks/{filename}/midi")
async def get_track(filename: str):
    """Serve an individual saved track MIDI file."""
    # Prevent directory traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = os.path.join(SAVED_TRACKS_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Track '{filename}' not found")

    return FileResponse(path, media_type="audio/midi", filename=filename)
