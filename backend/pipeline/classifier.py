import csv
import io

import numpy as np
import soundfile as sf
import tensorflow as tf
import tensorflow_hub as hub

from models import Segment

_model = None
_class_names = None


def _load_model():
    global _model, _class_names
    if _model is None:
        _model = hub.load("https://tfhub.dev/google/yamnet/1")
        # Load class names from the model's asset
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


def _classify_label(label: str) -> str:
    lower = label.lower()
    for kw in _HUMMING_KEYWORDS:
        if kw in lower:
            return "humming"
    for kw in _DRUM_KEYWORDS:
        if kw in lower:
            return "beatboxing"
    return "silence"


def classify_segments(
    wav_path: str, non_speech_segments: list[Segment]
) -> list[Segment]:
    """Classify non-speech segments as humming, beatboxing, or silence using YAMNet."""
    if not non_speech_segments:
        return []

    model, class_names = _load_model()
    audio_data, sr = sf.read(wav_path, dtype="float32")

    # Ensure mono
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    # YAMNet expects 16kHz
    if sr != 16000:
        import librosa
        audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
        sr = 16000

    classified = []
    for seg in non_speech_segments:
        start_sample = int(seg.start * sr)
        end_sample = int(seg.end * sr)
        chunk = audio_data[start_sample:end_sample]

        if len(chunk) < 1600:  # Less than 0.1s at 16kHz
            classified.append(Segment(start=seg.start, end=seg.end, type="silence"))
            continue

        scores, embeddings, spectrogram = model(chunk)
        mean_scores = tf.reduce_mean(scores, axis=0).numpy()
        top_idx = np.argmax(mean_scores)
        top_label = class_names[top_idx]
        seg_type = _classify_label(top_label)

        classified.append(Segment(start=seg.start, end=seg.end, type=seg_type))

    return classified
