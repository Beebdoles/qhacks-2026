import json
import tempfile

import mido
from google import genai
from google.genai import types
from musiclang.write.score import Score
from musiclang.write.library import (
    s0, s1, s2, s3, s4, s5, s6,
    I, II, III, IV, V, VI, VII,
    r,
)

# ── MusicLang lookup tables ──────────────────────────────────────────

DEGREE_MAP = {1: I, 2: II, 3: III, 4: IV, 5: V, 6: VI, 7: VII}

SCALE_NOTE_MAP = {0: s0, 1: s1, 2: s2, 3: s3, 4: s4, 5: s5, 6: s6}

DURATION_MAP = {
    "w": "w",   # whole
    "h": "h",   # half
    "q": "q",   # quarter
    "e": "e",   # eighth
    "s": "s",   # sixteenth
}

QUALITY_MAP = {
    "M": "M",
    "m": "m",
}

# ── Builder helpers ──────────────────────────────────────────────────

def build_note(data):
    """Convert {"s": 0, "octave": 1, "duration": "q"} → MusicLang Note."""
    degree = data.get("s", 0)
    degree = max(0, min(6, int(degree)))
    note = SCALE_NOTE_MAP.get(degree, s0)

    octave = int(data.get("octave", 0))
    if octave != 0:
        note = note.o(octave)

    dur_code = str(data.get("duration", "q"))
    dur_attr = DURATION_MAP.get(dur_code, "q")
    note = getattr(note, dur_attr)

    return note


def build_melody(notes_list):
    """Concatenate a list of note dicts into a MusicLang melody (Note + Note + ...)."""
    if not notes_list:
        return r.q  # fallback: quarter rest
    melody = build_note(notes_list[0])
    for n in notes_list[1:]:
        melody = melody + build_note(n)
    return melody


def build_chord(chord_data, tonality_obj):
    """Build a single MusicLang chord expression with instrument melodies.

    chord_data: {"degree": 1, "duration_beats": 4, "instruments": {"piano": [...]}}
    tonality_obj: e.g.  I.M
    """
    deg = int(chord_data.get("degree", 1))
    deg = max(1, min(7, deg))
    chord_degree = DEGREE_MAP.get(deg, I)

    chord_expr = chord_degree % tonality_obj

    instruments = chord_data.get("instruments", {})
    if not instruments:
        # No instruments specified → single quarter rest on piano
        return chord_expr(piano=r.q)

    kwargs = {}
    for inst_name, notes_list in instruments.items():
        inst_name = str(inst_name).strip().lower()
        if not notes_list:
            continue
        melody = build_melody(notes_list)
        kwargs[inst_name] = melody

    if not kwargs:
        return chord_expr(piano=r.q)

    return chord_expr(**kwargs)


def build_tonality(tonality_data):
    """Convert {"degree": 1, "quality": "M"} → MusicLang Tonality object (e.g. I.M)."""
    deg = int(tonality_data.get("degree", 1))
    deg = max(1, min(7, deg))
    quality = str(tonality_data.get("quality", "M"))
    quality = QUALITY_MAP.get(quality, "M")

    base = DEGREE_MAP.get(deg, I)
    return getattr(base, quality)


def build_scores_by_type(gemini_json):
    """Group segments by type and build a separate MusicLang Score per type.

    Returns dict: {"beatboxing": (Score, tempo, time_sig), "singing": (...), ...}
    """
    tempo = int(gemini_json.get("tempo_bpm", 120))
    ts = gemini_json.get("time_signature", [4, 4])
    if isinstance(ts, list) and len(ts) == 2:
        time_sig = (int(ts[0]), int(ts[1]))
    else:
        time_sig = (4, 4)

    tonality_data = gemini_json.get("tonality", {"degree": 1, "quality": "M"})
    tonality_obj = build_tonality(tonality_data)

    # Group chords by segment type
    chords_by_type = {}
    for segment in gemini_json.get("segments", []):
        seg_type = segment.get("type", "")
        if seg_type in ("silence", "speech"):
            continue
        for chord_data in segment.get("chords", []):
            chords_by_type.setdefault(seg_type, []).append(
                build_chord(chord_data, tonality_obj)
            )

    # Build one Score per type
    scores = {}
    for seg_type, chord_list in chords_by_type.items():
        if not chord_list:
            chord_list = [(I % tonality_obj)(piano=r.w)]
        scores[seg_type] = (
            Score(chord_list, tempo=tempo, time_signature=time_sig),
            tempo,
            time_sig,
        )

    return scores


