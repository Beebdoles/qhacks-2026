from dataclasses import dataclass

import numpy as np

from .config import (
    PITCH_CHANGE_THRESHOLD,
    MIN_NOTE_DURATION,
    CONFIDENCE_DIP_THRESHOLD,
)
from .utils import hz_to_cents


@dataclass
class RawNote:
    pitch_hz: float
    start: float
    end: float
    avg_confidence: float


def segment_notes(
    times: np.ndarray,
    frequencies: np.ndarray,
    confidences: np.ndarray,
    onset_times: np.ndarray,
) -> list[RawNote]:
    """Segment filtered pitch contour into discrete notes.

    Returns list of RawNote with median Hz, start/end times, and mean confidence.
    """
    voiced_mask = frequencies > 0
    spans = _find_spans(voiced_mask)
    notes: list[RawNote] = []

    for span_start, span_end in spans:
        span_times = times[span_start:span_end]
        span_freqs = frequencies[span_start:span_end]
        span_confs = confidences[span_start:span_end]

        # Find boundary indices within this span
        boundaries = [0]

        for i in range(1, len(span_freqs)):
            # Pitch change boundary
            cents = abs(hz_to_cents(span_freqs[i], span_freqs[i - 1]))
            if cents > PITCH_CHANGE_THRESHOLD:
                boundaries.append(i)
                continue

            # Confidence dip boundary
            if span_confs[i] < CONFIDENCE_DIP_THRESHOLD:
                boundaries.append(i)
                continue

            # Onset alignment boundary
            t = span_times[i]
            for onset_t in onset_times:
                if abs(t - onset_t) < (times[1] - times[0]) * 0.5:
                    boundaries.append(i)
                    break

        boundaries.append(len(span_freqs))
        boundaries = sorted(set(boundaries))

        # Create notes from sub-segments
        for j in range(len(boundaries) - 1):
            seg_start = boundaries[j]
            seg_end = boundaries[j + 1]

            seg_freqs = span_freqs[seg_start:seg_end]
            seg_confs = span_confs[seg_start:seg_end]
            seg_times = span_times[seg_start:seg_end]

            if len(seg_freqs) == 0:
                continue

            start_time = seg_times[0]
            end_time = seg_times[-1]
            duration = end_time - start_time

            if duration < MIN_NOTE_DURATION:
                continue

            median_hz = float(np.median(seg_freqs))
            mean_conf = float(np.mean(seg_confs))

            notes.append(RawNote(
                pitch_hz=median_hz,
                start=start_time,
                end=end_time,
                avg_confidence=mean_conf,
            ))

    return notes


def _find_spans(mask: np.ndarray) -> list[tuple[int, int]]:
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
