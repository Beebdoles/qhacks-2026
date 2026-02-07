import tempfile
import os
import uuid
from pathlib import Path
from musiclang_predict import MusicLangPredictor
from musiclang import Score
from basic_pitch.inference import predict as bp_predict, Model as BPModel
from basic_pitch import ICASSP_2022_MODEL_PATH

# Use CoreML model on macOS (TF SavedModel is incompatible with TF 2.20)
_BP_MODEL = BPModel(Path(ICASSP_2022_MODEL_PATH).parent / "nmp.mlpackage")

OUTPUT_DIR = Path(__file__).resolve().parent / "midi-outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}

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


def convert_audio_to_midi(audio_bytes: bytes, filename: str) -> bytes:
    """Convert audio bytes (mp3/wav/etc.) to MIDI bytes using basic-pitch."""
    suffix = Path(filename).suffix.lower() if filename else ".mp3"
    tmp_audio = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_audio.write(audio_bytes)
    tmp_audio.close()
    try:
        _, midi_data, _ = bp_predict(tmp_audio.name, model_or_model_path=_BP_MODEL)
        midi_output = _create_output_midi_path()
        midi_data.write(midi_output)
        with open(midi_output, "rb") as f:
            midi_bytes = f.read()
        cleanup(midi_output)
        return midi_bytes
    finally:
        cleanup(tmp_audio.name)


def ensure_midi_bytes(file_bytes: bytes, filename: str) -> bytes:
    """If the file is audio (mp3/wav/etc.), convert to MIDI. Otherwise return as-is."""
    suffix = Path(filename).suffix.lower() if filename else ""
    if suffix in AUDIO_EXTENSIONS:
        return convert_audio_to_midi(file_bytes, filename)
    return file_bytes


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
    # Change instrument (no generation, just swap)
    # ------------------------------------------------------------------

    def change_instrument(
        self,
        midi_bytes: bytes,
        target_instrument: str,
        tempo: int,
        time_signature: tuple[int, int],
    ) -> str:
        """Change the instrument of a MIDI file. Returns path to output MIDI."""
        target_instrument = self._normalize_instrument(target_instrument)
        input_path = _save_bytes_to_temp(midi_bytes)
        output_path = _create_output_midi_path()
        try:
            score = Score.from_midi(input_path)
            original_instruments = list(score.instrument_names)
            if not original_instruments:
                raise ValueError("Input MIDI has no instruments")
            # Rename the first (primary) instrument to the target
            primary = original_instruments[0]
            if primary != target_instrument:
                score = score.replace_instruments_names(
                    **{primary: target_instrument}
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
        """Choose a rich default accompaniment ensemble, excluding the target."""
        defaults = [
            "piano",           # chords / harmony
            "acoustic_guitar", # rhythm chords
            "acoustic_bass",   # bass line
            "string_ensemble_1",  # pad / sustained chords
            "drums_0",         # percussion
        ]
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
    # Feature 2: Arrange (enhance existing MIDI with accompaniment)
    # ------------------------------------------------------------------

    def arrange(
        self,
        midi_bytes: bytes,
        accompaniment_instruments: list[str] | None,
        nb_tokens: int,
        temperature: float,
        topp: float,
        rng_seed: int,
        tempo: int,
        time_signature: tuple[int, int],
        target_instrument: str | None = None,
    ) -> str:
        """Keep existing notes/melody and generate accompaniment around them.

        Optionally changes the primary instrument if target_instrument is provided.
        Returns path to the output MIDI file.
        """
        input_path = _save_bytes_to_temp(midi_bytes)
        output_path = _create_output_midi_path()
        try:
            # 1. Load input and extract chord progression
            original_score = Score.from_midi(input_path)
            chord_repr = original_score.to_chord_repr()
            chords_list = chord_repr.split()

            # 2. Optionally change the primary instrument
            if target_instrument:
                target_instrument = self._normalize_instrument(target_instrument)
                original_instruments = list(original_score.instrument_names)
                if original_instruments and original_instruments[0] != target_instrument:
                    original_score = original_score.replace_instruments_names(
                        **{original_instruments[0]: target_instrument}
                    )

            # 3. Determine accompaniment instruments (avoid colliding with existing)
            existing_instruments = set(original_score.instrument_names)
            if accompaniment_instruments:
                acc_instruments = [
                    self._normalize_instrument(i) for i in accompaniment_instruments
                    if self._normalize_instrument(i) not in existing_instruments
                ]
            else:
                acc_instruments = self._default_accompaniment("")
                acc_instruments = [
                    i for i in acc_instruments
                    if i not in existing_instruments
                ]

            if not acc_instruments:
                acc_instruments = ["acoustic_guitar", "acoustic_bass", "drums_0"]

            # 4. Build template and generate accompaniment
            template = [(chord, acc_instruments) for chord in chords_list]
            accompaniment_score = self.predictor.predict_chords_and_instruments(
                template,
                time_signature=time_signature,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
            )

            # 5. Merge original (kept intact) + accompaniment
            combined = self._merge_scores(original_score, accompaniment_score)
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