# Channel + program assignments per segment type.
# beatboxing → MIDI channel 9 (General MIDI drums)
# singing    → channel 1, instrument chosen by Gemini (piano=0 or flute=73)
# fallback   → channel 2, program 48 (string ensemble)
SINGING_PROGRAMS = {"piano": 0, "flute": 73}

TRACK_INSTRUMENTS = {
    "beatboxing": {"channel": 9, "program": 0, "is_drum": True},
    "singing":    {"channel": 1, "program": 73},
    "humming":    {"channel": 1, "program": 73},
}
_next_fallback_channel = 2


def _get_instrument(seg_type):
    """Return (channel, program, is_drum) for a segment type."""
    global _next_fallback_channel
    if seg_type in TRACK_INSTRUMENTS:
        cfg = TRACK_INSTRUMENTS[seg_type]
        return cfg["channel"], cfg.get("program", 0), cfg.get("is_drum", False)
    # Assign a fresh channel for unknown types
    ch = _next_fallback_channel
    _next_fallback_channel = min(_next_fallback_channel + 1, 15)
    if ch == 9:  # skip drum channel
        ch = _next_fallback_channel
        _next_fallback_channel += 1
    return ch, 48, False


def merge_midis(midi_files, output_path):
    """Merge per-type MIDI files into one multi-track MIDI (type 1).

    Each segment type gets its own MIDI channel and instrument program,
    so tracks are audibly distinct when played.

    midi_files: {"beatboxing": "path.mid", "singing": "path.mid", ...}
    """
    combined = mido.MidiFile(type=1)
    ticks = None
    tempo_track_added = False

    for seg_type, path in midi_files.items():
        mid = mido.MidiFile(path)
        if ticks is None:
            combined.ticks_per_beat = mid.ticks_per_beat
            ticks = mid.ticks_per_beat

        channel, program, is_drum = _get_instrument(seg_type)

        for track in mid.tracks:
            new_track = mido.MidiTrack()
            new_track.append(mido.MetaMessage("track_name", name=seg_type, time=0))
            # Set instrument for this track
            new_track.append(mido.Message("program_change", channel=channel, program=program, time=0))

            for msg in track:
                if msg.is_meta and msg.type in ("set_tempo", "time_signature"):
                    if not tempo_track_added:
                        new_track.append(msg)
                    continue
                if msg.is_meta and msg.type == "track_name":
                    continue
                # Remap channel on all channel messages (note_on, note_off, etc.)
                if hasattr(msg, "channel") and not msg.is_meta:
                    msg = msg.copy(channel=channel)
                    # Skip existing program_change from MusicLang
                    if msg.type == "program_change":
                        continue
                new_track.append(msg)

            combined.tracks.append(new_track)
            tempo_track_added = True

    combined.save(output_path)


# ── Gemini prompt ────────────────────────────────────────────────────

