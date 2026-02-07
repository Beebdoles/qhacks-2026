from basic_pitch.inference import predict

from models import NoteEvent, Segment


def extract_melody(
    wav_path: str, humming_segments: list[Segment]
) -> list[NoteEvent]:
    """Extract melody notes from humming segments using BasicPitch."""
    if not humming_segments:
        return []

    # Run BasicPitch on the full audio
    model_output, midi_data, note_events = predict(wav_path)

    # Filter notes to only those within humming segment time ranges
    notes = []
    for start_sec, end_sec, pitch, velocity, _ in note_events:
        for seg in humming_segments:
            # Note overlaps with a humming segment
            if start_sec < seg.end and end_sec > seg.start:
                notes.append(
                    NoteEvent(
                        pitch=int(pitch),
                        start=float(start_sec),
                        end=float(end_sec),
                        velocity=min(int(velocity * 127), 127),
                    )
                )
                break

    return notes
