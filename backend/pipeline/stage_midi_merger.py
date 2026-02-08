import pretty_midi

from models import SegmentMidiResult


def run_midi_merger_stage(
    midi_results: list[SegmentMidiResult], output_path: str
) -> str:
    """Merge per-segment MIDI files into a single multi-track MIDI.

    Uses pretty_midi. Time-shifts each segment's notes by its start_offset
    so they sit at the correct position in the global timeline.

    Returns the output file path.
    """
    # Filter to successful results only
    successes = [
        r for r in midi_results
        if r.midi_path is not None and r.error is None
    ]

    if not successes:
        # Write an empty MIDI to prevent frontend 404
        empty = pretty_midi.PrettyMIDI(initial_tempo=120)
        empty.write(output_path)
        print("[midi_merger] No successful segments — wrote empty MIDI")
        return output_path

    # Use first segment's tempo
    first_midi = pretty_midi.PrettyMIDI(successes[0].midi_path)
    tempos = first_midi.get_tempo_changes()
    base_tempo = tempos[1][0] if len(tempos[1]) > 0 else 120.0

    merged = pretty_midi.PrettyMIDI(initial_tempo=base_tempo)

    for result in successes:
        seg_midi = pretty_midi.PrettyMIDI(result.midi_path)
        seg_type = result.segment_type.value
        track_name = f"{seg_type}_{result.segment_index}"

        for src_inst in seg_midi.instruments:
            inst = pretty_midi.Instrument(
                program=src_inst.program,
                is_drum=src_inst.is_drum,
                name=track_name,
            )

            # Time-shift notes by segment start offset
            for note in src_inst.notes:
                shifted = pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.start + result.start_offset,
                    end=note.end + result.start_offset,
                )
                inst.notes.append(shifted)

            # Time-shift control changes
            for cc in src_inst.control_changes:
                cc.time += result.start_offset
                inst.control_changes.append(cc)

            # Time-shift pitch bends
            for pb in src_inst.pitch_bends:
                pb.time += result.start_offset
                inst.pitch_bends.append(pb)

            merged.instruments.append(inst)

    merged.write(output_path)
    print(f"[midi_merger] Merged {len(successes)} segments -> {output_path}")
    return output_path
