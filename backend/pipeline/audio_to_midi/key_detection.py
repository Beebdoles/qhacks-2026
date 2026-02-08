from dataclasses import dataclass

import librosa
import numpy as np

from .utils import hz_to_midi, get_scale_degrees, snap_to_scale


@dataclass
class MidiNote:
    pitch: int
    start: float
    end: float
    velocity: int


# Krumhansl-Schmuckler key profiles
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def detect_key(
    original: np.ndarray, sr: int, notes: list
) -> tuple[int, str]:
    """Detect musical key using Krumhansl-Schmuckler algorithm on chroma features.

    Returns (root_pitch_class, mode) e.g. (0, 'major') for C major.
    """
    chroma = librosa.feature.chroma_cqt(y=original, sr=sr)
    chroma_totals = np.sum(chroma, axis=1)  # shape: (12,)

    best_corr = -np.inf
    best_root = 0
    best_mode = "major"

    for root in range(12):
        rotated = np.roll(chroma_totals, -root)

        corr_major = np.corrcoef(rotated, _MAJOR_PROFILE)[0, 1]
        corr_minor = np.corrcoef(rotated, _MINOR_PROFILE)[0, 1]

        if corr_major > best_corr:
            best_corr = corr_major
            best_root = root
            best_mode = "major"
        if corr_minor > best_corr:
            best_corr = corr_minor
            best_root = root
            best_mode = "minor"

    return best_root, best_mode


def snap_notes_to_key(notes: list, root: int, mode: str) -> list[MidiNote]:
    """Convert RawNotes to MidiNotes, snapping pitches to detected key.

    Derives velocity from avg_confidence (Revision #8).
    """
    scale = get_scale_degrees(root, mode)
    midi_notes: list[MidiNote] = []

    for note in notes:
        raw_midi = hz_to_midi(note.pitch_hz)
        rounded = round(raw_midi)
        snapped = snap_to_scale(rounded, scale)

        velocity = int(min(127, max(40, note.avg_confidence * 127)))

        midi_notes.append(MidiNote(
            pitch=snapped,
            start=note.start,
            end=note.end,
            velocity=velocity,
        ))

    return midi_notes
