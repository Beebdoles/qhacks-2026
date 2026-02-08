import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

VALID_ROOTS = r"[A-G][#b]?"
VALID_QUALITIES = r"(?:M7|M|m7b5|m7|m|7|sus2|sus4|dim0|dim)"
VALID_CHORD_RE = re.compile(rf"^{VALID_ROOTS}{VALID_QUALITIES}(?:/{VALID_ROOTS})?$")


def _validate_chord_progression(chord_str: str) -> bool:
    """Return True if every chord in the space-separated string is valid MusicLang format."""
    return all(VALID_CHORD_RE.match(c) for c in chord_str.split())


# ---------------------------------------------------------------------------
# Generation prompt: NL description → structured generation parameters
# ---------------------------------------------------------------------------

GENERATION_SYSTEM_PROMPT = """You are a music production assistant. Given a natural language description of music to generate, output a JSON object with generation parameters.

Output format:
{
    "chord_progression": "<chord string or null>",
    "tempo": <int 40-300>,
    "temperature": <float 0.1-1.0>,
    "time_signature": [<numerator>, <denominator>],
    "nb_tokens": <int 256-4096>,
    "explanation": "<brief explanation>"
}

Rules:
- chord_progression: Use MusicLang chord format. ONE CHORD PER BAR. The number of chords
  determines the song length! Each bar lasts (time_signature_numerator / tempo * 60) seconds.
  To calculate how many chords you need: num_chords = desired_seconds / (numerator / tempo * 60)
  Example: 30 seconds at 150 BPM in 4/4 = 30 / (4/150*60) = 30 / 1.6 = ~19 chords.
  IMPORTANT: If the user requests a specific duration, output ENOUGH chords to fill that duration.
  Repeat or vary the progression as needed to reach the target number of chords.
  Each chord MUST be: <root><quality> where root is one of: C, D, E, F, G, A, B (with optional # or b)
  and quality is EXACTLY one of: M, m, 7, m7b5, sus2, sus4, m7, M7, dim, dim0
  Examples of VALID chords: Am, CM, Dm, E7, FM, GM, Bm, Am7, CM7, Dm7, G7, Adim, Em7b5
  Examples of INVALID chords: Amin, Cmaj, Dmin7, Gsus, A5, Caug, Cm6 (DO NOT use these)
  Bass notation: e.g. "Bm/D". Examples: "Am CM Dm E7", "CM FM GM CM"
  Use null if the user does not specify a key or mood (free generation).
- tempo: "slow" -> 70, "moderate" -> 110, "fast" -> 150, "upbeat" -> 140
- temperature: "creative"/"experimental" -> 0.95, normal -> 0.9, "structured" -> 0.5
- time_signature: Default [4, 4]. "waltz" -> [3, 4], "6/8" -> [6, 8]
- nb_tokens: Controls output length. Duration mapping (approximate):
  ~5 seconds -> 512, ~15 seconds -> 1024, ~30 seconds -> 2048, ~60 seconds -> 4096
  If the user specifies a duration in seconds, pick the closest nb_tokens value.
  "short" -> 512, default -> 1024, "long" -> 2048

Mood-to-chord mappings:
- "sad"/"melancholic" -> minor keys: "Am Dm Em Am"
- "happy"/"upbeat" -> major keys: "CM FM GM CM"
- "jazzy" -> 7th chords: "CM7 Am7 Dm7 G7"
- "dark"/"ominous" -> "Am Dm E7 Am" with slower tempo
- "peaceful"/"calm" -> "CM Am FM GM" with slow tempo
- "energetic" -> major keys, fast tempo, higher temperature

Output ONLY valid JSON. No markdown fences, no extra text."""


# ---------------------------------------------------------------------------
# Backtrack style prompt: style description → instrument list
# ---------------------------------------------------------------------------

BACKTRACK_STYLE_PROMPT = """You are a music production assistant. Given a musical style description, output a JSON object specifying which instruments should be in the backing track.

Output format:
{
    "instruments": ["instrument1", "instrument2", ...],
    "explanation": "..."
}

Valid instrument names (use these exactly):
piano, acoustic_guitar, jazz_guitar, clean_guitar, electric_bass_finger, acoustic_bass,
fretless_bass, violin, viola, cello, contrabass, string_ensemble_1, flute, clarinet,
oboe, trumpet, trombone, french_horn, alto_sax, tenor_sax, drums_0, vibraphone,
drawbar_organ, harmonica, harp

Style-to-instrument mappings:
- "rock" -> ["distortion_guitar", "electric_bass_pick", "drums_0", "piano"]
- "jazz" -> ["piano", "acoustic_bass", "drums_0", "tenor_sax"]
- "pop" -> ["piano", "acoustic_guitar", "electric_bass_finger", "drums_0"]
- "classical" -> ["violin", "viola", "cello", "contrabass", "flute"]
- "funk" -> ["clean_guitar", "electric_bass_finger", "drums_0", "piano"]
- "orchestral" -> ["violin", "viola", "cello", "contrabass", "flute", "oboe", "french_horn"]
- "acoustic" -> ["acoustic_guitar", "acoustic_bass", "piano"]
- "electronic" -> ["synth_bass_1", "pad_polysynth", "square_lead", "drums_0"]

Choose 3-5 instruments that best match the style. Always include a bass instrument and a rhythmic element.

Output ONLY valid JSON. No markdown fences, no extra text."""

