import mido


def run_midi_merger_stage(
    mapped_midis: dict[str, str], output_path: str
) -> str:
    """Merge per-type mapped MIDIs into a single Type 1 multi-track MIDI.

    Returns the output file path.
    """
    combined = mido.MidiFile(type=1)
    ticks = None
    tempo_track_added = False

    for seg_type, path in mapped_midis.items():
        mid = mido.MidiFile(path)
        if ticks is None:
            combined.ticks_per_beat = mid.ticks_per_beat
            ticks = mid.ticks_per_beat

        for track in mid.tracks:
            new_track = mido.MidiTrack()
            new_track.append(
                mido.MetaMessage("track_name", name=seg_type, time=0)
            )

            for msg in track:
                # Deduplicate tempo/time_signature meta events
                if msg.is_meta and msg.type in ("set_tempo", "time_signature"):
                    if not tempo_track_added:
                        new_track.append(msg)
                    continue
                if msg.is_meta and msg.type == "track_name":
                    continue
                new_track.append(msg)

            combined.tracks.append(new_track)
            tempo_track_added = True

    combined.save(output_path)
    print(f"[midi_merger] Merged {len(mapped_midis)} tracks -> {output_path}")
    return output_path
