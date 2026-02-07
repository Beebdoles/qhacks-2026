import torch
import torchaudio

from models import Segment

_model = None
_utils = None


def _load_model():
    global _model, _utils
    if _model is None:
        _model, _utils = torch.hub.load(
            "snakers4/silero-vad", "silero_vad", trust_repo=True
        )
    return _model, _utils


def detect_speech_segments(wav_16k_path: str) -> list[Segment]:
    """Run Silero VAD to find speech segments."""
    model, utils = _load_model()
    get_speech_timestamps = utils[0]

    waveform, sr = torchaudio.load(wav_16k_path)
    # Silero expects mono 16kHz
    waveform = waveform.squeeze(0)

    speech_timestamps = get_speech_timestamps(
        waveform, model, sampling_rate=16000, threshold=0.5
    )

    segments = []
    for ts in speech_timestamps:
        segments.append(
            Segment(
                start=ts["start"] / 16000.0,
                end=ts["end"] / 16000.0,
                type="speech",
            )
        )

    return segments
