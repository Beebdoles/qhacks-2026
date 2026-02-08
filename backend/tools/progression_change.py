# progression_change — Change the key/scale of a track.
import os
import tempfile

import music21
import pretty_midi

from intent.schema import ToolCall

MIDI_NOTE_MIN = 0
MIDI_NOTE_MAX = 127

# Pitch class name -> semitone offset from C
_PITCH_CLASS = {
    "C": 0, "C#": 1, "D-": 1, "D": 2, "D#": 3, "E-": 3,
    "E": 4, "F": 5, "F#": 6, "G-": 6, "G": 7, "G#": 8,
    "A-": 8, "A": 9, "A#": 10, "B-": 10, "B": 11,
}

# Scale intervals (semitones from root)
_SCALE_INTERVALS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}


def _parse_scale_name(name: str) -> tuple[int, str]:
    """Parse a scale name like 'A minor' or 'F# major' into (root_pc, mode)."""
    parts = name.strip().split()
    if len(parts) < 2:
        raise ValueError(
            f"Invalid scale name: {name!r}. Expected format: 'C major', 'A minor', 'F# minor', etc."
        )

    mode = parts[-1].lower()
    root_name = " ".join(parts[:-1]).strip()

    if mode not in _SCALE_INTERVALS:
        raise ValueError(f"Unsupported mode: {mode!r}. Use 'major' or 'minor'.")

    pc = _PITCH_CLASS.get(root_name)
    if pc is None:
        raise ValueError(
            f"Unknown root note: {root_name!r}. "
            f"Valid: {', '.join(sorted(_PITCH_CLASS.keys()))}"
        )

    return pc, mode


def _detect_key(midi_path: str) -> tuple[int, str, str]:
    """Detect the key of a MIDI file using music21's Krumhansl-Schmuckler algorithm."""
    score = music21.converter.parse(midi_path)
    key = score.analyze("key")
    if key is None:
        raise RuntimeError("music21 could not detect a key from this MIDI file.")

    root_name = key.tonic.name
    mode = key.mode

    pc = _PITCH_CLASS.get(root_name)
    if pc is None:
        raise RuntimeError(f"music21 returned unexpected tonic: {root_name!r}")

    return pc, mode, f"{root_name} {mode}"


def _find_tracks(midi: pretty_midi.PrettyMIDI, description: str) -> list[pretty_midi.Instrument]:
    """Fuzzy-match a target_description against instrument/track names.

    Falls back to all non-drum instruments if no match found.
    """
    non_drum = [inst for inst in midi.instruments if not inst.is_drum]

    if not description:
        return non_drum

    desc_lower = description.strip().lower()
    matched = []
    for inst in midi.instruments:
        name = (inst.name or "").strip().lower()
        if name and (name in desc_lower or desc_lower in name):
            matched.append(inst)

    return matched if matched else non_drum


def _remap_note(
    pitch: int,
    src_root: int,
    src_intervals: list[int],
    dst_root: int,
    dst_intervals: list[int],
) -> int:
    """Re-map a single MIDI pitch from source scale to destination scale."""
    rel = (pitch - src_root) % 12
    octave_offset = (pitch - src_root) // 12

    if rel in src_intervals:
        degree_idx = src_intervals.index(rel)
        new_rel = dst_intervals[degree_idx]
    else:
        root_delta = dst_root - src_root
        return max(MIDI_NOTE_MIN, min(MIDI_NOTE_MAX, pitch + root_delta))

    new_pitch = dst_root + octave_offset * 12 + new_rel
    return max(MIDI_NOTE_MIN, min(MIDI_NOTE_MAX, new_pitch))


def run_progression_change(tool_call: ToolCall, midi_path: str) -> str:
    """Change the key/scale of a MIDI file.

    Reads tool_call.params for:
        progression (str): Target scale name, e.g. "A minor", "D major".
        target_description (str, optional): Which track to change.

    Auto-detects the current key using music21, then remaps notes to the
    target scale. Modifies the MIDI file in-place (atomic write).
    """
    tag = "[progression_change]"

    if not os.path.isfile(midi_path):
        raise FileNotFoundError(f"No MIDI found at {midi_path}")

    target_scale = tool_call.params.get("progression", "")
    target = tool_call.params.get("target_description", "")

    if not target_scale:
        raise ValueError("No target scale/key provided in 'progression' param.")

    # Parse target scale
    dst_root, dst_mode = _parse_scale_name(str(target_scale))
    dst_intervals = _SCALE_INTERVALS[dst_mode]
    dst_name = str(target_scale).strip()

    # Detect current key
    src_root, src_mode, src_name = _detect_key(midi_path)
    src_intervals = _SCALE_INTERVALS[src_mode]

    if src_root == dst_root and src_mode == dst_mode:
        return f"Already in {src_name}, no changes needed."

    # Load MIDI
    midi = pretty_midi.PrettyMIDI(midi_path)

    matched = _find_tracks(midi, target)
    if not matched:
        available = [inst.name for inst in midi.instruments if inst.name]
        raise ValueError(f"No tracks matching {target!r}. Available: {available}")

    same_mode = src_mode == dst_mode
    root_delta = dst_root - src_root

    total_changed = 0
    total_clamped = 0

    for inst in matched:
        if inst.is_drum:
            continue

        for note in inst.notes:
            if same_mode:
                new_pitch = note.pitch + root_delta
            else:
                new_pitch = _remap_note(
                    note.pitch, src_root, src_intervals, dst_root, dst_intervals
                )

            if new_pitch < MIDI_NOTE_MIN or new_pitch > MIDI_NOTE_MAX:
                new_pitch = max(MIDI_NOTE_MIN, min(MIDI_NOTE_MAX, new_pitch))
                total_clamped += 1

            note.pitch = new_pitch
            total_changed += 1

    # Atomic write
    dir_name = os.path.dirname(midi_path)
    fd, tmp_path = tempfile.mkstemp(suffix=".mid", dir=dir_name)
    os.close(fd)
    try:
        midi.write(tmp_path)
        os.replace(tmp_path, midi_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    summary = (
        f"Changed from {src_name} to {dst_name}"
        f" ({total_changed} notes on {len(matched)} track(s))."
    )
    if total_clamped:
        summary += f" ({total_clamped} notes clamped to MIDI range 0-127.)"

    print(f"{tag} {summary}")
    return summary
