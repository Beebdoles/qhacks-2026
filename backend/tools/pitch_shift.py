# pitch_shift — Transpose a track up or down by N semitones.
import os
import tempfile
import pretty_midi

from intent.schema import ToolCall

MIDI_NOTE_MIN = 0
MIDI_NOTE_MAX = 127


def _find_tracks(midi: pretty_midi.PrettyMIDI, description: str) -> list[pretty_midi.Instrument]:
    """Fuzzy-match a target_description against instrument/track names.

    If no name-based match is found, falls back to all non-drum instruments
    (the file-level resolution in dispatch.py already picked the right MIDI).
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

    # Fall back to all non-drum tracks — dispatch already resolved the file
    return matched if matched else non_drum


def run_pitch_shift(tool_call: ToolCall, midi_path: str) -> str:
    """Apply pitch shift from a ToolCall to the MIDI file at midi_path.

    Reads tool_call.params for:
        semitones (int): Number of semitones to shift (positive=up, negative=down).
        target_description (str, optional): Which track to shift.

    Modifies the MIDI file in-place (atomic write) and returns a summary string.
    """
    tag = "[pitch_shift]"

    if not os.path.isfile(midi_path):
        raise FileNotFoundError(f"No MIDI found at {midi_path}")

    semitones = tool_call.params.get("semitones", 0)
    target = tool_call.params.get("target_description", "")

    if semitones == 0:
        return "No pitch change requested (semitones=0)."

    midi = pretty_midi.PrettyMIDI(midi_path)

    matched = _find_tracks(midi, target)
    if not matched:
        available = [inst.name for inst in midi.instruments if inst.name]
        raise ValueError(
            f"No tracks matching {target!r}. Available: {available}"
        )

    total_shifted = 0
    total_clamped = 0

    for inst in matched:
        for note in inst.notes:
            new_pitch = note.pitch + semitones

            if new_pitch < MIDI_NOTE_MIN:
                new_pitch = MIDI_NOTE_MIN
                total_clamped += 1
            elif new_pitch > MIDI_NOTE_MAX:
                new_pitch = MIDI_NOTE_MAX
                total_clamped += 1

            note.pitch = new_pitch
            total_shifted += 1

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

    direction = "up" if semitones > 0 else "down"
    summary = (
        f"Shifted {total_shifted} notes {direction} by {abs(semitones)} semitones"
        f" on {len(matched)} track(s)."
    )
    if total_clamped:
        summary += f" ({total_clamped} notes clamped to MIDI range 0-127.)"

    print(f"{tag} {summary}")
    return summary
