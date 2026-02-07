import librosa
import numpy as np

from models import DrumHit, Segment

# General MIDI drum map
KICK_NOTE = 36
SNARE_NOTE = 38
HIHAT_NOTE = 42


def extract_drums(
    wav_path: str, beatbox_segments: list[Segment]
) -> list[DrumHit]:
    """Extract drum hits from beatbox segments using onset detection + spectral classification."""
    if not beatbox_segments:
        return []

    y, sr = librosa.load(wav_path, sr=16000, mono=True)
    hits = []

    for seg in beatbox_segments:
        start_sample = int(seg.start * sr)
        end_sample = int(seg.end * sr)
        chunk = y[start_sample:end_sample]

        if len(chunk) < 512:
            continue

        # Detect onsets
        onset_frames = librosa.onset.onset_detect(
            y=chunk, sr=sr, hop_length=512, backtrack=True
        )
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)

        for onset_t in onset_times:
            abs_time = seg.start + onset_t
            # Analyze spectral centroid around the onset
            onset_sample = int(onset_t * sr)
            window_start = max(0, onset_sample - 256)
            window_end = min(len(chunk), onset_sample + 512)
            window = chunk[window_start:window_end]

            if len(window) < 64:
                continue

            centroid = librosa.feature.spectral_centroid(
                y=window, sr=sr, hop_length=len(window)
            )
            avg_centroid = float(np.mean(centroid))

            if avg_centroid < 500:
                hits.append(DrumHit(time=abs_time, drum="kick"))
            elif avg_centroid < 3000:
                hits.append(DrumHit(time=abs_time, drum="snare"))
            else:
                hits.append(DrumHit(time=abs_time, drum="hihat"))

    return hits
