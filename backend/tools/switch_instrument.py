# switch_instrument — Change the instrument of a previously created track.
import os
import tempfile
import pretty_midi

from intent.schema import ToolCall

# Canonical instrument name → General MIDI program number.
# Names here match the canonical forms produced by normalize.py's INSTRUMENT_ALIASES.
INSTRUMENT_PROGRAMS: dict[str, int] = {
    # Piano family
    "piano": 0,
    "acoustic_grand_piano": 0,
    "bright_acoustic_piano": 1,
    "electric_grand_piano": 2,
    "honky_tonk_piano": 3,
    "electric_piano": 4,
    "harpsichord": 6,
    # Organ
    "drawbar_organ": 16,
    "rock_organ": 18,
    "church_organ": 19,
    # Guitar
    "acoustic_guitar": 25,
    "acoustic_guitar_nylon": 24,
    "acoustic_guitar_steel": 25,
    "clean_guitar": 27,
    "electric_guitar": 27,
    "overdriven_guitar": 29,
    "distortion_guitar": 30,
    # Bass
    "acoustic_bass": 32,
    "electric_bass_finger": 33,
    "electric_bass_pick": 34,
    "slap_bass": 36,
    "synth_bass_1": 38,
    "synth_bass_2": 39,
    # Strings
    "violin": 40,
    "viola": 41,
    "cello": 42,
    "contrabass": 43,
    "string_ensemble_1": 48,
    "string_ensemble_2": 49,
    "synth_strings": 50,
    "harp": 46,
    # Ensemble / choir
    "choir": 52,
    # Brass
    "trumpet": 56,
    "trombone": 57,
    "tuba": 58,
    "french_horn": 60,
    "brass_section": 61,
    # Reed / woodwind
    "soprano_sax": 64,
    "alto_sax": 65,
    "tenor_sax": 66,
    "baritone_sax": 67,
    "oboe": 68,
    "clarinet": 71,
    "piccolo": 72,
    "flute": 73,
    "recorder": 74,
    # Pipe
    "pan_flute": 75,
    # Synth lead
    "synth_lead": 80,
    "synth_pad": 88,
    # Ethnic / misc
    "sitar": 104,
    "banjo": 105,
    "steel_drums": 114,
    # Harmonica / accordion
    "harmonica": 22,
    "accordion": 21,
    # Percussive
    "music_box": 10,
    "xylophone": 13,
    "marimba": 12,
    "vibraphone": 11,
    "tubular_bells": 14,
    # Special — drums / percussion (channel 9)
    "drums": -1,
    "drums_0": -1,
    "drum": -1,
    "percussion": -1,
    # Drum-specific sounds (channel 9, notes remapped via DRUM_NOTE_MAP)
    "kick": -1,
    "kick_drum": -1,
    "bass_drum": -1,
    "snare": -1,
    "snare_drum": -1,
    "hi_hat": -1,
    "closed_hi_hat": -1,
    "open_hi_hat": -1,
    "crash": -1,
    "ride": -1,
    "floor_tom": -1,
    "high_tom": -1,
}

# Drum instrument name → GM percussion note number.
# When switching to one of these, all notes are remapped to the target pitch.
DRUM_NOTE_MAP: dict[str, int] = {
    "kick": 36,
    "kick_drum": 36,
    "bass_drum": 36,
    "snare": 38,
    "snare_drum": 38,
    "hi_hat": 42,
    "closed_hi_hat": 42,
    "open_hi_hat": 46,
    "crash": 49,
    "ride": 51,
    "floor_tom": 41,
    "high_tom": 48,
}


def _find_tracks(midi: pretty_midi.PrettyMIDI, description: str) -> list[pretty_midi.Instrument]:
    """Fuzzy-match a target_description against instrument/track names.

    Unlike pitch_shift/progression_change, switch_instrument needs to match
    ALL instruments (including drums) since we may switch to or from drums.
    """
    all_instruments = list(midi.instruments)

    if not description:
        return all_instruments

    desc_lower = description.strip().lower()
    matched = []
    for inst in midi.instruments:
        name = (inst.name or "").strip().lower()
        if name and (name in desc_lower or desc_lower in name):
            matched.append(inst)

    return matched if matched else all_instruments


def _resolve_program(instrument: str) -> tuple[int, bool]:
    """Resolve an instrument name to (program_number, is_drum).

    Returns (-1, True) for drums. Tries exact match first, then substring.
    """
    name = instrument.strip().lower()

    # Exact match
    if name in INSTRUMENT_PROGRAMS:
        prog = INSTRUMENT_PROGRAMS[name]
        if prog == -1:
            return -1, True
        return prog, False

    # Substring match: find first key that contains the name or vice versa
    for key, prog in INSTRUMENT_PROGRAMS.items():
        if name in key or key in name:
            if prog == -1:
                return -1, True
            return prog, False

    raise ValueError(
        f"Unknown instrument: {instrument!r}. "
        f"Known instruments: {', '.join(sorted(INSTRUMENT_PROGRAMS.keys()))}"
    )


def run_switch_instrument(tool_call: ToolCall, midi_path: str) -> str:
    """Change the instrument of tracks in a MIDI file.

    Reads tool_call.params for:
        instrument (str): Target instrument name (already normalized).
        target_description (str, optional): Which track to change.

    Modifies the MIDI file in-place (atomic write) and returns a summary string.
    """
    tag = "[switch_instrument]"

    if not os.path.isfile(midi_path):
        raise FileNotFoundError(f"No MIDI found at {midi_path}")

    instrument = tool_call.params.get("instrument", "")
    target = tool_call.params.get("target_description", "")

    if not instrument:
        raise ValueError("No instrument name provided in 'instrument' param.")

    program, is_drum = _resolve_program(instrument)

    midi = pretty_midi.PrettyMIDI(midi_path)

    matched = _find_tracks(midi, target)
    if not matched:
        available = [inst.name for inst in midi.instruments if inst.name]
        raise ValueError(f"No tracks matching {target!r}. Available: {available}")

    for inst in matched:
        if is_drum:
            inst.is_drum = True
            inst.name = instrument
            # Specific drum type → remap all notes to that GM percussion note
            drum_note = DRUM_NOTE_MAP.get(instrument.strip().lower())
            if drum_note is not None:
                for note in inst.notes:
                    note.pitch = drum_note
        else:
            inst.is_drum = False
            inst.program = program
            inst.name = instrument

    # Atomic write
    dir_name = os.path.dirname(midi_path)
    fd, tmp_path = tempfile.mkstemp(suffix=".mid", dir=dir_name)
    os.close(fd)
    try:
        midi.write(tmp_path)
        os.replace(tmp_path, midi_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    if is_drum:
        drum_note = DRUM_NOTE_MAP.get(instrument.strip().lower())
        if drum_note is not None:
            summary = f"Changed {len(matched)} track(s) to {instrument} (drum note {drum_note})."
        else:
            summary = f"Changed {len(matched)} track(s) to drums."
    else:
        summary = f"Changed {len(matched)} track(s) to {instrument} (program {program})."

    print(f"{tag} {summary}")
    return summary
