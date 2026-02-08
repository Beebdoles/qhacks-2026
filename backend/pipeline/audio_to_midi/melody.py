import pretty_midi

from .preprocessing import preprocess_audio
from .pitch_detection import detect_pitch
from .confidence_filter import filter_pitch
from .onset_detection import detect_onsets
from .note_segmentation import segment_notes
from .key_detection import detect_key, snap_notes_to_key
from .quantization import detect_tempo, quantize_notes, build_melody_midi


def audio_to_melody_midi(
    audio_path: str, instrument: str
) -> pretty_midi.PrettyMIDI:
    """Convert audio to a melody MIDI track.

    Orchestrates the full melody pipeline:
    preprocessing -> pitch detection -> filtering -> onset detection ->
    note segmentation -> key detection -> quantization -> MIDI building.
    """
    print(f"[melody] Processing: {audio_path}")

    # Stage 1: Preprocess
    harmonic, original, sr = preprocess_audio(audio_path)
    print(f"[melody] Preprocessed: {len(original)} samples @ {sr}Hz")

    # Stage 2: Pitch detection
    times, frequencies, confidences = detect_pitch(harmonic, original, sr)
    print(f"[melody] Pitch detected: {len(times)} frames")

    # Stage 3: Confidence filtering
    times, frequencies, confidences = filter_pitch(times, frequencies, confidences)

    # Stage 4: Onset detection (uses original audio)
    onset_times = detect_onsets(original, sr)
    print(f"[melody] Onsets detected: {len(onset_times)}")

    # Stage 5: Note segmentation
    raw_notes = segment_notes(times, frequencies, confidences, onset_times)
    print(f"[melody] Raw notes: {len(raw_notes)}")

    if not raw_notes:
        raise ValueError(
            "No melody detected in segment — audio may be too quiet, "
            "too noisy, or not contain pitched content"
        )

    # Stage 6: Key detection + snap (uses original audio)
    root, mode = detect_key(original, sr, raw_notes)
    midi_notes = snap_notes_to_key(raw_notes, root, mode)
    print(f"[melody] Key: {root} {mode}, {len(midi_notes)} MIDI notes")

    # Stage 7: Tempo + quantization (uses original audio)
    tempo, reliable = detect_tempo(original, sr)
    midi_notes = quantize_notes(midi_notes, tempo, reliable)
    print(f"[melody] Tempo: {tempo:.1f} BPM (reliable={reliable})")

    # Build final MIDI
    midi = build_melody_midi(midi_notes, tempo, instrument)
    print(f"[melody] MIDI built: {len(midi.instruments[0].notes)} notes")

    return midi
