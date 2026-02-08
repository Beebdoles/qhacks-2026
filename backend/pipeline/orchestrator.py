import os
import subprocess
import traceback

from models import JobStatus
from pipeline.stage_gemini import run_gemini_stage
from pipeline.stage_transcribe import run_transcribe_stage
from pipeline.stage_score_builder import run_score_builder_stage
from pipeline.stage_instrument_mapper import run_instrument_mapper_stage
from pipeline.stage_midi_merger import run_midi_merger_stage

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

        # ── Stage 1: Gemini Analysis ────────────────────────────────
        job.stage = "gemini_analysis"
        job.progress = 5
        print(f"{tag} Stage 1: Gemini analysis...")

        analysis = run_gemini_stage(job_id, upload_path)

        job.segments = analysis.segments
        job.progress = 40
        print(f"{tag} Stage 1 complete. {len(analysis.segments)} segments.")

        # ── Stage 1.5: Speech Transcription ───────────────────────
        job.stage = "speech_transcription"
        job.progress = 42
        print(f"{tag} Stage 1.5: Transcribing speech segments...")

        instruction_doc = run_transcribe_stage(analysis, upload_path, job_id)

        job.instruction_doc = instruction_doc
        job.progress = 50
        print(f"{tag} Stage 1.5 complete.")

        # ── Stage 2: Score Builder ──────────────────────────────────
        job.stage = "score_building"
        job.progress = 45
        print(f"{tag} Stage 2: Building MusicLang scores...")

        per_type_midis = run_score_builder_stage(analysis, job_dir)

        job.progress = 65
        print(f"{tag} Stage 2 complete. {len(per_type_midis)} type MIDIs.")

        # ── Stage 3: Instrument Mapper ──────────────────────────────
        job.stage = "instrument_mapping"
        job.progress = 70
        print(f"{tag} Stage 3: Mapping instruments...")

        mapped_midis = run_instrument_mapper_stage(
            per_type_midis, analysis.singing_instrument, job_dir
        )

        job.progress = 80
        print(f"{tag} Stage 3 complete.")

        # ── Stage 4: MIDI Merger ────────────────────────────────────
        job.stage = "midi_merging"
        job.progress = 85
        print(f"{tag} Stage 4: Merging MIDI tracks...")

        output_path = os.path.join(job_dir, "output.mid")
        run_midi_merger_stage(mapped_midis, output_path)

        job.midi_path = output_path
        job.progress = 100
        job.stage = "complete"
        job.status = "complete"
        print(f"{tag} Pipeline complete! MIDI at {output_path}")

    except Exception as e:
        job.status = "failed"
        job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        print(f"{tag} FAILED: {type(e).__name__}: {e}")
