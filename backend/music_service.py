import tempfile
import os
import uuid
from pathlib import Path
from musiclang_predict import MusicLangPredictor
from musiclang import Score
from basic_pitch.inference import predict as bp_predict, Model as BPModel
from basic_pitch import ICASSP_2022_MODEL_PATH
import pretty_midi
import mido

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


def _smooth_midi(midi_data: pretty_midi.PrettyMIDI,
                  min_note_duration: float = 0.15,
                  merge_gap: float = 0.05,
                  quantize_bpm: float = None,
                  quantize_grid: str = "sixteenth") -> pretty_midi.PrettyMIDI:
    """Aggressive anti-jitter MIDI cleanup for humming/vocal transcription.

    Pipeline:
    1. Majority voting: snap short notes to the pitch of their stable neighbors.
       Looks past immediate neighbors to find "anchor" notes (duration >= threshold).
    2. Remove notes shorter than min_note_duration.
    3. Merge consecutive same-pitch notes separated by small gaps.
    4. Second cull: remove anything that became too short after merging.
    5. Optional rhythm quantization to a beat grid.
    """
    short_threshold = min_note_duration * 2  # notes under this are snap candidates

    for instrument in midi_data.instruments:
        if not instrument.notes:
            continue

        instrument.notes.sort(key=lambda n: n.start)
        notes = instrument.notes

        # --- Pass 1: Aggressive majority voting ---
        # For each short note, find the nearest stable (long) neighbors on each
        # side and snap if they agree on pitch and the current note is within
        # 2 semitones. Also snaps to a single stable neighbor if only one exists.
        for i in range(len(notes)):
            curr = notes[i]
            if (curr.end - curr.start) >= short_threshold:
                continue

            prev_pitch = None
            next_pitch = None

            for j in range(i - 1, -1, -1):
                if (notes[j].end - notes[j].start) >= min_note_duration:
                    prev_pitch = notes[j].pitch
                    break

            for j in range(i + 1, len(notes)):
                if (notes[j].end - notes[j].start) >= min_note_duration:
                    next_pitch = notes[j].pitch
                    break

            if prev_pitch is not None and next_pitch is not None:
                if prev_pitch == next_pitch and abs(curr.pitch - prev_pitch) <= 2:
                    curr.pitch = prev_pitch
            elif prev_pitch is not None and abs(curr.pitch - prev_pitch) <= 1:
                curr.pitch = prev_pitch
            elif next_pitch is not None and abs(curr.pitch - next_pitch) <= 1:
                curr.pitch = next_pitch

        # --- Pass 2: Remove very short notes ---
        notes = [n for n in notes if (n.end - n.start) >= min_note_duration]

        # --- Pass 3: Merge consecutive same-pitch notes ---
        if notes:
            merged = [notes[0]]
            for note in notes[1:]:
                prev = merged[-1]
                if (note.pitch == prev.pitch
                        and note.start - prev.end <= merge_gap):
                    prev.end = max(prev.end, note.end)
                    prev.velocity = max(prev.velocity, note.velocity)
                else:
                    merged.append(note)
            notes = merged

        # --- Pass 4: Second cull after merging ---
        notes = [n for n in notes if (n.end - n.start) >= min_note_duration]

        # --- Pass 5: Optional rhythm quantization ---
        if quantize_bpm and notes:
            beat_dur = 60.0 / quantize_bpm
            grid = {
                "sixteenth": beat_dur / 4,
                "eighth": beat_dur / 2,
                "quarter": beat_dur,
            }.get(quantize_grid, beat_dur / 4)

            for note in notes:
                note.start = round(note.start / grid) * grid
                note.end = round(note.end / grid) * grid
                if note.end - note.start < grid:
                    note.end = note.start + grid

            # Re-merge after quantization (may create overlaps)
            notes.sort(key=lambda n: n.start)
            merged = [notes[0]]
            for note in notes[1:]:
                prev = merged[-1]
                if note.pitch == prev.pitch and note.start <= prev.end:
                    prev.end = max(prev.end, note.end)
                    prev.velocity = max(prev.velocity, note.velocity)
                else:
                    merged.append(note)
            notes = merged

        instrument.notes = notes

    return midi_data


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


