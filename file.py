import json

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


def build_score(gemini_json):
    """Convert the full Gemini JSON into a MusicLang Score and metadata."""
    tempo = int(gemini_json.get("tempo_bpm", 120))
    ts = gemini_json.get("time_signature", [4, 4])
    if isinstance(ts, list) and len(ts) == 2:
        time_sig = (int(ts[0]), int(ts[1]))
    else:
        time_sig = (4, 4)

    tonality_data = gemini_json.get("tonality", {"degree": 1, "quality": "M"})
    tonality_obj = build_tonality(tonality_data)

    chord_list = []
    for segment in gemini_json.get("segments", []):
        seg_type = segment.get("type", "")
        if seg_type == "silence":
            continue
        for chord_data in segment.get("chords", []):
            chord_list.append(build_chord(chord_data, tonality_obj))

    if not chord_list:
        # Fallback: single rest chord
        chord_list = [(I % tonality_obj)(piano=r.w)]

    score = Score(chord_list, tempo=tempo, time_signature=time_sig)
    return score, tempo, time_sig


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
- For "beatboxing" segments, use percussive patterns with short durations (e/s) on piano or acoustic_guitar
- For "singing" segments, create melodic lines with longer notes (q/h) on violin or flute
- For "speech" segments, use rhythmic chord stabs on piano
- Skip "silence" segments (they will be ignored)
- Each chord's total note durations should roughly match duration_beats in quarter notes
- Use octave 0 as the default, -1 for bass, 1 for higher register
"""


# ── Main ─────────────────────────────────────────────────────────────

def main():
    client = genai.Client()

    audio_test = client.files.upload(file="test_audio_beatbox.mp3")
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

    # Build MusicLang score
    print("\nBuilding MusicLang score...")
    score, tempo, time_sig = build_score(gemini_result)
    print(f"  Tempo: {tempo} BPM")
    print(f"  Time signature: {time_sig[0]}/{time_sig[1]}")

    # Export to MIDI
    output_path = "output.mid"
    score.to_midi(output_path)
    print(f"\nMIDI file written to {output_path}")


if __name__ == "__main__":
    main()
