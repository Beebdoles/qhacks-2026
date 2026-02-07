import os
import traceback

import soundfile as sf

from models import JobStatus, Segment

# In-memory job store
jobs: dict[str, JobStatus] = {}


def _get_audio_duration(wav_path: str) -> float:
    info = sf.info(wav_path)
    return info.duration


def _compute_non_speech_segments(
    speech_segments: list[Segment], duration: float, min_gap: float = 0.3
) -> list[Segment]:
    """Find gaps between speech segments that are long enough to analyze."""
    non_speech = []
    prev_end = 0.0

    sorted_segs = sorted(speech_segments, key=lambda s: s.start)
    for seg in sorted_segs:
        if seg.start - prev_end >= min_gap:
            non_speech.append(
                Segment(start=prev_end, end=seg.start, type="unknown")
            )
        prev_end = seg.end

    if duration - prev_end >= min_gap:
        non_speech.append(Segment(start=prev_end, end=duration, type="unknown"))

    return non_speech


def run_pipeline(job_id: str, audio_path: str) -> None:
    """Execute the full audio-to-MIDI pipeline, updating job state after each step."""
    job = jobs[job_id]
    job.status = "processing"

    try:
        # Step 1: Preprocess
        job.progress = 10
        from pipeline.preprocess import preprocess
        wav_path = preprocess(audio_path)

        duration = _get_audio_duration(wav_path)

        # Step 2: Silero VAD
        job.progress = 25
        from pipeline.segmenter import detect_speech_segments
        speech_segments = detect_speech_segments(wav_path)

        # Step 3: Classify non-speech segments
        job.progress = 40
        non_speech = _compute_non_speech_segments(speech_segments, duration)

        from pipeline.classifier import classify_segments
        classified = classify_segments(wav_path, non_speech)

        all_segments = sorted(speech_segments + classified, key=lambda s: s.start)
        job.segments = all_segments

        # Step 4: Transcribe speech
        job.progress = 55
        from pipeline.transcriber import transcribe_speech
        transcriptions = transcribe_speech(wav_path, speech_segments)
        job.transcriptions = transcriptions

        # Step 5: Extract melody from humming
        job.progress = 70
        humming_segs = [s for s in all_segments if s.type == "humming"]
        from pipeline.melody import extract_melody
        melody_notes = extract_melody(wav_path, humming_segs)

        # Step 6: Extract drums from beatboxing
        job.progress = 85
        beatbox_segs = [s for s in all_segments if s.type == "beatboxing"]
        from pipeline.drums import extract_drums
        drum_hits = extract_drums(wav_path, beatbox_segs)

        # Step 7: Assemble MIDI
        job.progress = 95
        output_dir = os.path.dirname(audio_path)
        from pipeline.assembler import assemble_midi
        midi_path = assemble_midi(melody_notes, drum_hits, output_dir)

        job.midi_path = midi_path
        job.progress = 100
        job.status = "complete"

    except Exception as e:
        job.status = "failed"
        job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
