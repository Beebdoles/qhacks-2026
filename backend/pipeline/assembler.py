import os

import pretty_midi

from models import DrumHit, NoteEvent

DRUM_MAP = {
    "kick": 36,
    "snare": 38,
    "hihat": 42,
}


def assemble_midi(
    melody_notes: list[NoteEvent],
    drum_hits: list[DrumHit],
    output_dir: str,
    tempo: float = 120.0,
) -> str:
    """Assemble a multi-track MIDI file from melody notes and drum hits."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    # Track 1: Melody (flute, program 73)
    if melody_notes:
        flute = pretty_midi.Instrument(program=73, is_drum=False, name="Melody")
        for n in melody_notes:
            note = pretty_midi.Note(
                velocity=n.velocity,
                pitch=n.pitch,
                start=n.start,
                end=n.end,
            )
            flute.notes.append(note)
        midi.instruments.append(flute)

    # Track 2: Drums (channel 9, is_drum=True)
    if drum_hits:
        drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
        for hit in drum_hits:
            note_num = DRUM_MAP.get(hit.drum, 38)
            note = pretty_midi.Note(
                velocity=100,
                pitch=note_num,
                start=hit.time,
                end=hit.time + 0.1,  # Short duration for percussion
            )
            drums.notes.append(note)
        midi.instruments.append(drums)

    out_path = os.path.join(output_dir, "output.mid")
    midi.write(out_path)
    return out_path
