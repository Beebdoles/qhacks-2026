# repeat_track — Repeat/loop a track N times.
import os
import tempfile
import pretty_midi

from intent.schema import ToolCall


def run_repeat_track(tool_call: ToolCall, midi_path: str) -> str:
    """Concatenate additional copies of a MIDI file's content.

    Reads tool_call.params for:
        times (int): Number of additional copies to append. times=3 means
                     3 copies are added after the original (4 total). Default 1.

    Modifies the MIDI file in-place (atomic write) and returns a summary string.
    """
    tag = "[repeat_track]"

    if not os.path.isfile(midi_path):
        raise FileNotFoundError(f"No MIDI found at {midi_path}")

    times = int(tool_call.params.get("times", 1))

    if times < 1:
        raise ValueError(f"times must be >= 1, got {times}")

    midi = pretty_midi.PrettyMIDI(midi_path)

    original_duration = midi.get_end_time()
    if original_duration <= 0:
        return "MIDI file is empty, nothing to repeat."

    for inst in midi.instruments:
        original_notes = list(inst.notes)
        for copy_idx in range(1, times + 1):
            offset = copy_idx * original_duration
            for note in original_notes:
                inst.notes.append(pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.start + offset,
                    end=note.end + offset,
                ))

        original_ccs = list(inst.control_changes)
        for copy_idx in range(1, times + 1):
            offset = copy_idx * original_duration
            for cc in original_ccs:
                inst.control_changes.append(pretty_midi.ControlChange(
                    number=cc.number,
                    value=cc.value,
                    time=cc.time + offset,
                ))

        original_bends = list(inst.pitch_bends)
        for copy_idx in range(1, times + 1):
            offset = copy_idx * original_duration
            for pb in original_bends:
                inst.pitch_bends.append(pretty_midi.PitchBend(
                    pitch=pb.pitch,
                    time=pb.time + offset,
                ))

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

    total = times + 1
    summary = (
        f"Appended {times} additional copy/copies to {os.path.basename(midi_path)} "
        f"({total} total, {original_duration:.1f}s → {original_duration * total:.1f}s)."
    )
    print(f"{tag} {summary}")
    return summary
