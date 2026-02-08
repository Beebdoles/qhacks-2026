import librosa
import numpy as np
import pretty_midi
from scipy.signal import butter, sosfilt

from .config import (
    SAMPLE_RATE,
    KICK_CENTROID_MAX,
    HIHAT_CENTROID_MIN,
    HIT_WINDOW_PRE,
    HIT_WINDOW_POST,
    HIHAT_DECAY_THRESHOLD_MS,
    HIHAT_DECAY_DB,
    HIT_MIN_AMPLITUDE_DB,
)
from .utils import detect_tempo_from_onsets


# GM drum map
KICK = 36
SNARE = 38
CLOSED_HIHAT = 42
OPEN_HIHAT = 46


def audio_to_drum_midi(audio_path: str) -> pretty_midi.PrettyMIDI:
    """Convert beatboxing audio to a drum MIDI track.

    Three stages: onset detection + amplitude gate, hit classification, MIDI building.
    """
    print(f"[percussion] Processing: {audio_path}")

    # Load audio
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)

    # ── Stage 1: Onset detection + amplitude gate ─────────────────────
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="frames")
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # Extract windows and filter by amplitude (Revision #19)
    hits = []
    for onset_time in onset_times:
        onset_sample = int(onset_time * sr)
        win_start = max(0, onset_sample - int(HIT_WINDOW_PRE * sr))
        win_end = min(len(y), onset_sample + int(HIT_WINDOW_POST * sr))
        window = y[win_start:win_end]

        if len(window) == 0:
            continue

        # Amplitude gate
        peak_amp = np.max(np.abs(window))
        if peak_amp > 0:
            peak_db = 20 * np.log10(peak_amp)
        else:
            peak_db = -100

        if peak_db < HIT_MIN_AMPLITUDE_DB:
            continue

        hits.append((onset_time, window))

    print(f"[percussion] {len(hits)} hits after amplitude gate (from {len(onset_times)} onsets)")

    # ── Stage 2: Classify each hit ────────────────────────────────────
    classified_hits = []
    for onset_time, window in hits:
        centroid = float(librosa.feature.spectral_centroid(y=window, sr=sr).mean())
        rolloff = float(librosa.feature.spectral_rolloff(y=window, sr=sr).mean())

        if centroid < KICK_CENTROID_MAX:
            drum = KICK
        elif centroid > HIHAT_CENTROID_MIN:
            drum = _classify_hihat(window, sr)
        else:
            # Mid-range: use rolloff to distinguish snare vs weak kick
            mid_rolloff_threshold = sr * 0.5 * 0.6  # 60% of Nyquist
            if rolloff > mid_rolloff_threshold:
                drum = SNARE
            else:
                drum = KICK

        classified_hits.append((onset_time, drum))

    print(f"[percussion] Classification: {len(classified_hits)} hits")

    # ── Stage 3: Tempo + MIDI building ────────────────────────────────
    hit_times = np.array([t for t, _ in classified_hits]) if classified_hits else np.array([])
    tempo, reliable = detect_tempo_from_onsets(hit_times)
    print(f"[percussion] Tempo: {tempo:.1f} BPM (reliable={reliable})")

    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="Percussion")

    note_duration = 0.05  # 50ms fixed

    if reliable:
        beat_dur = 60.0 / tempo
        grid_dur = beat_dur / 4  # 16th note grid

        for onset_time, drum in classified_hits:
            # Quantize to grid
            grid_idx = round(onset_time / grid_dur)
            snapped = grid_idx * grid_dur
            offset = abs(onset_time - snapped)
            if offset / grid_dur <= 0.4:
                t = snapped
            else:
                t = onset_time

            note = pretty_midi.Note(
                velocity=100, pitch=drum, start=t, end=t + note_duration
            )
            drum_inst.notes.append(note)
    else:
        for onset_time, drum in classified_hits:
            note = pretty_midi.Note(
                velocity=100, pitch=drum, start=onset_time, end=onset_time + note_duration
            )
            drum_inst.notes.append(note)

    midi.instruments.append(drum_inst)
    print(f"[percussion] MIDI built: {len(drum_inst.notes)} drum hits")

    return midi


def _classify_hihat(window: np.ndarray, sr: int) -> int:
    """Classify hi-hat as open or closed based on decay envelope (Revision #11)."""
    # High-pass filter above 5kHz
    nyquist = sr / 2
    cutoff = min(HIHAT_CENTROID_MIN, nyquist - 1)
    if cutoff <= 0 or cutoff >= nyquist:
        return CLOSED_HIHAT

    sos = butter(4, cutoff / nyquist, btype="high", output="sos")
    filtered = sosfilt(sos, window)

    # Compute RMS envelope
    frame_length = max(64, int(sr * 0.005))  # 5ms frames
    hop = frame_length // 2
    rms = librosa.feature.rms(y=filtered, frame_length=frame_length, hop_length=hop)[0]

    if len(rms) == 0 or np.max(rms) == 0:
        return CLOSED_HIHAT

    # Find where RMS drops below threshold from peak
    peak_rms = np.max(rms)
    threshold = peak_rms * (10 ** (HIHAT_DECAY_DB / 20))

    peak_idx = np.argmax(rms)
    decay_samples = None
    for i in range(peak_idx, len(rms)):
        if rms[i] < threshold:
            decay_samples = (i - peak_idx) * hop
            break

    if decay_samples is None:
        return OPEN_HIHAT

    decay_ms = (decay_samples / sr) * 1000

    if decay_ms < HIHAT_DECAY_THRESHOLD_MS:
        return CLOSED_HIHAT
    else:
        return OPEN_HIHAT
