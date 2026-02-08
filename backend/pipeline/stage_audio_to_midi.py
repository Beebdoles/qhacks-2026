import os
from typing import Callable

from models import Segment, SegmentMidiResult, SegmentType
from pipeline.audio_to_midi import audio_to_melody_midi, audio_to_drum_midi

INSTRUMENT_MAP = {
    "singing": "Acoustic Grand Piano",
    "humming": "Flute",
}

ELIGIBLE_TYPES = {"singing", "humming", "beatboxing"}


def run_audio_to_midi_stage(
    segments: list[Segment],
    job_dir: str,
    progress_callback: Callable[[int], None] | None = None,
) -> list[SegmentMidiResult]:
    """Convert eligible audio segments to individual MIDI files.

    Returns a list of SegmentMidiResult (both successes and failures).
    """
    results: list[SegmentMidiResult] = []

    eligible = [
        (i, seg) for i, seg in enumerate(segments)
        if seg.type.value in ELIGIBLE_TYPES and seg.audio_path
    ]

    for idx, (seg_idx, seg) in enumerate(eligible):
        seg_type = seg.type.value
        instrument = INSTRUMENT_MAP.get(seg_type, "Acoustic Grand Piano")

        try:
            if seg_type in ("singing", "humming"):
                midi = audio_to_melody_midi(seg.audio_path, instrument)
            else:  # beatboxing
                midi = audio_to_drum_midi(seg.audio_path)
                instrument = "Percussion"

            # Save per-segment MIDI
            midi_filename = f"segment_{seg_idx}_{seg_type}.mid"
            midi_path = os.path.join(job_dir, midi_filename)
            midi.write(midi_path)

            results.append(SegmentMidiResult(
                segment_index=seg_idx,
                segment_type=seg.type,
                midi_path=midi_path,
                start_offset=0.0,
                instrument=instrument,
            ))
            print(f"[audio_to_midi] Segment {seg_idx} ({seg_type}): OK -> {midi_filename}")

        except Exception as e:
            results.append(SegmentMidiResult(
                segment_index=seg_idx,
                segment_type=seg.type,
                midi_path=None,
                start_offset=seg.start,
                instrument=instrument,
                error=f"{type(e).__name__}: {e}",
            ))
            print(f"[audio_to_midi] Segment {seg_idx} ({seg_type}): FAILED - {e}")

        if progress_callback:
            progress_callback(idx)

    return results
