import concurrent.futures
import os
import subprocess
import tempfile

from basic_pitch.inference import predict

from models import NoteEvent

BASICPITCH_TIMEOUT = 120  # seconds for full audio
MIN_DURATION = 0.05       # ignore notes shorter than 50ms
MIN_VELOCITY = 35         # ignore quiet detections (likely noise/harmonics)
MERGE_GAP = 0.08          # merge notes with gap < 80ms
PITCH_TOLERANCE = 1       # merge notes within 1 semitone
LEGATO_FILL = 0.15        # fill gaps shorter than 150ms between notes


def _ensure_wav(audio_path: str) -> tuple[str, bool]:
    """Convert to WAV if needed. Returns (wav_path, needs_cleanup)."""
    if audio_path.lower().endswith(".wav"):
        return audio_path, False

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-i", audio_path, "-ar", "22050", "-ac", "1", tmp.name],
        capture_output=True, check=True,
    )
    return tmp.name, True


def _smooth_notes(notes: list[NoteEvent]) -> list[NoteEvent]:
    """Merge jittery adjacent notes and filter out short artifacts."""
    if not notes:
        return notes

    # Filter out very short and very quiet notes (noise/harmonics)
    notes = [n for n in notes if (n.end - n.start) >= MIN_DURATION and n.velocity >= MIN_VELOCITY]
    if not notes:
        return []

    # Sort by start time
    notes.sort(key=lambda n: n.start)

    merged: list[NoteEvent] = [notes[0]]
    for note in notes[1:]:
        prev = merged[-1]
        gap = note.start - prev.end
        pitch_diff = abs(note.pitch - prev.pitch)

        if pitch_diff <= PITCH_TOLERANCE and gap <= MERGE_GAP:
            # Merge: extend prev note, keep pitch of the longer one
            prev_dur = prev.end - prev.start
            note_dur = note.end - note.start
            winning_pitch = prev.pitch if prev_dur >= note_dur else note.pitch
            merged[-1] = NoteEvent(
                pitch=winning_pitch,
                start=prev.start,
                end=note.end,
                velocity=max(prev.velocity, note.velocity),
            )
        else:
            merged.append(note)

    # Fill small gaps by extending the previous note (legato)
    filled: list[NoteEvent] = [merged[0]]
    for note in merged[1:]:
        prev = filled[-1]
        gap = note.start - prev.end
        if 0 < gap <= LEGATO_FILL:
            # Stretch previous note to close the gap
            filled[-1] = NoteEvent(
                pitch=prev.pitch,
                start=prev.start,
                end=note.start,
                velocity=prev.velocity,
            )
        filled.append(note)

    return filled


def extract_melody(audio_path: str) -> list[NoteEvent]:
    """Run BasicPitch on the full audio and return extracted note events."""
    wav_path, cleanup = _ensure_wav(audio_path)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(
                predict, wav_path,
                onset_threshold=0.4,
                frame_threshold=0.25,
                minimum_note_length=80,
            )
            try:
                _, _, note_events = future.result(timeout=BASICPITCH_TIMEOUT)
            except concurrent.futures.TimeoutError:
                print("[melody] BasicPitch timed out, returning empty notes")
                return []
    finally:
        if cleanup and os.path.exists(wav_path):
            os.unlink(wav_path)

    notes = []
    for start_sec, end_sec, pitch, velocity, _ in note_events:
        notes.append(
            NoteEvent(
                pitch=int(pitch),
                start=round(float(start_sec), 3),
                end=round(float(end_sec), 3),
                velocity=min(int(velocity * 127), 127),
            )
        )

    raw_count = len(notes)
    notes = _smooth_notes(notes)
    print(f"[melody] BasicPitch extracted {raw_count} notes, smoothed to {len(notes)}")
    return notes
