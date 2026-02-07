import argparse
import json
import numpy as np
import librosa
import tensorflow_hub as hub
from pyannote.audio import Pipeline
from pydub import AudioSegment


# ----------------------------
# Utility functions
# ----------------------------

def mp3_to_wav_16k_mono(mp3_path):
    audio = AudioSegment.from_file(mp3_path)
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(16000)

    samples = np.array(audio.get_array_of_samples()).astype(np.float32)

    # Normalize to [-1, 1]
    samples /= np.iinfo(audio.array_type).max

    return samples, 16000


def merge_segments(segments, gap=0.2):
    """
    Merge adjacent segments of the same label if separated by <= gap seconds.
    """
    if not segments:
        return []

    merged = [segments[0]]

    for seg in segments[1:]:
        prev = merged[-1]
        if seg["label"] == prev["label"] and seg["start"] <= prev["end"] + gap:
            prev["end"] = max(prev["end"], seg["end"])
        else:
            merged.append(seg)

    return merged


def smooth_labels(frame_labels, min_run=2):
    """
    Removes short flickering runs shorter than min_run frames.
    """
    if len(frame_labels) == 0:
        return frame_labels

    smoothed = frame_labels.copy()
    i = 0
    while i < len(smoothed):
        j = i
        while j < len(smoothed) and smoothed[j] == smoothed[i]:
            j += 1
        run_len = j - i

        if run_len < min_run:
            # replace short run with previous label if possible
            if i > 0:
                for k in range(i, j):
                    smoothed[k] = smoothed[i - 1]
            elif j < len(smoothed):
                for k in range(i, j):
                    smoothed[k] = smoothed[j]

        i = j

    return smoothed


def in_any_interval(t0, t1, intervals):
    """
    Checks if [t0,t1] overlaps any speech interval.
    """
    for s0, s1 in intervals:
        if t1 > s0 and t0 < s1:
            return True
    return False


# ----------------------------
# Main labeling pipeline
# ----------------------------

def run_pyannote_sad(waveform, sr, hf_token):
    """
    Runs pyannote speech activity detection.
    Returns list of (start, end) speech intervals.
    """
    pipeline = Pipeline.from_pretrained(
        "pyannote/voice-activity-detection",
        use_auth_token=hf_token
    )

    # pyannote expects dict input
    output = pipeline({"waveform": waveform, "sample_rate": sr})

    speech_intervals = []
    for segment in output.get_timeline().support():
        speech_intervals.append((segment.start, segment.end))

    return speech_intervals


def run_yamnet(waveform, sr):
    """
    Runs pretrained YAMNet model from TF Hub.
    Returns (scores, embeddings, spectrogram).
    """
    yamnet = hub.load("https://tfhub.dev/google/yamnet/1")
    scores, embeddings, spectrogram = yamnet(waveform)
    return scores.numpy(), embeddings.numpy(), spectrogram.numpy()


def build_labels(waveform, sr, speech_intervals, yamnet_scores, class_map):
    """
    Build final labeled segments using pyannote speech mask + yamnet classes.
    """
    # YAMNet frame hop size is about 0.48 sec (internally ~0.96 sec windows)
    # In practice, treat frames as evenly spaced over audio duration.
    duration = len(waveform) / sr
    num_frames = yamnet_scores.shape[0]
    frame_len = duration / num_frames

    labels = []

    # Class indices of interest
    speech_idx = class_map.get("Speech")
    music_idx = class_map.get("Music")
    singing_idx = class_map.get("Singing")
    percussion_idx = class_map.get("Percussion")
    drum_idx = class_map.get("Drum")
    beatboxing_idx = class_map.get("Beatboxing")

    for i in range(num_frames):
        t0 = i * frame_len
        t1 = (i + 1) * frame_len

        # If pyannote says speech, override
        if in_any_interval(t0, t1, speech_intervals):
            labels.append("speech")
            continue

        scores = yamnet_scores[i]

        # Pull probabilities (if class missing, treat as 0)
        speech_score = scores[speech_idx] if speech_idx is not None else 0.0
        music_score = scores[music_idx] if music_idx is not None else 0.0
        singing_score = scores[singing_idx] if singing_idx is not None else 0.0
        perc_score = scores[percussion_idx] if percussion_idx is not None else 0.0
        drum_score = scores[drum_idx] if drum_idx is not None else 0.0
        beatboxing_score = scores[beatboxing_idx] if beatboxing_idx is not None else 0.0

        # Rule-based labeling
        if speech_score > 0.4:
            label = "speech"
        elif (singing_score + music_score) > 0.6:
            label = "humming/music"
        elif (beatboxing_score + perc_score + drum_score) > 0.5:
            label = "rhythm/percussion"
        else:
            label = "other"

        labels.append(label)

    # Smooth flickering labels
    labels = smooth_labels(labels, min_run=2)

    # Convert frame labels to time segments
    segments = []
    cur_label = labels[0]
    start = 0.0

    for i in range(1, len(labels)):
        if labels[i] != cur_label:
            end = i * frame_len
            segments.append({"start": start, "end": end, "label": cur_label})
            cur_label = labels[i]
            start = i * frame_len

    segments.append({"start": start, "end": duration, "label": cur_label})

    # Merge adjacent segments of same label
    segments = merge_segments(segments, gap=0.2)

    return segments


# ----------------------------
# Load YAMNet class labels
# ----------------------------

def load_yamnet_class_map():
    """
    Downloads the YAMNet class map.
    """
    import urllib.request

    url = "https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv"
    data = urllib.request.urlopen(url).read().decode("utf-8").splitlines()

    class_map = {}
    for line in data[1:]:
        parts = line.split(",")
        idx = int(parts[0])
        display_name = parts[2]
        class_map[display_name] = idx

    return class_map


# ----------------------------
# Entry point
# ----------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mp3_path", help="Input MP3 file")
    parser.add_argument("--hf_token", required=True, help="HuggingFace token for pyannote")
    parser.add_argument("--out", default="labels.json", help="Output JSON file")
    args = parser.parse_args()

    print("[1/5] Loading MP3 and converting to 16kHz mono...")
    waveform, sr = mp3_to_wav_16k_mono(args.mp3_path)

    print("[2/5] Loading YAMNet class map...")
    class_map = load_yamnet_class_map()

    print("[3/5] Running pyannote speech activity detection...")
    speech_intervals = run_pyannote_sad(waveform, sr, args.hf_token)

    print("[4/5] Running YAMNet...")
    yamnet_scores, yamnet_embeddings, yamnet_spectrogram = run_yamnet(waveform, sr)

    print("[5/5] Building labeled segments...")
    segments = build_labels(waveform, sr, speech_intervals, yamnet_scores, class_map)

    output = {
        "file": args.mp3_path,
        "sample_rate": sr,
        "speech_intervals": [{"start": s, "end": e} for (s, e) in speech_intervals],
        "segments": segments
    }

    with open(args.out, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Done. Wrote labeled timeline to {args.out}")


if __name__ == "__main__":
    main()
