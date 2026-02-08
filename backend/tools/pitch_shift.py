# pitch_shift — Transpose a track up or down by N semitones.
import os
import tempfile
import pretty_midi

# Resolve project root from this file's location (backend/toolcalls/change_pitch.py)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LATEST_MIDI = os.path.join(_PROJECT_ROOT, "latest-job", "output.mid")

MIDI_NOTE_MIN = 0
MIDI_NOTE_MAX = 127


def change_pitch(layer: str, pitch: int, shift_type: str) -> str:
    """Shift the pitch of all notes on a given layer in the latest job's MIDI.

    Args:
        layer: Track/layer name to modify (e.g. "singing", "humming", "beatboxing").
        pitch: Amount to shift (positive = up, negative = down).
        shift_type: "octave" (shift by octaves, 12 semitones each) or "semitone".

    Returns:
        Summary string describing what was changed.
    """
    if not os.path.isfile(_LATEST_MIDI):
        raise FileNotFoundError(f"No MIDI found at {_LATEST_MIDI}")

    # Determine semitone delta
    shift_type_lower = shift_type.strip().lower()
    if shift_type_lower == "octave" or shift_type_lower == "octaves":
        delta = pitch * 12
    elif shift_type_lower in ("semitone", "semitones"):
        delta = pitch
    else:
        raise ValueError(f"Unknown shift type: {shift_type!r}. Use 'octave' or 'semitone'.")

    if delta == 0:
        return "No pitch change requested (delta=0)."

    midi = pretty_midi.PrettyMIDI(_LATEST_MIDI)

    # Find matching instrument/track by name
    matched = []
    layer_lower = layer.strip().lower()
    for inst in midi.instruments:
        if inst.name and inst.name.strip().lower() == layer_lower:
            matched.append(inst)

    if not matched:
        available = [inst.name for inst in midi.instruments if inst.name]
        raise ValueError(
            f"Layer {layer!r} not found. Available layers: {available}"
        )

    total_shifted = 0
    total_clamped = 0

    for inst in matched:
        for note in inst.notes:
            new_pitch = note.pitch + delta

            # Clamp to valid MIDI range
            if new_pitch < MIDI_NOTE_MIN:
                new_pitch = MIDI_NOTE_MIN
                total_clamped += 1
            elif new_pitch > MIDI_NOTE_MAX:
                new_pitch = MIDI_NOTE_MAX
                total_clamped += 1

            note.pitch = new_pitch
            total_shifted += 1

    # Write to temp file first, then atomically replace to avoid
    # corrupting the file if the frontend reads it mid-write
    dir_name = os.path.dirname(_LATEST_MIDI)
    fd, tmp_path = tempfile.mkstemp(suffix=".mid", dir=dir_name)
    os.close(fd)
    try:
        midi.write(tmp_path)
        os.replace(tmp_path, _LATEST_MIDI)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    direction = "up" if delta > 0 else "down"
    summary = (
        f"Shifted {total_shifted} notes {direction} by {abs(delta)} semitones "
        f"on layer {layer!r}."
    )
    if total_clamped:
        summary += f" ({total_clamped} notes clamped to MIDI range 0-127.)"

    print(f"[change_pitch] {summary}")
    return summary
