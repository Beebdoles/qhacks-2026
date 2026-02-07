import tempfile
import os
import uuid
from pathlib import Path
from musiclang_predict import MusicLangPredictor
from musiclang import Score

OUTPUT_DIR = Path(__file__).resolve().parent / "midi-outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

INSTRUMENT_ALIASES = {
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


def _save_bytes_to_temp(data: bytes) -> str:
    """Save bytes to a temp .mid file. Returns the path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


def _create_output_midi_path() -> str:
    """Create a unique output path in the midi-outputs folder."""
    return str(OUTPUT_DIR / f"{uuid.uuid4().hex}.mid")


def cleanup(path: str):
    """Remove a temp file if it exists."""
    try:
        os.unlink(path)
    except OSError:
        pass


class MusicService:
    def __init__(self):
        self.predictor = MusicLangPredictor("musiclang/musiclang-v2")

    def generate(
        self,
        chord_progression: str | None,
        nb_tokens: int,
        temperature: float,
        topp: float,
        rng_seed: int,
        tempo: int,
        time_signature: tuple[int, int],
    ) -> str:
        """Generate music from scratch. Returns path to output MIDI file."""
        output_path = _create_output_midi_path()

        if chord_progression:
            score = self.predictor.predict_chords(
                chord_progression,
                time_signature=time_signature,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
            )
        else:
            score = self.predictor.predict(
                None,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
            )

        score.to_midi(output_path, tempo=tempo, time_signature=time_signature)
        return output_path

    def extend(
        self,
        midi_bytes: bytes,
        nb_tokens: int,
        temperature: float,
        topp: float,
        rng_seed: int,
        tempo: int,
        time_signature: tuple[int, int],
    ) -> str:
        """Extend an existing MIDI file. Returns path to output MIDI file."""
        input_path = _save_bytes_to_temp(midi_bytes)
        output_path = _create_output_midi_path()
        try:
            original_score = Score.from_midi(input_path)
            generated_score = self.predictor.predict(
                input_path,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
            )
            combined = original_score + generated_score
            combined.to_midi(output_path, tempo=tempo, time_signature=time_signature)
            return output_path
        finally:
            cleanup(input_path)

    def analyze_midi(self, midi_bytes: bytes) -> dict:
        """Extract metadata from a MIDI file for LLM context."""
        input_path = _save_bytes_to_temp(midi_bytes)
        try:
            score = Score.from_midi(input_path)
            return {
                "instruments": list(score.instrument_names),
                "duration": str(score.duration),
            }
        finally:
            cleanup(input_path)

    def apply_edit(
        self,
        midi_bytes: bytes,
        edit_plan: dict,
        nb_tokens: int,
        temperature: float,
        topp: float,
        rng_seed: int,
        tempo: int,
        time_signature: tuple[int, int],
    ) -> str:
        """Apply an LLM-produced edit plan to a MIDI file. Returns path to output MIDI."""
        input_path = _save_bytes_to_temp(midi_bytes)
        output_path = _create_output_midi_path()

        try:
            action = edit_plan.get("action", "regenerate_with_chords")

            # Override params if LLM specified them
            if edit_plan.get("tempo"):
                tempo = edit_plan["tempo"]
            if edit_plan.get("temperature"):
                temperature = edit_plan["temperature"]

            if action in ("regenerate_with_chords", "regenerate_with_chords_and_tempo"):
                chord_progression = edit_plan.get("chord_progression")
                if chord_progression:
                    score = self.predictor.predict_chords(
                        chord_progression,
                        time_signature=time_signature,
                        score=input_path,
                        nb_tokens=nb_tokens,
                        temperature=temperature,
                        topp=topp,
                        rng_seed=rng_seed,
                    )
                else:
                    score = self.predictor.predict(
                        input_path,
                        nb_tokens=nb_tokens,
                        temperature=temperature,
                        topp=topp,
                        rng_seed=rng_seed,
                    )

            elif action == "extend":
                original_score = Score.from_midi(input_path)
                generated = self.predictor.predict(
                    input_path,
                    nb_tokens=nb_tokens,
                    temperature=temperature,
                    topp=topp,
                    rng_seed=rng_seed,
                )
                score = original_score + generated

            elif action == "change_tempo":
                score = Score.from_midi(input_path)

            elif action == "adjust_temperature":
                score = self.predictor.predict(
                    input_path,
                    nb_tokens=nb_tokens,
                    temperature=temperature,
                    topp=topp,
                    rng_seed=rng_seed,
                )

            else:
                # Unknown action: regenerate using original as prompt
                score = self.predictor.predict(
                    input_path,
                    nb_tokens=nb_tokens,
                    temperature=temperature,
                    topp=topp,
                    rng_seed=rng_seed,
                )

            score.to_midi(output_path, tempo=tempo, time_signature=time_signature)
            return output_path
        finally:
            cleanup(input_path)

    # ------------------------------------------------------------------
    # Helpers for arrange / backtrack
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_instrument(name: str) -> str:
        """Resolve aliases and normalize an instrument name."""
        name = name.strip().lower()
        return INSTRUMENT_ALIASES.get(name, name)

    @staticmethod
    def _default_accompaniment(target_instrument: str) -> list[str]:
        """Choose sensible default accompaniment instruments, excluding the target."""
        defaults = ["piano", "acoustic_bass", "drums_0"]
        return [i for i in defaults if i != target_instrument]

    @staticmethod
    def _merge_scores(melody_score: Score, accompaniment_score: Score) -> Score:
        """Merge a melody score with an accompaniment score chord-by-chord.

        Both scores must share the same chord progression (same number of chords).
        The melody parts are injected into each accompaniment chord.
        """
        num_chords = min(len(melody_score.chords), len(accompaniment_score.chords))
        merged_chords = []
        for i in range(num_chords):
            mel_chord = melody_score.chords[i]
            acc_chord = accompaniment_score.chords[i]
            # Merge the score dicts: accompaniment parts + melody parts
            merged_parts = {}
            merged_parts.update(acc_chord.score)
            merged_parts.update(mel_chord.score)  # melody takes priority on conflict
            merged_chords.append(acc_chord(**merged_parts))

        if not merged_chords:
            raise ValueError("No chords to merge — input may be empty")
        return sum(merged_chords[1:], merged_chords[0])

    # ------------------------------------------------------------------
    # Feature 2: Arrange (transcribe + accompaniment)
    # ------------------------------------------------------------------

    def arrange(
        self,
        midi_bytes: bytes,
        target_instrument: str,
        accompaniment_instruments: list[str] | None,
        nb_tokens: int,
        temperature: float,
        topp: float,
        rng_seed: int,
        tempo: int,
        time_signature: tuple[int, int],
    ) -> str:
        """Transcribe melody to target instrument and generate accompaniment.

        Returns path to the output MIDI file.
        """
        target_instrument = self._normalize_instrument(target_instrument)
        input_path = _save_bytes_to_temp(midi_bytes)
        output_path = _create_output_midi_path()
        try:
            # 1. Load input and extract chord progression
            original_score = Score.from_midi(input_path)
            chord_repr = original_score.to_chord_repr()
            chords_list = chord_repr.split()

            # 2. Extract primary melody (first instrument)
            original_instruments = list(original_score.instrument_names)
            melody_instrument = original_instruments[0]
            melody_score = original_score.get_instrument_names([melody_instrument])

            # 3. Rename melody to target instrument
            if melody_instrument != target_instrument:
                melody_score = melody_score.replace_instruments_names(
                    **{melody_instrument: target_instrument}
                )

            # 4. Determine accompaniment instruments
            if accompaniment_instruments:
                acc_instruments = [
                    self._normalize_instrument(i) for i in accompaniment_instruments
                ]
            else:
                acc_instruments = self._default_accompaniment(target_instrument)

            # Remove target instrument from accompaniment to avoid collision
            acc_instruments = [i for i in acc_instruments if i != target_instrument]
            if not acc_instruments:
                acc_instruments = self._default_accompaniment(target_instrument)

            # 5. Build template and generate accompaniment
            template = [(chord, acc_instruments) for chord in chords_list]
            accompaniment_score = self.predictor.predict_chords_and_instruments(
                template,
                time_signature=time_signature,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
            )

            # 6. Merge melody + accompaniment
            combined = self._merge_scores(melody_score, accompaniment_score)
            combined.to_midi(output_path, tempo=tempo, time_signature=time_signature)
            return output_path
        finally:
            cleanup(input_path)

    # ------------------------------------------------------------------
    # Feature 4: Make backtrack
    # ------------------------------------------------------------------

    def make_backtrack(
        self,
        midi_bytes: bytes,
        backing_instruments: list[str],
        nb_tokens: int,
        temperature: float,
        topp: float,
        rng_seed: int,
        tempo: int,
        time_signature: tuple[int, int],
    ) -> str:
        """Generate a full-band backing track for an input melody MIDI.

        Returns path to the output MIDI file containing melody + backing.
        """
        input_path = _save_bytes_to_temp(midi_bytes)
        output_path = _create_output_midi_path()
        try:
            # 1. Load melody and extract chord structure
            melody_score = Score.from_midi(input_path)
            chord_repr = melody_score.to_chord_repr()
            chords_list = chord_repr.split()

            # 2. Normalize instruments and remove any that collide with the melody
            melody_instruments = set(melody_score.instrument_names)
            backing = [
                self._normalize_instrument(i) for i in backing_instruments
                if self._normalize_instrument(i) not in melody_instruments
            ]
            if not backing:
                # Fall back if all instruments collided
                backing = ["piano", "acoustic_bass", "drums_0"]
                backing = [i for i in backing if i not in melody_instruments]

            if not backing:
                raise ValueError(
                    "Could not determine backing instruments — melody uses all defaults"
                )

            # 3. Build template and generate backing track
            template = [(chord, backing) for chord in chords_list]
            backing_score = self.predictor.predict_chords_and_instruments(
                template,
                time_signature=time_signature,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
            )

            # 4. Merge melody + backing
            combined = self._merge_scores(melody_score, backing_score)
            combined.to_midi(output_path, tempo=tempo, time_signature=time_signature)
            return output_path
        finally:
            cleanup(input_path)
