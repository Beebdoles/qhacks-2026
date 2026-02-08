from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import NoteEvent

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _midi_to_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def format_extracted_notes(notes: list[NoteEvent]) -> str:
    """Format BasicPitch-extracted notes into a prompt section for Gemini."""
    if not notes:
        return ""

    lines = [
        "",
        "## Extracted Pitch Data (from pitch detection — use as ground truth)",
        "",
        "The following notes were extracted from the audio using a pitch detection algorithm.",
        "For singing/humming segments, use these pitches and timings as the ground truth",
        "for your melody. Convert them to scale degrees relative to your chosen tonality",
        "and chords, and quantize durations to the nearest w/h/q/e/s.",
        "Do NOT invent new melody notes — use these detected pitches.",
        "",
    ]
    for n in notes:
        lines.append(
            f"  pitch={n.pitch} ({_midi_to_name(n.pitch)}), "
            f"start={n.start:.3f}s, end={n.end:.3f}s, velocity={n.velocity}"
        )

    return "\n".join(lines)


ANALYSIS_PROMPT = """Analyze the provided audio file and produce a complete musical analysis with two parts:

## Part 1 — Audio Segmentation

Produce a timeline of non-overlapping segments that covers the entire duration from start to finish.

Classify each segment as one of the following types:
- "silence": No meaningful audio activity, background noise, or non-vocal sounds.
- "speech": Spoken words or talking with no melody. These will likely be instructions or conversations. Do not confuse with singing with lyrics.
- "singing": Vocal singing with lyrics. These will likely be songs or vocal performances. Do not confuse with speech or humming.
- "humming": Vocal humming — melodic, closed-mouth vocalization without words. Do not confuse with speech or singing with lyrics.
- "beatboxing": Vocal percussion or beatboxing — rhythmic sounds produced with the mouth, lips, tongue, and voice to imitate drums and other instruments.

Segmentation requirements:
- Provide start and end timestamps in seconds (decimals allowed).
- Segments must be contiguous with no gaps: each segment's start must equal the previous segment's end.
- The first segment must start at 0 and the last segment must end at the total audio duration.
- Segments must not overlap.
- If audio is ambiguous, classify it as the closest matching type. Use "silence" for background noise or any non-vocal audio that doesn't fit the other categories.

## Part 2 — Musical Structure (MusicLang-compatible)

For each non-silence, non-speech segment, generate chord progressions with per-instrument melodies compatible with the MusicLang library:
- Scale degrees 0-6 (not note names) for melody notes
- Chord degrees 1-7 with quality "M" (major) or "m" (minor)
- Duration codes: "w" (whole), "h" (half), "q" (quarter), "e" (eighth), "s" (sixteenth)
- Instrument names: piano, violin, flute, cello, acoustic_guitar, etc.
- A top-level tonality field (degree 1-7 + quality "M"/"m")

Composition guidelines:
- For "beatboxing" segments, use percussive drum patterns with short durations (e/s) on piano in low octaves (-1, -2). These will become a percussion/drum track.
- For "singing" or "humming" segments, create melodic lines with longer notes (q/h). These will become the melody track.
- You MUST set the top-level "singing_instrument" field to either "piano" or "flute" — pick whichever best matches the character of the singing (breathy/airy → flute, rhythmic/chordal → piano).
- "speech" and "silence" segments should have empty chords arrays.
- Each chord's total note durations should roughly match duration_beats in quarter notes.
- Use octave 0 as the default, -1 for bass, 1 for higher register.
- Each segment type will be exported as a separate MIDI file so they can be layered together. Design each type to sound good independently and when combined.
"""
