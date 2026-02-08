import os
import subprocess

from models import GeminiAnalysis, Segment, SegmentType


def run_audio_splitter_stage(
    analysis: GeminiAnalysis, audio_path: str, job_dir: str
) -> list[Segment]:
    """Filter out silence segments and split audio into individual files."""
    tag = "[audio_splitter]"

    non_silence = [
        seg for seg in analysis.segments if seg.type != SegmentType.silence
    ]

    print(f"{tag} Splitting {len(non_silence)} non-silence segments...")

    for i, seg in enumerate(non_silence):
        filename = f"segment_{i}_{seg.type.value}_{seg.start}_{seg.end}.mp3"
        output_path = os.path.join(job_dir, filename)

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(seg.start),
                "-to", str(seg.end),
                output_path,
            ],
            capture_output=True,
            check=True,
        )

        seg.audio_path = output_path
        print(f"{tag}   [{i}] {seg.type.value} {seg.start:.2f}-{seg.end:.2f}s → {filename}")

    print(f"{tag} Done! {len(non_silence)} audio files created.")
    return non_silence