HARDCODED_BACKTRACK_RESPONSE = {
    "instruments": ["piano", "acoustic_bass", "drums_0"],
    "explanation": "Hardcoded default backing band for testing",
}


# ---------------------------------------------------------------------------
# Edit prompt (existing): NL edit instruction → structured edit action
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a music production assistant. Given an analysis of a MIDI file and a user's editing instruction, output a JSON object specifying how to modify the music.

The MIDI analysis includes:
- instruments: list of instruments in the piece
- duration: total duration

You can output ONE of these actions:

1. {"action": "regenerate_with_chords", "chord_progression": "<new chords>", "explanation": "..."}
   Use when the user wants to change harmony, key, or mood.
   Supported chord qualities: M (major), m (minor), 7, m7b5, sus2, sus4, m7, M7, dim, dim0
   Bass notation supported: e.g. "Bm/D"
   One chord per bar. Example: "Am CM Dm E7 Am"

2. {"action": "extend", "explanation": "..."}
   Use when the user wants to make the piece longer.

3. {"action": "change_tempo", "tempo": <int>, "explanation": "..."}
   Use when the user wants to change speed only.
   Typical ranges: 60-80 slow, 100-120 moderate, 140-180 fast.

4. {"action": "regenerate_with_chords_and_tempo", "chord_progression": "<new chords>", "tempo": <int>, "explanation": "..."}
   Use when changing both harmony/mood AND tempo.

5. {"action": "adjust_temperature", "temperature": <float 0.1-1.0>, "explanation": "..."}
   Use when user wants more predictable (low ~0.3) or more creative/chaotic (high ~0.95) output.

Mapping guidelines:
- "more upbeat" / "happier" -> major chords (CM, FM, GM) + faster tempo
- "sadder" / "melancholic" -> minor chords (Am, Dm, Em) + slower tempo
- "jazzy" -> 7th chords (CM7, Am7, Dm7, G7)
- "darker" / "ominous" -> minor + diminished chords, slower tempo
- "simpler" -> fewer chord changes, basic triads
- "more complex" -> more chord changes, extended harmonies
- "longer" / "extend" -> extend action
- "faster" / "slower" -> change_tempo action
- "more creative" / "more random" -> higher temperature
- "more structured" / "less random" -> lower temperature

Output ONLY valid JSON. No markdown fences, no extra text."""


# Set to True to bypass Gemini and use a hardcoded response for testing
USE_HARDCODED = True

HARDCODED_RESPONSE = {
    "action": "regenerate_with_chords_and_tempo",
    "chord_progression": "CM7 Am7 Dm7 G7 CM7 Am7 Dm7 G7",
    "tempo": 110,
    "explanation": "Hardcoded jazzy ii-V-I progression for testing",
}


async def interpret_edit_instruction(instruction: str, analysis: dict) -> dict:
    """Use Gemini to interpret a natural language edit instruction into a structured action plan."""
    if USE_HARDCODED:
        print(f"[HARDCODED] Ignoring instruction: '{instruction}', returning test response")
        return HARDCODED_RESPONSE

    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""{SYSTEM_PROMPT}

MIDI Analysis:
- Instruments: {', '.join(analysis.get('instruments', ['unknown']))}
- Duration: {analysis.get('duration', 'unknown')}

User instruction: "{instruction}"

Output the JSON action:"""

    response = await model.generate_content_async(prompt)
    text = response.text.strip()

    # Handle markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)


