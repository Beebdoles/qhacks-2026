import concurrent.futures
import os
import tempfile

import soundfile as sf
from basic_pitch.inference import predict

from models import NoteEvent, Segment

BASICPITCH_TIMEOUT = 60  # seconds per segment


def extract_melody(
    wav_path: str, humming_segments: list[Segment]
) -> list[NoteEvent]:
    """Extract melody notes from humming segments using BasicPitch."""
    if not humming_segments:
        return []

    audio_data, sr = sf.read(wav_path, dtype="float32")
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    notes = []
    for i, seg in enumerate(humming_segments):
        duration = seg.end - seg.start
        print(f"[melody] Processing humming segment {i+1}/{len(humming_segments)}: {seg.start:.2f}-{seg.end:.2f}s ({duration:.1f}s)")

        start_sample = int(seg.start * sr)
        end_sample = int(seg.end * sr)
        chunk = audio_data[start_sample:end_sample]

        if len(chunk) < sr * 0.1:
            continue

        # Write chunk to a temp WAV so BasicPitch can read it
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                sf.write(tmp_path, chunk, sr)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(predict, tmp_path)
                try:
                    _, _, note_events = future.result(timeout=BASICPITCH_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    print(f"[melody] BasicPitch timed out on segment {seg.start:.2f}-{seg.end:.2f}s, skipping")
                    continue

            for start_sec, end_sec, pitch, velocity, _ in note_events:
                notes.append(
                    NoteEvent(
                        pitch=int(pitch),
                        start=float(seg.start + start_sec),
                        end=float(seg.start + end_sec),
                        velocity=min(int(velocity * 127), 127),
                    )
                )
            print(f"[melody] Got {len(note_events)} notes from segment {i+1}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return notes
