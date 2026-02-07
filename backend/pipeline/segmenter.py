import os
import torch
import torchaudio
from pyannote.audio import Model
from pyannote.audio.pipelines import VoiceActivityDetection
from models import Segment

_pipeline = None


def _load_pipeline():
    global _pipeline
    if _pipeline is None:
        token = os.environ.get("HF_TOKEN")
        model = Model.from_pretrained(
            "pyannote/segmentation-3.0",
            token=token,
        )
        _pipeline = VoiceActivityDetection(segmentation=model)
        _pipeline.instantiate({
            "min_duration_on": 0.05,
            "min_duration_off": 0.1,
        })
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _pipeline = _pipeline.to(device)
    return _pipeline


def detect_speech_segments(wav_16k_path: str) -> list[Segment]:
    """Run pyannote VAD to find speech segments."""
    pipeline = _load_pipeline()
    waveform, sr = torchaudio.load(wav_16k_path)
    output = pipeline({"waveform": waveform, "sample_rate": sr})
    segments = []
    for speech in output.get_timeline().support():
        segments.append(
            Segment(start=speech.start, end=speech.end, type="speech")
        )
    return segments
