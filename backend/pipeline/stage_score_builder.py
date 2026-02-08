from __future__ import annotations

import json
import os

import mido
from musiclang.write.score import Score
from musiclang.write.library import (
    s0, s1, s2, s3, s4, s5, s6,
    I, II, III, IV, V, VI, VII,
    r,
)

from models import GeminiAnalysis, NoteData, NoteEvent, ChordData, Tonality, Segment

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


# ── Direct MIDI from BasicPitch notes ─────────────────────────────────

MELODY_TYPES = {"singing", "humming"}


def _notes_in_range(
    notes: list[NoteEvent], start: float, end: float
) -> list[NoteEvent]:
    """Filter notes whose onset falls within [start, end)."""
    return [n for n in notes if start <= n.start < end]


def _build_midi_from_notes(
    notes: list[NoteEvent], tempo: int, time_sig: tuple[int, int], output_path: str
) -> None:
    """Build a MIDI file directly from BasicPitch NoteEvent list."""
    ticks_per_beat = 480
    mid = mido.MidiFile(type=0, ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Tempo + time signature meta
    us_per_beat = int(60_000_000 / tempo)
    track.append(mido.MetaMessage("set_tempo", tempo=us_per_beat, time=0))
    track.append(mido.MetaMessage(
        "time_signature",
        numerator=time_sig[0], denominator=time_sig[1],
        clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0,
    ))

    if not notes:
        mid.save(output_path)
        return

    # Convert note events to MIDI messages sorted by absolute time
    events = []  # (abs_tick, type, pitch, velocity)
    sec_per_tick = 60.0 / (tempo * ticks_per_beat)
    for n in notes:
        on_tick = int(n.start / sec_per_tick)
        off_tick = int(n.end / sec_per_tick)
        events.append((on_tick, "note_on", n.pitch, n.velocity))
        events.append((off_tick, "note_off", n.pitch, 0))

    events.sort(key=lambda e: (e[0], e[1] == "note_on"))  # offs before ons at same tick

    prev_tick = 0
    for abs_tick, msg_type, pitch, vel in events:
        delta = max(0, abs_tick - prev_tick)
        track.append(mido.Message(msg_type, note=pitch, velocity=vel, time=delta))
        prev_tick = abs_tick

    mid.save(output_path)


# ── Stage entry point ────────────────────────────────────────────────


def run_score_builder_stage(
    analysis: GeminiAnalysis,
    job_dir: str,
    extracted_notes: list[NoteEvent] | None = None,
) -> dict[str, str]:
    """Build MusicLang scores per segment type and export to MIDI.

    For singing/humming: uses BasicPitch notes directly (accurate pitches).
    For beatboxing: uses Gemini → MusicLang (pattern generation).

    Returns {seg_type: midi_path} mapping.
    """
    tempo = analysis.tempo_bpm
    ts = analysis.time_signature
    if len(ts) == 2:
        time_sig = (ts[0], ts[1])
    else:
        time_sig = (4, 4)

    tonality_obj = build_tonality(analysis.tonality)

    if extracted_notes is None:
        extracted_notes = []

    # Collect segments by type
    segments_by_type: dict[str, list[Segment]] = {}
    for segment in analysis.segments:
        seg_type = segment.type.value
        if seg_type in ("silence", "speech"):
            continue
        segments_by_type.setdefault(seg_type, []).append(segment)

    midi_paths: dict[str, str] = {}

    for seg_type, segments in segments_by_type.items():
        midi_path = os.path.join(job_dir, f"{seg_type}.mid")

        if seg_type in MELODY_TYPES and extracted_notes:
            # Use BasicPitch notes directly for singing/humming
            relevant_notes = []
            for seg in segments:
                relevant_notes.extend(_notes_in_range(extracted_notes, seg.start, seg.end))

            # Shift notes to start at time 0 so all tracks overlap
            if relevant_notes:
                earliest = min(n.start for n in relevant_notes)
                relevant_notes = [
                    NoteEvent(
                        pitch=n.pitch,
                        start=n.start - earliest,
                        end=n.end - earliest,
                        velocity=n.velocity,
                    )
                    for n in relevant_notes
                ]

            # Dump BasicPitch notes used for this segment type
            with open(os.path.join(job_dir, f"debug_basicpitch_{seg_type}.json"), "w") as f:
                json.dump([n.model_dump() for n in relevant_notes], f, indent=2)

            _build_midi_from_notes(relevant_notes, tempo, time_sig, midi_path)
            print(f"[score_builder] {seg_type} -> {midi_path} (BasicPitch: {len(relevant_notes)} notes)")
        else:
            # Use Gemini → MusicLang for beatboxing and fallback
            # (MusicLang already starts at time 0)
            chord_list = []
            for seg in segments:
                for chord_data in seg.chords:
                    chord_list.append(build_chord(chord_data, tonality_obj))

            # Dump chord data input for MusicLang
            with open(os.path.join(job_dir, f"debug_musiclang_input_{seg_type}.json"), "w") as f:
                chords_dump = []
                for seg in segments:
                    for cd in seg.chords:
                        chords_dump.append(cd.model_dump())
                json.dump({"tonality": analysis.tonality.model_dump(), "tempo": tempo,
                           "time_sig": list(time_sig), "chords": chords_dump}, f, indent=2)

            if not chord_list:
                chord_list = [(I % tonality_obj)(piano=r.w)]

            score = Score(chord_list, tempo=tempo, time_signature=time_sig)
            # Dump MusicLang score to debug file
            debug_path = os.path.join(job_dir, f"debug_musiclang_{seg_type}.txt")
            with open(debug_path, "w") as f:
                f.write(str(score))
            print(f"[score_builder] Wrote debug file: debug_musiclang_{seg_type}.txt")
            score.to_midi(midi_path)
            print(f"[score_builder] {seg_type} -> {midi_path} (MusicLang)")

        midi_paths[seg_type] = midi_path

    return midi_paths
