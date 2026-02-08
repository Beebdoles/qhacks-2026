import os
import tempfile

import music21
import pretty_midi

# Resolve project root from this file's location (backend/toolcalls/change_scale.py)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LATEST_MIDI = os.path.join(_PROJECT_ROOT, "latest-job", "output.mid")

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
    """Parse a scale name like 'A minor' or 'F# major' into (root_pc, mode).

    Returns:
        (root_pitch_class, mode) where root_pitch_class is 0-11 semitones from C.
    """
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
    """Detect the key of a MIDI file using music21's Krumhansl-Schmuckler algorithm.

    Returns:
        (root_pitch_class, mode, key_name) e.g. (0, "major", "C major")
    """
    score = music21.converter.parse(midi_path)
    key = score.analyze("key")

    root_name = key.tonic.name  # e.g. "C", "F#"
    mode = key.mode             # "major" or "minor"

    pc = _PITCH_CLASS.get(root_name)
    if pc is None:
        raise RuntimeError(f"music21 returned unexpected tonic: {root_name!r}")

    return pc, mode, f"{root_name} {mode}"


def _remap_note(
    pitch: int,
    src_root: int,
    src_intervals: list[int],
    dst_root: int,
    dst_intervals: list[int],
) -> int:
    """Re-map a single MIDI pitch from source scale to destination scale.

    Notes on a scale degree get mapped to the corresponding degree in the
    target scale. Chromatic / passing tones just get the root transposition.
    """
    # Position relative to source root (0-11)
    rel = (pitch - src_root) % 12
    octave_offset = (pitch - src_root) // 12

    if rel in src_intervals:
        # On a scale degree — map to corresponding degree in target
        degree_idx = src_intervals.index(rel)
        new_rel = dst_intervals[degree_idx]
    else:
        # Chromatic tone — just transpose by root difference
        root_delta = dst_root - src_root
        return max(MIDI_NOTE_MIN, min(MIDI_NOTE_MAX, pitch + root_delta))

    new_pitch = dst_root + octave_offset * 12 + new_rel
    return max(MIDI_NOTE_MIN, min(MIDI_NOTE_MAX, new_pitch))


def change_scale(layer: str, target_scale: str) -> str:
    """Change the key/scale of the latest job's MIDI file.

    Auto-detects the current key using music21, then transposes and
    re-maps notes to the target scale.

    Args:
        target_scale: Target scale name, e.g. "A minor", "D major", "F# minor".

    Returns:
        Summary string describing the transformation.
    """
    if not os.path.isfile(_LATEST_MIDI):
        raise FileNotFoundError(f"No MIDI found at {_LATEST_MIDI}")

    # Parse target
    dst_root, dst_mode = _parse_scale_name(target_scale)
    dst_intervals = _SCALE_INTERVALS[dst_mode]

    # Detect current key
    try:
        src_root, src_mode, src_name = _detect_key(_LATEST_MIDI)
    except Exception as exc:
        print(f"[change_scale] Key detection failed ({exc}), assuming C major")
        src_root, src_mode, src_name = 0, "major", "C major"
    src_intervals = _SCALE_INTERVALS[src_mode]

    dst_name = target_scale.strip()

    if src_root == dst_root and src_mode == dst_mode:
        return f"Already in {src_name}, no changes needed."

    # Load with pretty_midi for note manipulation
    try:
        midi = pretty_midi.PrettyMIDI(_LATEST_MIDI)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse MIDI file: {exc}") from exc

    same_mode = src_mode == dst_mode
    root_delta = dst_root - src_root

    total_changed = 0
    total_clamped = 0

    # Find matching instrument/track by name, defaulting unknown names to singing
    matched = []
    layer_lower = layer.strip().lower()
    for inst in midi.instruments:
        if inst.name and inst.name.strip().lower() == layer_lower:
            matched.append(inst)

    if not matched:
        # Fallback: try to match "singing" tracks instead
        for inst in midi.instruments:
            if inst.name and inst.name.strip().lower() == "singing":
                matched.append(inst)
        if matched:
            print(f"[change_scale] Layer {layer!r} not found, defaulting to 'singing'")

    if not matched:
        # Last resort: pick the first non-drum instrument
        for inst in midi.instruments:
            if not inst.is_drum:
                matched.append(inst)
                break
        if matched:
            print(f"[change_scale] No named layers found, defaulting to first non-drum instrument ({matched[0].name!r})")

    if not matched:
        available = [inst.name for inst in midi.instruments if inst.name]
        raise ValueError(
            f"Layer {layer!r} not found and no fallback available. Available layers: {available}"
        )

    for inst in matched:
        if inst.is_drum:
            continue

        for note in inst.notes:
            if same_mode:
                # Same mode — simple transposition
                new_pitch = note.pitch + root_delta
            else:
                # Different mode — re-map scale degrees
                new_pitch = _remap_note(
                    note.pitch, src_root, src_intervals, dst_root, dst_intervals
                )

            if new_pitch < MIDI_NOTE_MIN or new_pitch > MIDI_NOTE_MAX:
                new_pitch = max(MIDI_NOTE_MIN, min(MIDI_NOTE_MAX, new_pitch))
                total_clamped += 1

            note.pitch = new_pitch
            total_changed += 1

    # Atomic write
    dir_name = os.path.dirname(_LATEST_MIDI)
    fd, tmp_path = tempfile.mkstemp(suffix=".mid", dir=dir_name)
    os.close(fd)
    try:
        midi.write(tmp_path)
        os.replace(tmp_path, _LATEST_MIDI)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    summary = f"Changed from {src_name} to {dst_name} ({total_changed} notes modified)."
    if total_clamped:
        summary += f" ({total_clamped} notes clamped to MIDI range 0-127.)"

    print(f"[change_scale] {summary}")
    return summary
