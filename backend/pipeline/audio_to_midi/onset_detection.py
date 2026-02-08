import librosa
import numpy as np

from .config import HOP, ONSET_DELTA


def detect_onsets(original: np.ndarray, sr: int) -> np.ndarray:
    """Detect note onsets tuned for singing/humming.

    Returns array of onset times in seconds.
    """
    onset_envelope = librosa.onset.onset_strength(
        y=original, sr=sr, hop_length=HOP
    )

    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_envelope,
        sr=sr,
        hop_length=HOP,
        units="time",
        backtrack=True,
        delta=ONSET_DELTA,
    )

    return onset_frames