async def interpret_generation_prompt(prompt: str) -> dict:
    """Use Gemini to interpret a NL generation description into structured params."""
    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel("gemini-2.0-flash")

    full_prompt = f"""{GENERATION_SYSTEM_PROMPT}

User description: "{prompt}"

Output the JSON parameters:"""

    for attempt in range(3):
        response = await model.generate_content_async(full_prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        chords = result.get("chord_progression")
        if chords is None or _validate_chord_progression(chords):
            return result
        print(f"[LLM] Invalid chords on attempt {attempt + 1}: {chords}, retrying...")

    # Final fallback: use the result but strip the invalid chords
    result["chord_progression"] = None
    return result


async def interpret_backtrack_style(style: str) -> dict:
    """Use Gemini to interpret a style description into a list of backing instruments."""
    if USE_HARDCODED:
        print(f"[HARDCODED] Ignoring style: '{style}', returning test response")
        return HARDCODED_BACKTRACK_RESPONSE

    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel("gemini-2.0-flash")

    full_prompt = f"""{BACKTRACK_STYLE_PROMPT}

Style description: "{style}"

Output the JSON:"""

    response = await model.generate_content_async(full_prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Arrangement prompt: MIDI analysis → arrangement parameters
# ---------------------------------------------------------------------------

ARRANGEMENT_SYSTEM_PROMPT = """You are a music arrangement assistant. Given a detailed analysis of a MIDI file, suggest how to arrange accompaniment that supports and enhances the existing melody/track.

Input analysis includes:
- chord_progression: absolute chord names (e.g. "CM FM GM CM")
- roman_numerals: functional harmony (e.g. ["I", "IV", "V", "I"])
- key: detected key (e.g. "C" for C major, "a" for A minor)
- tempo: detected BPM
- time_signature: e.g. [4, 4]
- instruments: existing instruments in the track
- complexity: "simple", "moderate", or "complex"
- densities, mean_octaves, mean_amplitudes: per-instrument statistics

Output format:
{
    "accompaniment_instruments": ["instrument1", "instrument2", ...],
    "chord_progression": "<enriched chord progression or null to keep original>",
    "tempo": <int BPM or null to keep detected>,
    "style": "<brief style/character description>",
    "explanation": "<reasoning for choices>"
}

Rules for accompaniment_instruments (pick 3-5):
- Always include a bass instrument (acoustic_bass, electric_bass_finger, etc.)
- Always include a harmonic/chordal instrument (piano, acoustic_guitar, etc.)
- Consider adding rhythm (drums_0) unless the piece is very delicate
- NEVER duplicate instruments already in the input track
- Match the style implied by the key, tempo, and chord progression

Valid instrument names:
piano, acoustic_guitar, jazz_guitar, clean_guitar, electric_bass_finger, acoustic_bass,
fretless_bass, violin, viola, cello, contrabass, string_ensemble_1, flute, clarinet,
oboe, trumpet, trombone, french_horn, alto_sax, tenor_sax, drums_0, vibraphone,
drawbar_organ, harmonica, harp, synth_bass_1, pad_polysynth

Style inference guidelines:
- Simple major key, moderate tempo → pop/folk: piano, acoustic_guitar, acoustic_bass, drums_0
- Minor key, slow → ballad/cinematic: piano, string_ensemble_1, cello, acoustic_bass
- Complex chords (7ths, extensions) → jazz: piano, acoustic_bass, drums_0, tenor_sax
- Fast tempo, major → upbeat/rock: clean_guitar, electric_bass_finger, drums_0, piano
- Very simple (nursery rhyme) → light: piano, acoustic_guitar, acoustic_bass

For chord_progression enrichment:
- If the original is very simple (e.g. only I-IV-V), you may suggest adding passing chords or 7th extensions
- If already rich, return null to keep the original
- Must use MusicLang format: CM, Am, G7, Dm7, etc. One chord per bar.

Output ONLY valid JSON. No markdown fences, no extra text."""

HARDCODED_ARRANGEMENT_RESPONSE = {
    "accompaniment_instruments": ["piano", "acoustic_bass", "drums_0", "string_ensemble_1"],
    "chord_progression": None,
    "tempo": None,
    "style": "Light pop arrangement with piano, bass, drums, and strings",
    "explanation": "Hardcoded default arrangement for testing",
}


async def interpret_arrangement(analysis: dict) -> dict:
    """Use Gemini to interpret MIDI analysis into arrangement parameters."""
    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel("gemini-2.0-flash")

    full_prompt = f"""{ARRANGEMENT_SYSTEM_PROMPT}

MIDI Analysis:
- Key: {analysis.get('key', 'unknown')}
- Chord progression: {analysis.get('chord_progression', 'unknown')}
- Roman numerals: {analysis.get('roman_numerals', [])}
- Tempo: {analysis.get('tempo', 120)} BPM
- Time signature: {analysis.get('time_signature', [4, 4])}
- Instruments: {', '.join(analysis.get('instruments', ['unknown']))}
- Complexity: {analysis.get('complexity', 'moderate')}
- Duration: {analysis.get('duration_seconds', 'unknown')} seconds ({analysis.get('num_chords', 'unknown')} chords)
- Densities: {analysis.get('densities', {})}
- Mean octaves: {analysis.get('mean_octaves', {})}
- Mean amplitudes: {analysis.get('mean_amplitudes', {})}

Output the JSON arrangement parameters:"""

    response = await model.generate_content_async(full_prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)
