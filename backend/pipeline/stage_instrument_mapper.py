import mido

from models import SingingInstrument

SINGING_PROGRAMS = {"piano": 0, "flute": 73}

BASE_TRACK_INSTRUMENTS = {
    "beatboxing": {"channel": 9, "program": 0, "is_drum": True},
    "singing": {"channel": 1, "program": 73},
    "humming": {"channel": 1, "program": 73},
}


def run_instrument_mapper_stage(
    per_type_midis: dict[str, str],
    singing_instrument: SingingInstrument,
    job_dir: str,
) -> dict[str, str]:
    """Remap MIDI channels/instruments per segment type.

    Returns {seg_type: mapped_midi_path}.
    """
    # Build per-invocation instrument map (thread-safe, no globals)
    track_instruments = dict(BASE_TRACK_INSTRUMENTS)

    # Apply Gemini's singing instrument choice
    program = SINGING_PROGRAMS.get(singing_instrument.value, 73)
    track_instruments["singing"] = {"channel": 1, "program": program}
    track_instruments["humming"] = {"channel": 1, "program": program}

    # Thread-safe fallback state
    fallback_state = {"next_channel": 2}

    def get_instrument(seg_type: str):
        if seg_type in track_instruments:
            cfg = track_instruments[seg_type]
            return cfg["channel"], cfg.get("program", 0), cfg.get("is_drum", False)
        ch = fallback_state["next_channel"]
        fallback_state["next_channel"] = min(ch + 1, 15)
        if ch == 9:
            ch = fallback_state["next_channel"]
            fallback_state["next_channel"] += 1
        return ch, 48, False

    mapped: dict[str, str] = {}
    for seg_type, path in per_type_midis.items():
        mid = mido.MidiFile(path)
        channel, program, _is_drum = get_instrument(seg_type)

        for track in mid.tracks:
            remapped = mido.MidiTrack()
            remapped.append(
                mido.Message("program_change", channel=channel, program=program, time=0)
            )
            for msg in track:
                if hasattr(msg, "channel") and not msg.is_meta:
                    msg = msg.copy(channel=channel)
                    if msg.type == "program_change":
                        continue
                remapped.append(msg)
            track[:] = remapped

        mapped_path = path.replace(".mid", "_mapped.mid")
        mid.save(mapped_path)
        mapped[seg_type] = mapped_path
        print(f"[instrument_mapper] {seg_type} -> ch{channel} prog{program} -> {mapped_path}")

    return mapped
