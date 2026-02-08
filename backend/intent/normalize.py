from __future__ import annotations

from intent.schema import ToolName

# Aliases from chloe-dev music_service.py
INSTRUMENT_ALIASES: dict[str, str] = {
    "guitar": "acoustic_guitar",
    "bass": "acoustic_bass",
    "electric_guitar": "clean_guitar",
    "drums": "drums_0",
    "drum": "drums_0",
    "sax": "tenor_sax",
    "saxophone": "tenor_sax",
    "strings": "string_ensemble_1",
    "organ": "drawbar_organ",
    "electric_bass": "electric_bass_finger",
    "synth": "synth_bass_1",
}


def normalize_params(tool: ToolName, params: dict) -> dict:
    """Normalize LLM-produced params into canonical form per tool.

    Returns a new dict with normalized values, or the original if no tool-specific
    normalization applies.
    """
    if tool == ToolName.pitch_shift:
        return _normalize_pitch_shift(params)
    if tool == ToolName.repeat_track:
        return _normalize_repeat_track(params)
    if tool == ToolName.switch_instrument:
        return _normalize_switch_instrument(params)
    if tool == ToolName.mp3_to_midi:
        return _normalize_mp3_to_midi(params)
    if tool == ToolName.progression_change:
        return _normalize_progression_change(params)
    return params


def _normalize_pitch_shift(params: dict) -> dict:
    """Normalize pitch shift params to {semitones: int}."""
    result = dict(params)

    # Accept "octave_up" / "octave_down" shorthands
    if result.pop("octave_up", None):
        result["semitones"] = 12
    elif result.pop("octave_down", None):
        result["semitones"] = -12

    # Accept "up" as alias for semitones
    if "up" in result and "semitones" not in result:
        result["semitones"] = result.pop("up")
    elif "down" in result and "semitones" not in result:
        val = result.pop("down")
        result["semitones"] = -_to_int(val) if val else 0

    # Ensure int
    if "semitones" in result:
        result["semitones"] = _to_int(result["semitones"])

    return result


def _normalize_repeat_track(params: dict) -> dict:
    """Normalize repeat params to {times: int}."""
    result = dict(params)

    # Accept "repeat" as alias for "times"
    if "repeat" in result and "times" not in result:
        result["times"] = result.pop("repeat")
    elif "count" in result and "times" not in result:
        result["times"] = result.pop("count")

    if "times" in result:
        result["times"] = _to_int(result["times"])

    return result


def _normalize_switch_instrument(params: dict) -> dict:
    """Normalize instrument name via aliases."""
    result = dict(params)
    if "instrument" in result:
        name = str(result["instrument"]).strip().lower()
        result["instrument"] = INSTRUMENT_ALIASES.get(name, name)
    return result


def _normalize_mp3_to_midi(params: dict) -> dict:
    """Normalize mp3_to_midi params — mainly instrument alias resolution."""
    result = dict(params)
    if "instrument" in result:
        name = str(result["instrument"]).strip().lower()
        result["instrument"] = INSTRUMENT_ALIASES.get(name, name)
    return result


def _normalize_progression_change(params: dict) -> dict:
    """Normalize progression param.

    Keeps scale names like "A minor" or "F# major" as strings.
    Converts numeric chord degree sequences like "1-4-5" to int lists.
    """
    result = dict(params)
    prog = result.get("progression")
    if isinstance(prog, str):
        parts = prog.replace("-", " ").replace(",", " ").split()
        # If all parts are numeric, treat as chord degree list
        if all(p.isdigit() for p in parts if p.strip()):
            result["progression"] = [_to_int(p) for p in parts if p.strip()]
        # Otherwise keep as-is (scale name like "A minor", "D major")
    elif isinstance(prog, list):
        result["progression"] = [_to_int(p) for p in prog]
    return result


def validate_required_params(tool: ToolName, params: dict) -> str | None:
    """Check that required params are present for the tool.

    Returns an error message if validation fails, None if OK.
    """
    if tool == ToolName.switch_instrument:
        if "instrument" not in params:
            return "switch_instrument requires 'instrument' param"
    elif tool == ToolName.pitch_shift:
        if "semitones" not in params:
            return "pitch_shift requires 'semitones' param"
    elif tool == ToolName.repeat_track:
        if "times" not in params:
            return "repeat_track requires 'times' param"
    return None


def _to_int(val) -> int:
    """Coerce a value to int, handling strings."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
