import csv

import numpy as np
import soundfile as sf
import tensorflow as tf
import tensorflow_hub as hub

from models import Segment

_model = None
_class_names = None
_class_to_category = None

YAMNET_HOP = 0.48  # seconds between YAMNet windows
MIN_SUB_DURATION = 0.3  # minimum sub-segment length before merging


def _load_model():
    global _model, _class_names
    if _model is None:
        _model = hub.load("https://tfhub.dev/google/yamnet/1")
        class_map_path = _model.class_map_path().numpy().decode("utf-8")
        with tf.io.gfile.GFile(class_map_path) as f:
            reader = csv.DictReader(f)
            _class_names = [row["display_name"] for row in reader]
    return _model, _class_names


# Keywords for classifying YAMNet output
_HUMMING_KEYWORDS = {
    "singing",
    "humming",
    "vocal",
    "choir",
    "yodeling",
    "whistling",
    "melody",
}
_DRUM_KEYWORDS = {
    "drum",
    "percussion",
    "knock",
    "tap",
    "bang",
    "snare",
    "bass drum",
    "hi-hat",
    "cymbal",
    "beatbox",
    "beatboxing",
}
_SPEECH_KEYWORDS = {
    "speech",
    "narration",
    "conversation",
    "talk",
    "monologue",
}


def _build_class_map(class_names):
    """Build a one-time mapping from YAMNet class index → category."""
    global _class_to_category
    if _class_to_category is not None:
        return _class_to_category

    _class_to_category = {}
    for idx, name in enumerate(class_names):
        lower = name.lower()
        for kw in _SPEECH_KEYWORDS:
            if kw in lower:
                _class_to_category[idx] = "speech"
                break
        else:
            for kw in _HUMMING_KEYWORDS:
                if kw in lower:
                    _class_to_category[idx] = "humming"
                    break
            else:
                for kw in _DRUM_KEYWORDS:
                    if kw in lower:
                        _class_to_category[idx] = "beatboxing"
                        break
    return _class_to_category


def _window_category(window_scores, class_names):
    """Classify a single YAMNet window by summing scores per category.

    Instead of taking the single top-scoring class, this sums up the scores
    of ALL classes matching each category. This prevents speech from winning
    just because it has one high-scoring class when multiple humming-related
    classes collectively score higher.
    """
    cat_map = _build_class_map(class_names)
    totals = {"speech": 0.0, "humming": 0.0, "beatboxing": 0.0}
    for idx, cat in cat_map.items():
        totals[cat] += float(window_scores[idx])
    best = max(totals, key=totals.get)
    if totals[best] < 0.05:
        return "silence"
    return best


def classify_segments(
    wav_path: str, segments: list[Segment]
) -> list[Segment]:
    """Classify segments using per-window YAMNet analysis with sub-segment splitting.

    Runs YAMNet once on the full audio, then slices window scores per segment.
    """
    if not segments:
        return []

    model, class_names = _load_model()
    audio_data, sr = sf.read(wav_path, dtype="float32")

    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    if sr != 16000:
        import librosa
        audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
        sr = 16000

    # Run YAMNet ONCE on the full audio
    scores, _, _ = model(audio_data)
    all_scores = scores.numpy()
    total_windows = all_scores.shape[0]

    result = []
    for seg in segments:
        if seg.end - seg.start < 0.1:
            result.append(Segment(start=seg.start, end=seg.end, type="silence"))
            continue

        # Map segment time range to YAMNet window indices
        win_start = int(seg.start / YAMNET_HOP)
        win_end = int(np.ceil(seg.end / YAMNET_HOP))
        win_start = max(0, min(win_start, total_windows))
        win_end = max(win_start, min(win_end, total_windows))

        scores_np = all_scores[win_start:win_end]
        n_windows = scores_np.shape[0]

        if n_windows == 0:
            result.append(Segment(start=seg.start, end=seg.end, type="silence"))
            continue

        # Classify each window independently
        win_types = [_window_category(scores_np[i], class_names) for i in range(n_windows)]

        # Group consecutive same-type windows
        groups = []
        cur_type = win_types[0]
        cur_start = 0
        for i in range(1, n_windows):
            if win_types[i] != cur_type:
                groups.append((cur_start, i, cur_type))
                cur_type = win_types[i]
                cur_start = i
        groups.append((cur_start, n_windows, cur_type))

        # Convert window indices to timestamps (relative to full audio)
        subs = []
        for gi, (ws, we, gt) in enumerate(groups):
            t_start = (win_start + ws) * YAMNET_HOP if gi > 0 else seg.start
            t_end = (win_start + we) * YAMNET_HOP if gi < len(groups) - 1 else seg.end
            subs.append({"start": t_start, "end": t_end, "type": gt})

        # Absorb short sub-segments into their neighbors
        merged = []
        for s in subs:
            if s["end"] - s["start"] < MIN_SUB_DURATION and merged:
                merged[-1]["end"] = s["end"]
            else:
                merged.append(s)
        if len(merged) > 1 and merged[-1]["end"] - merged[-1]["start"] < MIN_SUB_DURATION:
            merged[-2]["end"] = merged[-1]["end"]
            merged.pop()

        for s in merged:
            print(f"[classifier] {s['start']:.2f}-{s['end']:.2f}s → {s['type']}")
            result.append(Segment(start=s["start"], end=s["end"], type=s["type"]))

    # Final pass: merge adjacent same-type segments
    if not result:
        return result
    final = [result[0]]
    for seg in result[1:]:
        if seg.type == final[-1].type and seg.start - final[-1].end < 0.1:
            final[-1] = Segment(start=final[-1].start, end=seg.end, type=seg.type)
        else:
            final.append(seg)

    return final
