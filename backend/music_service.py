import tempfile
import os
from musiclang_predict import MusicLangPredictor
from musiclang import Score


def _save_bytes_to_temp(data: bytes) -> str:
    """Save bytes to a temp .mid file. Returns the path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


def _create_temp_midi_path() -> str:
    """Create a temp file path for output MIDI."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    tmp.close()
    return tmp.name


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
        output_path = _create_temp_midi_path()

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
        output_path = _create_temp_midi_path()
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
        output_path = _create_temp_midi_path()

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
