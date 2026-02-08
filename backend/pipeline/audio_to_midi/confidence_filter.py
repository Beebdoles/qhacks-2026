import numpy as np
from scipy.signal import medfilt

from .config import CONFIDENCE_THRESHOLD, MEDIAN_FILTER_SIZE, MIN_VOICED_DURATION


def filter_pitch(
    times: np.ndarray, frequencies: np.ndarray, confidences: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Filter pitch estimates by confidence, apply per-span median filter,
    and remove short voiced regions.

    Returns (times, filtered_freqs, confidences).
    """
    filtered = frequencies.copy()

    # Mask low-confidence frames
    low_conf = confidences < CONFIDENCE_THRESHOLD
    filtered[low_conf] = 0.0

    # Median filter per voiced span (Revision #2)
    voiced_mask = filtered > 0
    spans = _find_spans(voiced_mask)

    for start, end in spans:
        span_len = end - start
        # Skip spans shorter than kernel size (Revision #20)
        if span_len < MEDIAN_FILTER_SIZE:
            continue
        kernel = MEDIAN_FILTER_SIZE
        if kernel % 2 == 0:
            kernel += 1
        if span_len >= kernel:
            filtered[start:end] = medfilt(filtered[start:end], kernel_size=kernel)

    # Remove short voiced regions
    hop_time = times[1] - times[0] if len(times) > 1 else 0.01
    voiced_mask = filtered > 0
    spans = _find_spans(voiced_mask)

    for start, end in spans:
        duration = (end - start) * hop_time
        if duration < MIN_VOICED_DURATION:
            filtered[start:end] = 0.0

    return times, filtered, confidences


def _find_spans(mask: np.ndarray) -> list[tuple[int, int]]:
    """Find contiguous True runs in a boolean array. Returns [(start, end), ...]."""
    spans = []
    in_span = False
    start = 0
    for i, v in enumerate(mask):
        if v and not in_span:
            start = i
            in_span = True
        elif not v and in_span:
            spans.append((start, i))
            in_span = False
    if in_span:
        spans.append((start, len(mask)))
    return spans
