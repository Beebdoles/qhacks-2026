# Tool dispatcher — routes a ToolCall to the correct tool function.
from __future__ import annotations

import os
import glob
import shutil

from intent.schema import ToolCall, ToolName
from tools.pitch_shift import run_pitch_shift
from tools.progression_change import run_progression_change
from tools.switch_instrument import run_switch_instrument
from tools.repeat_track import run_repeat_track


# Default location for user's saved tracks
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_TRACKS_DIR = os.path.join(_BACKEND_DIR, "saved_tracks")


def _words_overlap(description: str, filename: str) -> bool:
    """Check if any significant word in the description matches the filename."""
    stop_words = {"the", "a", "an", "track", "my", "that", "this"}
    # Split both into words, compare
    desc_words = {w for w in description.split() if w not in stop_words and len(w) > 1}
    name_parts = set(filename.replace("_", " ").replace("-", " ").split())
    return bool(desc_words & name_parts)


def resolve_midi_path(tool_call: ToolCall, job_dir: str) -> str:
    """Find the MIDI file a tool call should operate on.

    Resolution order:
      1. If target_description matches a file in saved_tracks/ → use that
      2. If the job_dir has per-type MIDIs (singing.mid, etc.) → best match
      3. If the job_dir has a merged output.mid → use that
    """
    target = (tool_call.params.get("target_description") or "").strip().lower()

    # 1. Check saved_tracks/ — return path directly so tools modify in place
    if os.path.isdir(SAVED_TRACKS_DIR):
        saved = sorted(glob.glob(os.path.join(SAVED_TRACKS_DIR, "*.mid")))
        if target:
            # Match by name when a target is specified
            for path in saved:
                name = os.path.splitext(os.path.basename(path))[0].lower()
                if name in target or target in name or _words_overlap(target, name):
                    return path
        elif len(saved) == 1:
            # Only one track — use it
            return saved[0]
        elif saved:
            # Multiple tracks, no target — fall through to let tool pick
            # but if nothing else matches below, use first saved track
            pass

    # 2. Check for per-type MIDIs in job dir that match the description
    if target:
        for path in glob.glob(os.path.join(job_dir, "*.mid")):
            name = os.path.splitext(os.path.basename(path))[0].lower()
            if name in target or target in name or _words_overlap(target, name):
                return path

    # 3. Check for output.mid in job dir
    output_mid = os.path.join(job_dir, "output.mid")
    if os.path.isfile(output_mid):
        return output_mid

    # 4. Fallback: first .mid in job dir
    mids = sorted(glob.glob(os.path.join(job_dir, "*.mid")))
    if mids:
        return mids[0]

    # 5. Fallback: first .mid in saved_tracks/
    if os.path.isdir(SAVED_TRACKS_DIR):
        saved = sorted(glob.glob(os.path.join(SAVED_TRACKS_DIR, "*.mid")))
        if saved:
            return saved[0]

    raise FileNotFoundError(
        f"No MIDI file found for target {target!r} in saved_tracks/ or {job_dir}"
    )


def dispatch_tool_call(tool_call: ToolCall, job_dir: str) -> str:
    """Route a single ToolCall to the appropriate tool function.

    Args:
        tool_call: The parsed and normalized ToolCall from the intent stage.
        job_dir: Path to the current job's working directory.

    Returns:
        A summary string from the tool describing what it did.
    """
    tag = f"[dispatch]"

    if tool_call.tool == ToolName.pitch_shift:
        midi_path = resolve_midi_path(tool_call, job_dir)
        print(f"{tag} pitch_shift → {midi_path}")
        return run_pitch_shift(tool_call, midi_path)

    if tool_call.tool == ToolName.progression_change:
        midi_path = resolve_midi_path(tool_call, job_dir)
        print(f"{tag} progression_change → {midi_path}")
        return run_progression_change(tool_call, midi_path)

    if tool_call.tool == ToolName.switch_instrument:
        midi_path = resolve_midi_path(tool_call, job_dir)
        print(f"{tag} switch_instrument → {midi_path}")
        result = run_switch_instrument(tool_call, midi_path)

        # Rename the file in saved_tracks/ to match the new instrument,
        # replacing any existing file with that name
        new_instrument = tool_call.params.get("instrument", "")
        if new_instrument and midi_path.startswith(SAVED_TRACKS_DIR):
            new_path = os.path.join(SAVED_TRACKS_DIR, f"{new_instrument}.mid")
            if new_path != midi_path:
                os.replace(midi_path, new_path)
                print(f"{tag} Replaced {os.path.basename(midi_path)} → {os.path.basename(new_path)}")

        return result

    if tool_call.tool == ToolName.repeat_track:
        midi_path = resolve_midi_path(tool_call, job_dir)
        print(f"{tag} repeat_track → {midi_path}")
        return run_repeat_track(tool_call, midi_path)

    # TODO: wire up remaining tools
    # if tool_call.tool == ToolName.mp3_to_midi:
    #     return run_mp3_to_midi(tool_call, job_dir)

    raise NotImplementedError(f"Tool {tool_call.tool!r} is not yet implemented.")
