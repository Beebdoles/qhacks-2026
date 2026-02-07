import numpy as np
import soundfile as sf
import whisper

from models import Segment, Transcription

_model = None


def _load_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def transcribe_speech(
    wav_path: str, speech_segments: list[Segment]
) -> list[Transcription]:
    """Transcribe speech segments using Whisper."""
    if not speech_segments:
        return []

    model = _load_model()
    audio_data, sr = sf.read(wav_path, dtype="float32")

    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    transcriptions = []
    for seg in speech_segments:
        start_sample = int(seg.start * sr)
        end_sample = int(seg.end * sr)
        chunk = audio_data[start_sample:end_sample]

        if len(chunk) < 1600:
            continue

        # Whisper expects float32 numpy array at 16kHz
        chunk = chunk.astype(np.float32)
        result = model.transcribe(chunk, fp16=False)
        text = result.get("text", "").strip()

        if text:
            transcriptions.append(
                Transcription(start=seg.start, end=seg.end, text=text)
            )

    return transcriptions
