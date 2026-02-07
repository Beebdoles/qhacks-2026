import json
import os

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
