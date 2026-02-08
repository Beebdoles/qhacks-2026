import numpy as np
import librosa
import pretty_midi

from .config import GRID_SUBDIVISIONS, QUANTIZE_SNAP_TOLERANCE
from .key_detection import MidiNote
from .utils import detect_tempo_from_onsets
from .onset_detection import detect_onsets


def detect_tempo(original: np.ndarray, sr: int) -> tuple[float, bool]:
    """Detect tempo using librosa beat tracking, with onset-based fallback.

    Returns (tempo_bpm, reliable).
    """
    try:
        tempo_result = librosa.beat.beat_track(y=original, sr=sr)
        # Handle both old (tuple) and new (BeatTrackResults) return types
        if hasattr(tempo_result, 'bpm'):
            tempo = float(tempo_result.bpm)
        elif isinstance(tempo_result, tuple):
            t = tempo_result[0]
            tempo = float(t[0]) if isinstance(t, np.ndarray) else float(t)
        else:
            tempo = float(tempo_result)

        if 60 <= tempo <= 200:
            return (tempo, True)
    except Exception:
        pass

    # Fallback: onset-based tempo detection (Revision #5, #16)
    try:
        onset_times = detect_onsets(original, sr)
        return detect_tempo_from_onsets(onset_times)
    except Exception:
        pass

    return (120.0, False)


def quantize_notes(
    notes: list[MidiNote], tempo: float, reliable: bool
) -> list[MidiNote]:
    """Quantize notes to grid if tempo is reliable.

    Returns (possibly quantized) list of MidiNote.
    """
    if not reliable:
        return notes

    beat_dur = 60.0 / tempo
    grid_dur = beat_dur / GRID_SUBDIVISIONS
    quantized: list[MidiNote] = []

    for note in notes:
        # Snap start
        grid_idx = round(note.start / grid_dur)
        snapped_start = grid_idx * grid_dur
        start_offset = abs(note.start - snapped_start)

        if start_offset / grid_dur <= QUANTIZE_SNAP_TOLERANCE:
            new_start = snapped_start
        else:
            new_start = note.start

        # Snap end
        grid_idx_end = round(note.end / grid_dur)
        snapped_end = grid_idx_end * grid_dur
        end_offset = abs(note.end - snapped_end)

        if end_offset / grid_dur <= QUANTIZE_SNAP_TOLERANCE:
            new_end = snapped_end
        else:
            new_end = note.end

        # Ensure minimum duration
        if new_end <= new_start:
            new_end = new_start + grid_dur

        quantized.append(MidiNote(
            pitch=note.pitch,
            start=new_start,
            end=new_end,
            velocity=note.velocity,
        ))

    # Post-quantization overlap detection (Revision #12)
    quantized.sort(key=lambda n: (n.pitch, n.start))
    merged: list[MidiNote] = []

    for note in quantized:
        if merged and merged[-1].pitch == note.pitch and note.start < merged[-1].end:
            # Merge: extend the previous note
            merged[-1] = MidiNote(
                pitch=merged[-1].pitch,
                start=merged[-1].start,
                end=max(merged[-1].end, note.end),
                velocity=max(merged[-1].velocity, note.velocity),
            )
        else:
            merged.append(note)

    return merged


def build_melody_midi(
    notes: list[MidiNote], tempo: float, instrument_name: str
) -> pretty_midi.PrettyMIDI:
    """Build a PrettyMIDI object from quantized notes."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    program = pretty_midi.instrument_name_to_program(instrument_name)
    instrument = pretty_midi.Instrument(program=program, name=instrument_name)

    for note in notes:
        midi_note = pretty_midi.Note(
            velocity=note.velocity,
            pitch=note.pitch,
            start=note.start,
            end=note.end,
        )
        instrument.notes.append(midi_note)

    midi.instruments.append(instrument)
    return midi
