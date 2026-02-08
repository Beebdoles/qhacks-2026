import os
import subprocess
import traceback

from models import JobStatus
from pipeline.stage_gemini import run_gemini_stage
from pipeline.stage_audio_splitter import run_audio_splitter_stage
# Future: from pipeline.stage_midi_merger import run_midi_merger_stage

# In-memory job store
jobs: dict[str, JobStatus] = {}


def run_pipeline(job_id: str, audio_path: str) -> None:
    """Run the full audio-to-MIDI pipeline and update job state."""
    job = jobs[job_id]
    job.status = "processing"
    job_dir = os.path.dirname(audio_path)
    tag = f"[pipeline:{job_id[:8]}]"

    try:
        # ── Pre-processing: WebM → MP3 if needed ────────────────────
        upload_path = audio_path
        if audio_path.endswith(".webm"):
            mp3_path = audio_path.rsplit(".", 1)[0] + ".mp3"
            print(f"{tag} Converting WebM to MP3...")
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, mp3_path],
                capture_output=True, check=True,
            )
            upload_path = mp3_path

        # ── Stage 1: Gemini Segmentation ─────────────────────────────
        job.stage = "gemini_analysis"
        job.progress = 5
        print(f"{tag} Stage 1: Gemini segmentation...")

        analysis = run_gemini_stage(job_id, upload_path)

        job.segments = analysis.segments
        job.progress = 50
        print(f"{tag} Stage 1 complete. {len(analysis.segments)} segments.")

        # ── Stage 2: Audio Splitting ─────────────────────────────────
        job.stage = "audio_splitting"
        job.progress = 55
        print(f"{tag} Stage 2: Splitting audio by segment...")

        non_silence_segments = run_audio_splitter_stage(
            analysis, upload_path, job_dir
        )

        job.segments = non_silence_segments
        job.progress = 100
        job.stage = "complete"
        job.status = "complete"
        print(f"{tag} Pipeline complete! {len(non_silence_segments)} non-silence segments.")

        # Future: MIDI merger stage
        # job.stage = "midi_merging"
        # output_path = os.path.join(job_dir, "output.mid")
        # run_midi_merger_stage(mapped_midis, output_path)
        # job.midi_path = output_path

    except Exception as e:
        job.status = "failed"
        job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        print(f"{tag} FAILED: {type(e).__name__}: {e}")
