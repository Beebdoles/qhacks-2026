import math

import numpy as np

from .config import MIN_ONSETS_FOR_TEMPO


def hz_to_midi(hz: float) -> float:
    if hz <= 0:
        return 0.0
    return 69 + 12 * math.log2(hz / 440)


def midi_to_hz(midi: float) -> float:
    return 440 * (2 ** ((midi - 69) / 12))


def hz_to_cents(hz1: float, hz2: float) -> float:
    if hz1 <= 0 or hz2 <= 0:
        return 0.0
    return 1200 * math.log2(hz1 / hz2)


def get_scale_degrees(root: int, mode: str) -> list[int]:
    major = [0, 2, 4, 5, 7, 9, 11]
    minor = [0, 2, 3, 5, 7, 8, 10]
    intervals = major if mode == "major" else minor
    return [(root + i) % 12 for i in intervals]


def snap_to_scale(midi_note: int, scale_degrees: list[int]) -> int:
    pc = midi_note % 12
    octave = midi_note - pc
    best = min(scale_degrees, key=lambda d: min(abs(pc - d), 12 - abs(pc - d)))
    # Handle wrap-around: if snapping down wraps below, adjust octave
    diff = best - pc
    if diff > 6:
        diff -= 12
    elif diff < -6:
        diff += 12
    return midi_note + diff


def get_device() -> str:
    try:
        import torch
        if torch.backends.mps.is_available():
            # Smoke test MPS
            t = torch.zeros(1, device="mps")
            _ = t + 1
            return "mps"
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def detect_tempo_from_onsets(onset_times: np.ndarray) -> tuple[float, bool]:
    if len(onset_times) < MIN_ONSETS_FOR_TEMPO:
        return (120.0, False)

    iois = np.diff(onset_times)
    iois = iois[iois > 0.1]  # filter out very short intervals (< 100ms)

    if len(iois) < 2:
        return (120.0, False)

    median_ioi = np.median(iois)
    tempo = 60.0 / median_ioi

    # Clamp to reasonable range
    while tempo < 60:
        tempo *= 2
    while tempo > 200:
        tempo /= 2

    return (tempo, True)
