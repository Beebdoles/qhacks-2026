import concurrent.futures

import numpy as np
import soundfile as sf
import whisper

from models import Segment, Transcription

TRANSCRIBE_TIMEOUT = 15  # seconds per segment

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
    for i, seg in enumerate(speech_segments):
        duration = seg.end - seg.start
        print(f"[transcriber] Transcribing segment {i+1}/{len(speech_segments)}: {seg.start:.2f}-{seg.end:.2f}s ({duration:.1f}s)")

        start_sample = int(seg.start * sr)
        end_sample = int(seg.end * sr)
        chunk = audio_data[start_sample:end_sample]

        if len(chunk) < 1600:
            print(f"[transcriber] Segment too short, skipping")
            continue

        # Whisper expects float32 numpy array at 16kHz
        chunk = chunk.astype(np.float32)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(model.transcribe, chunk, fp16=False)
            try:
                result = future.result(timeout=TRANSCRIBE_TIMEOUT)
            except concurrent.futures.TimeoutError:
                print(f"[transcriber] Whisper timed out on segment {seg.start:.2f}-{seg.end:.2f}s, skipping")
                continue
        text = result.get("text", "").strip()
        print(f"[transcriber] Result: \"{text}\"")

        if text:
            transcriptions.append(
                Transcription(start=seg.start, end=seg.end, text=text)
            )

    return transcriptions