GEMINI_PROMPT = """Analyze the attached audio file along with the time segment descriptions below, and produce a structured JSON description of a melody/rhythm that could be generated from it.

The output must be compatible with the MusicLang library, which uses:
- Scale degrees 0-6 (not note names) for melody notes
- Chord degrees 1-7 with quality "M" (major) or "m" (minor)
- Duration codes: "w" (whole), "h" (half), "q" (quarter), "e" (eighth), "s" (sixteenth)
- Instrument names: piano, violin, flute, cello, acoustic_guitar, etc.
- A top-level tonality field (degree 1-7 + quality "M"/"m")

Time segments:
{timeframes}

Return ONLY valid JSON with this exact structure:
{{
  "tempo_bpm": <integer>,
  "time_signature": [<beats_per_bar>, <beat_unit>],
  "tonality": {{"degree": <1-7>, "quality": "<M or m>"}},
  "segments": [
    {{
      "start": <float>,
      "end": <float>,
      "type": "<original segment type>",
      "chords": [
        {{
          "degree": <1-7>,
          "duration_beats": <number>,
          "instruments": {{
            "<instrument_name>": [
              {{"s": <0-6>, "octave": <int>, "duration": "<w|h|q|e|s>"}},
              ...
            ]
          }}
        }}
      ]
    }}
  ]
}}

Guidelines:
- For "beatboxing" segments, use percussive drum patterns with short durations (e/s) on piano in low octaves (-1, -2). These will become a percussion/drum track.
- For "singing" or "humming" segments, create melodic lines with longer notes (q/h). These will become the melody track.
  - You MUST also include a top-level "singing_instrument" field set to either "piano" or "flute" — pick whichever best matches the character of the singing (breathy/airy → flute, rhythmic/chordal → piano).
- SKIP "speech" and "silence" segments entirely — do not include them in the output.
- Each chord's total note durations should roughly match duration_beats in quarter notes
- Use octave 0 as the default, -1 for bass, 1 for higher register
- IMPORTANT: Each segment type will be exported as a separate MIDI file so they can be layered together. Design each type to sound good independently and when combined.
"""


# ── Main ─────────────────────────────────────────────────────────────

def main():
    client = genai.Client()

    audio_test = client.files.upload(file="Recording.mp3")
    timeframes = """{
    "segments": [
      {"start": 0.0, "end": 2.1, "type": "speech"},
      {"start": 2.1, "end": 3.2, "type": "silence"},
      {"start": 3.2, "end": 6.8, "type": "beatboxing"},
      {"start": 6.8, "end": 8.1, "type": "silence"},
      {"start": 8.1, "end": 10.3, "type": "singing"},
      {"start": 10.3, "end": 11.2, "type": "silence"},
      {"start": 11.2, "end": 14.12, "type": "speech"}
    ]
  }"""

    prompt = GEMINI_PROMPT.format(timeframes=timeframes)

    print("Sending audio to Gemini...")
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[audio_test, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    gemini_result = json.loads(response.text)
    print("Gemini response:")
    print(json.dumps(gemini_result, indent=2))

    # Apply Gemini's instrument choice for singing/humming
    singing_inst = gemini_result.get("singing_instrument", "piano")
    program = SINGING_PROGRAMS.get(singing_inst, 73)
    TRACK_INSTRUMENTS["singing"] = {"channel": 1, "program": program}
    TRACK_INSTRUMENTS["humming"] = {"channel": 1, "program": program}
    print(f"\nSinging instrument: {singing_inst} (program {program})")

    # Build one MusicLang score per segment type
    print("Building MusicLang scores by segment type...")
    scores = build_scores_by_type(gemini_result)

    # Export each type to its own file + collect for merging
    midi_files = {}
    for seg_type, (score, tempo, time_sig) in scores.items():
        filename = f"output_{seg_type}.mid"
        score.to_midi(filename)
        midi_files[seg_type] = filename
        print(f"  {seg_type} → {filename}  (tempo={tempo}, time_sig={time_sig[0]}/{time_sig[1]})")

    # Merge all types into one multi-track MIDI
    combined_path = "output.mid"
    merge_midis(midi_files, combined_path)
    print(f"\nCombined multi-track MIDI → {combined_path}")
    print(f"Individual tracks: {', '.join(midi_files.values())}")


if __name__ == "__main__":
    main()
