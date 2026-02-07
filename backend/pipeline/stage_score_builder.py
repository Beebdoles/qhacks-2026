import os

from musiclang.write.score import Score
from musiclang.write.library import (
    s0, s1, s2, s3, s4, s5, s6,
    I, II, III, IV, V, VI, VII,
    r,
)

from models import GeminiAnalysis, NoteData, ChordData, Tonality

# ── MusicLang lookup tables ──────────────────────────────────────────

DEGREE_MAP = {1: I, 2: II, 3: III, 4: IV, 5: V, 6: VI, 7: VII}
SCALE_NOTE_MAP = {0: s0, 1: s1, 2: s2, 3: s3, 4: s4, 5: s5, 6: s6}
DURATION_MAP = {"w": "w", "h": "h", "q": "q", "e": "e", "s": "s"}
QUALITY_MAP = {"M": "M", "m": "m"}

# ── Builder helpers ──────────────────────────────────────────────────


def build_note(note: NoteData):
    """Convert a NoteData into a MusicLang Note."""
    degree = max(0, min(6, note.s))
    ml_note = SCALE_NOTE_MAP.get(degree, s0)

    if note.octave != 0:
        ml_note = ml_note.o(note.octave)

    dur_attr = DURATION_MAP.get(note.duration.value, "q")
    ml_note = getattr(ml_note, dur_attr)
    return ml_note


def build_melody(notes: list[NoteData]):
    """Concatenate note dicts into a MusicLang melody."""
    if not notes:
        return r.q
    melody = build_note(notes[0])
    for n in notes[1:]:
        melody = melody + build_note(n)
    return melody


def build_chord(chord: ChordData, tonality_obj):
    """Build a MusicLang chord expression with instrument melodies."""
    deg = max(1, min(7, chord.degree))
    chord_degree = DEGREE_MAP.get(deg, I)
    chord_expr = chord_degree % tonality_obj

    if not chord.instruments:
        return chord_expr(piano=r.q)

    kwargs = {}
    for inst_name, notes_list in chord.instruments.items():
        inst_name = inst_name.strip().lower()
        if not notes_list:
            continue
        kwargs[inst_name] = build_melody(notes_list)

    if not kwargs:
        return chord_expr(piano=r.q)

    return chord_expr(**kwargs)


def build_tonality(tonality: Tonality):
    """Convert Tonality model to a MusicLang Tonality object."""
    deg = max(1, min(7, tonality.degree))
    quality = QUALITY_MAP.get(tonality.quality, "M")
    base = DEGREE_MAP.get(deg, I)
    return getattr(base, quality)


# ── Stage entry point ────────────────────────────────────────────────


def run_score_builder_stage(
    analysis: GeminiAnalysis, job_dir: str
) -> dict[str, str]:
    """Build MusicLang scores per segment type and export to MIDI.

    Returns {seg_type: midi_path} mapping.
    """
    tempo = analysis.tempo_bpm
    ts = analysis.time_signature
    if len(ts) == 2:
        time_sig = (ts[0], ts[1])
    else:
        time_sig = (4, 4)

    tonality_obj = build_tonality(analysis.tonality)

    # Group chords by segment type (skip silence/speech)
    chords_by_type: dict[str, list] = {}
    for segment in analysis.segments:
        seg_type = segment.type.value
        if seg_type in ("silence", "speech"):
            continue
        for chord_data in segment.chords:
            chords_by_type.setdefault(seg_type, []).append(
                build_chord(chord_data, tonality_obj)
            )

    # Build one Score per type and export to MIDI
    midi_paths: dict[str, str] = {}
    for seg_type, chord_list in chords_by_type.items():
        if not chord_list:
            chord_list = [(I % tonality_obj)(piano=r.w)]

        score = Score(chord_list, tempo=tempo, time_signature=time_sig)
        midi_path = os.path.join(job_dir, f"{seg_type}.mid")
        score.to_midi(midi_path)
        midi_paths[seg_type] = midi_path
        print(f"[score_builder] {seg_type} -> {midi_path}")

    return midi_paths
