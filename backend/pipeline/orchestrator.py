import json
import os
import subprocess
import traceback

from models import JobStatus
from pipeline.melody import extract_melody
from pipeline.stage_gemini import run_gemini_stage
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

        # ── Stage 1: BasicPitch melody extraction ─────────────────
        job.stage = "pitch_detection"
        job.progress = 5
        print(f"{tag} Stage 1: BasicPitch melody extraction...")

        extracted_notes = extract_melody(upload_path)

        job.progress = 25
        print(f"{tag} Stage 1 complete. {len(extracted_notes)} notes extracted.")

        # Dump BasicPitch extracted notes
        with open(os.path.join(job_dir, "debug_basicpitch_notes.json"), "w") as f:
            json.dump([n.model_dump() for n in extracted_notes], f, indent=2)

        # ── Stage 2: Gemini Analysis (with extracted notes) ───────
        job.stage = "gemini_analysis"
        job.progress = 30
        print(f"{tag} Stage 2: Gemini analysis...")

        analysis = run_gemini_stage(job_id, upload_path, extracted_notes)

        job.segments = analysis.segments
        job.progress = 50
        print(f"{tag} Stage 2 complete. {len(analysis.segments)} segments.")

        # Dump parsed Gemini analysis
        with open(os.path.join(job_dir, "debug_gemini_analysis.json"), "w") as f:
            f.write(analysis.model_dump_json(indent=2))

        # ── Stage 3: Score Builder ──────────────────────────────────
        job.stage = "score_building"
        job.progress = 55
        print(f"{tag} Stage 3: Building MusicLang scores...")

        per_type_midis = run_score_builder_stage(analysis, job_dir, extracted_notes)

        job.progress = 70
        print(f"{tag} Stage 3 complete. {len(per_type_midis)} type MIDIs.")

        # ── Stage 4: Instrument Mapper ──────────────────────────────
        job.stage = "instrument_mapping"
        job.progress = 75
        print(f"{tag} Stage 4: Mapping instruments...")

        mapped_midis = run_instrument_mapper_stage(
            per_type_midis, analysis.singing_instrument, job_dir
        )

        job.progress = 85
        print(f"{tag} Stage 4 complete.")

        # ── Stage 5: MIDI Merger ────────────────────────────────────
        job.stage = "midi_merging"
        job.progress = 90
        print(f"{tag} Stage 5: Merging MIDI tracks...")

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
