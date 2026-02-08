#!/usr/bin/env python3
"""End-to-end test: RecordingC.mp3 → Gemini analysis → transcription → intent → tool dispatch."""
import os
import sys
import json
import uuid
import shutil

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pipeline.stage_gemini import run_gemini_stage
from pipeline.stage_transcribe import run_transcribe_stage
from pipeline.stage_intent import run_intent_stage
from pipeline.stage_score_builder import run_score_builder_stage
from pipeline.stage_instrument_mapper import run_instrument_mapper_stage
from pipeline.stage_midi_merger import run_midi_merger_stage
from intent.schema import ToolCall, ToolName
from tools.dispatch import dispatch_tool_call

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Accept filename as CLI arg, default to RecordingC.mp3
_default = "RecordingC.mp3"
_filename = sys.argv[1] if len(sys.argv) > 1 else _default
INPUT_FILE = os.path.join(BACKEND_DIR, "midi-inputs", _filename)


def main():
    assert os.path.isfile(INPUT_FILE), f"Input not found: {INPUT_FILE}"

    job_id = str(uuid.uuid4())
    job_dir = os.path.join("/tmp/audio_midi_jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)

    # Copy input into job dir (pipeline expects it there)
    input_path = os.path.join(job_dir, "input.mp3")
    shutil.copy2(INPUT_FILE, input_path)

    print(f"\n{'='*60}")
    print(f"  Test: {_filename} end-to-end pipeline")
    print(f"  Job ID: {job_id}")
    print(f"  Job dir: {job_dir}")
    print(f"{'='*60}\n")

    # ── Stage 1: Gemini Analysis ──────────────────────────────────
    print(">>> Stage 1: Gemini Analysis")
    analysis = run_gemini_stage(job_id, input_path)
    print(f"    Segments: {len(analysis.segments)}")
    print(f"    Tempo: {analysis.tempo_bpm} BPM")
    print(f"    Tonality: degree {analysis.tonality.degree} {analysis.tonality.quality}")
    print()

    # ── Stage 1.5: Speech Transcription ───────────────────────────
    print(">>> Stage 1.5: Speech Transcription")
    instruction_doc = run_transcribe_stage(analysis, input_path, job_id)
    print(f"\n--- Instruction Doc ---\n{instruction_doc}\n---\n")

    # ── Stage 1.75: Intent Parsing ────────────────────────────────
    print(">>> Stage 1.75: Intent Parsing")
    action_log = run_intent_stage(instruction_doc, analysis, job_id, job_dir)
    print(f"\n--- Action Log ({len(action_log)} calls) ---")
    print(json.dumps(action_log, indent=2))
    print("---\n")

    if not action_log:
        print("No tool calls produced. Nothing to dispatch.")
        return

    # ── Stage 2/3/4: Build MIDIs from musical segments ────────────
    # (So edit tools have something to operate on)
    print(">>> Building MIDIs from musical segments (stages 2-4)...")
    per_type_midis = run_score_builder_stage(analysis, job_dir)
    mapped_midis = run_instrument_mapper_stage(
        per_type_midis, analysis.singing_instrument, job_dir
    )
    output_path = os.path.join(job_dir, "output.mid")
    run_midi_merger_stage(mapped_midis, output_path)
    print(f"    Built output.mid ({os.path.getsize(output_path)} bytes)\n")

    # ── Tool Dispatch ─────────────────────────────────────────────
    print(">>> Dispatching tool calls...")
    for i, action in enumerate(action_log):
        tc = ToolCall(**action)
        print(f"\n  [{i+1}] {tc.tool.value}: {tc.instruction}")
        print(f"      params: {tc.params}")
        try:
            result = dispatch_tool_call(tc, job_dir)
            print(f"      ✓ {result}")
        except NotImplementedError as e:
            print(f"      ⏭ Skipped: {e}")
        except Exception as e:
            print(f"      ✗ Error: {e}")

    print(f"\n{'='*60}")
    print(f"  Done! Output at: {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