def autotune_audio(audio_bytes: bytes, filename: str, smooth: bool = True,
                    min_note_duration: float = 0.15, merge_gap: float = 0.05,
                    quantize_bpm: float = None,
                    quantize_grid: str = "sixteenth") -> bytes:
    """Convert audio to MIDI, optionally with aggressive anti-jitter smoothing."""
    suffix = Path(filename).suffix.lower() if filename else ".mp3"
    tmp_audio = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_audio.write(audio_bytes)
    tmp_audio.close()

    try:
        # 1. Run basic-pitch on audio
        _, midi_data, _ = bp_predict(
            tmp_audio.name, model_or_model_path=_BP_MODEL
        )

        # 2. Optionally smooth MIDI
        if smooth:
            midi_data = _smooth_midi(
                midi_data,
                min_note_duration=min_note_duration,
                merge_gap=merge_gap,
                quantize_bpm=quantize_bpm,
                quantize_grid=quantize_grid,
            )

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

    def analyze_midi_full(self, midi_bytes: bytes) -> dict:
        """Comprehensive MIDI analysis for arrangement planning."""
        input_path = _save_bytes_to_temp(midi_bytes)
        try:
            # --- musiclang analysis ---
            score = Score.from_midi(input_path)
            chord_repr = score.to_chord_repr()
            chords_list = chord_repr.split()
            instruments = list(score.instrument_names)
            duration_quarters = float(score.duration)

            # Key + Roman numerals
            try:
                key_str, roman_list = score.to_romantext_chord_list()
            except Exception:
                key_str, roman_list = "C", []

            # Densities, octaves, amplitudes
            try:
                densities = score.extract_densities()
            except Exception:
                densities = {}
            try:
                mean_octaves = score.extract_mean_octaves()
            except Exception:
                mean_octaves = {}
            try:
                mean_amplitudes = score.extract_mean_amplitudes()
            except Exception:
                mean_amplitudes = {}

            # --- pretty_midi for tempo + duration in seconds ---
            pm = pretty_midi.PrettyMIDI(input_path)
            try:
                pm_tempo = round(pm.estimate_tempo())
            except Exception:
                pm_tempo = 120
            duration_seconds = round(pm.get_end_time(), 2)

            # --- mido for time_signature meta messages ---
            mid = mido.MidiFile(input_path)
            mido_ts = None
            for track in mid.tracks:
                for msg in track:
                    if msg.type == "time_signature":
                        mido_ts = (msg.numerator, msg.denominator)
                        break
                if mido_ts:
                    break

            final_time_sig = mido_ts if mido_ts else (4, 4)
            final_tempo = pm_tempo if pm_tempo and pm_tempo > 0 else 120

            # --- Complexity heuristic ---
            avg_density = (
                sum(densities.values()) / len(densities) if densities else 0
            )
            unique_chords = len(set(chords_list))
            if unique_chords <= 2 and avg_density < 2.0:
                complexity = "simple"
            elif unique_chords >= 5 or avg_density > 5.0:
                complexity = "complex"
            else:
                complexity = "moderate"

            return {
                "chord_progression": chord_repr,
                "roman_numerals": roman_list,
                "key": key_str,
                "tempo": int(final_tempo),
                "time_signature": final_time_sig,
                "instruments": instruments,
                "duration_quarters": duration_quarters,
                "duration_seconds": duration_seconds,
                "num_chords": len(chords_list),
                "densities": {str(k): round(v, 2) for k, v in densities.items()},
                "mean_octaves": {str(k): v for k, v in mean_octaves.items()},
                "mean_amplitudes": {str(k): v for k, v in mean_amplitudes.items()},
                "complexity": complexity,
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
        accompaniment_instruments: list[str],
        nb_tokens: int,
        temperature: float,
        topp: float,
        rng_seed: int,
        tempo: int,
        time_signature: tuple[int, int],
        chord_progression: str | None = None,
        target_instrument: str | None = None,
    ) -> str:
        """Keep existing notes/melody and generate accompaniment around them.

        Uses pre-resolved accompaniment instruments and optionally an LLM-enriched
        chord progression. If chord_progression is None, extracts from the input.
        Returns path to the output MIDI file.
        """
        input_path = _save_bytes_to_temp(midi_bytes)
        output_path = _create_output_midi_path()
        try:
            # 1. Load input and determine chord progression
            original_score = Score.from_midi(input_path)
            if chord_progression:
                chords_list = chord_progression.split()
            else:
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
