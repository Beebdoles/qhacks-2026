import os

from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

from models import GeminiAnalysis, SegmentType

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Segment types that contain musical content
MUSICAL_TYPES = {SegmentType.singing, SegmentType.humming, SegmentType.beatboxing}


def run_transcribe_stage(
    analysis: GeminiAnalysis, audio_path: str, job_id: str
) -> str:
    """Slice all segments, transcribe speech via ElevenLabs, and build an instruction document."""
    tag = f"[transcribe:{job_id[:8]}]"

    # Load full audio
    audio = AudioSegment.from_file(audio_path)

    job_dir = os.path.dirname(audio_path)

    for i, seg in enumerate(analysis.segments):
        if seg.type == SegmentType.silence:
            continue

        start_ms = int(seg.start * 1000)
        end_ms = int(seg.end * 1000)
        clip = audio[start_ms:end_ms]

        # Save clip — named by type and index
        clip_filename = f"segment_{i}_{seg.type.value}.mp3"
        clip_path = os.path.join(job_dir, clip_filename)
        clip.export(clip_path, format="mp3")
        seg.audio_clip_path = clip_path

        print(f"{tag} Sliced segment {i} ({seg.type.value}, {seg.start:.1f}s-{seg.end:.1f}s) → {clip_filename}")

        # Transcribe speech segments
        if seg.type == SegmentType.speech:
            print(f"{tag} Transcribing segment {i}...")
            with open(clip_path, "rb") as f:
                result = client.speech_to_text.convert(
                    model_id="scribe_v1",
                    file=f,
                )
            seg.transcription = result.text.strip()
            print(f"{tag}   → \"{seg.transcription}\"")

    # Build instruction document
    instruction_doc = _build_instruction_doc(analysis)
    print(f"{tag} Instruction document built ({len(instruction_doc)} chars).")

    return instruction_doc


def _build_instruction_doc(analysis: GeminiAnalysis) -> str:
    """Build a structured timeline interleaving speech and musical segments."""
    lines = []
    lines.append(
        f"Audio analysis: tempo={analysis.tempo_bpm}bpm, "
        f"time_signature={analysis.time_signature[0]}/{analysis.time_signature[1]}, "
        f"key=degree {analysis.tonality.degree} {analysis.tonality.quality}"
    )
    lines.append("")

    for i, seg in enumerate(analysis.segments):
        time_range = f"{seg.start:.1f}s - {seg.end:.1f}s"
        path_ref = f" [file: {seg.audio_clip_path}]" if seg.audio_clip_path else ""

        if seg.type == SegmentType.speech:
            text = seg.transcription or "(transcription unavailable)"
            lines.append(f"[{time_range} | SPEECH]: \"{text}\"{path_ref}")

        elif seg.type == SegmentType.silence:
            lines.append(f"[{time_range} | SILENCE]")

        elif seg.type in MUSICAL_TYPES:
            label = seg.type.value.upper()
            chord_summary = ""
            if seg.chords:
                degrees = [f"{c.degree}" for c in seg.chords]
                chord_summary = f", chords: {' → '.join(degrees)}"
            lines.append(
                f"[{time_range} | {label}]: Musical segment"
                f" ({len(seg.chords)} chords{chord_summary}){path_ref}"
            )

    return "\n".join(lines)
