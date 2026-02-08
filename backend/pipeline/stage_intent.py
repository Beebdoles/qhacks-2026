from __future__ import annotations

import glob
import json
import os

from models import GeminiAnalysis
from intent.parser import pick_tools
from intent.normalize import normalize_params

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAVED_TRACKS_DIR = os.path.join(_BACKEND_DIR, "saved_tracks")


def run_intent_stage(
    instruction_doc: str, analysis: GeminiAnalysis | None, job_id: str, job_dir: str
) -> list[dict]:
    """Feed the instruction doc to Gemini and get back a list of tool calls.

    Returns the action log as a list of dicts (one per tool call).
    """
    tag = f"[intent:{job_id[:8]}]"

    print(f"{tag} Running tool picker on instruction doc ({len(instruction_doc)} chars)...")

    # Discover saved track names so the LLM can match user references
    available_tracks: list[str] = []
    if os.path.isdir(_SAVED_TRACKS_DIR):
        for path in sorted(glob.glob(os.path.join(_SAVED_TRACKS_DIR, "*.mid"))):
            available_tracks.append(os.path.splitext(os.path.basename(path))[0])
    if available_tracks:
        print(f"{tag} Available tracks: {available_tracks}")

    segments = analysis.segments if analysis else []
    result = pick_tools(instruction_doc, segments, available_tracks=available_tracks)

    # Normalize params for each tool call
    for tc in result.tool_calls:
        tc.params = normalize_params(tc.tool, tc.params)

    # Serialize to list of dicts
    action_log = [tc.model_dump() for tc in result.tool_calls]

    # Write to backend/log_files/
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log_files")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"action_log_{job_id}.json")
    with open(log_path, "w") as f:
        json.dump(action_log, f, indent=2)

    print(f"{tag} Tool picker complete. {len(action_log)} tool call(s) → {log_path}")
    return action_log
