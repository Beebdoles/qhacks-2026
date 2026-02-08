import librosa
import numpy as np

from .config import SAMPLE_RATE, NOISE_GATE_DB


def preprocess_audio(audio_path: str) -> tuple[np.ndarray, np.ndarray, int]:
    """Load and preprocess audio for pitch detection.

    Returns (harmonic, original, sr).
    """
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)

    # Peak normalize to [-1.0, 1.0]
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y / peak

    original = y.copy()

    # HPSS — keep harmonic
    harmonic, _ = librosa.effects.hpss(y)

    # Noise gate: zero frames below threshold
    frame_length = 2048
    hop_length = 512
    rms = librosa.feature.rms(y=harmonic, frame_length=frame_length, hop_length=hop_length)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=1.0)

    for i, db in enumerate(rms_db):
        if db < NOISE_GATE_DB:
            start = i * hop_length
            end = min(start + frame_length, len(harmonic))
            harmonic[start:end] = 0.0

    return harmonic, original, sr
