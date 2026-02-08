from intent.schema import ToolName
from intent.normalize import normalize_params, validate_required_params


class TestNormalizePitchShift:

    def test_semitones_int(self):
        result = normalize_params(ToolName.pitch_shift, {"semitones": 12})
        assert result["semitones"] == 12

    def test_semitones_string(self):
        result = normalize_params(ToolName.pitch_shift, {"semitones": "7"})
        assert result["semitones"] == 7

    def test_octave_up(self):
        result = normalize_params(ToolName.pitch_shift, {"octave_up": True})
        assert result["semitones"] == 12
        assert "octave_up" not in result

    def test_octave_down(self):
        result = normalize_params(ToolName.pitch_shift, {"octave_down": True})
        assert result["semitones"] == -12

    def test_up_alias(self):
        result = normalize_params(ToolName.pitch_shift, {"up": 5})
        assert result["semitones"] == 5
        assert "up" not in result

    def test_down_alias(self):
        result = normalize_params(ToolName.pitch_shift, {"down": 3})
        assert result["semitones"] == -3
        assert "down" not in result


class TestNormalizeRepeatTrack:

    def test_times_direct(self):
        result = normalize_params(ToolName.repeat_track, {"times": 3})
        assert result["times"] == 3

    def test_repeat_alias(self):
        result = normalize_params(ToolName.repeat_track, {"repeat": 4})
        assert result["times"] == 4
        assert "repeat" not in result

    def test_count_alias(self):
        result = normalize_params(ToolName.repeat_track, {"count": 2})
        assert result["times"] == 2

    def test_string_value(self):
        result = normalize_params(ToolName.repeat_track, {"times": "5"})
        assert result["times"] == 5


class TestNormalizeSwitchInstrument:

    def test_alias_guitar(self):
        result = normalize_params(ToolName.switch_instrument, {"instrument": "guitar"})
        assert result["instrument"] == "acoustic_guitar"

    def test_alias_drums(self):
        result = normalize_params(ToolName.switch_instrument, {"instrument": "drums"})
        assert result["instrument"] == "drums_0"

    def test_no_alias(self):
        result = normalize_params(ToolName.switch_instrument, {"instrument": "piano"})
        assert result["instrument"] == "piano"

    def test_case_insensitive(self):
        result = normalize_params(ToolName.switch_instrument, {"instrument": "Guitar"})
        assert result["instrument"] == "acoustic_guitar"


class TestNormalizeMp3ToMidi:

    def test_instrument_alias(self):
        result = normalize_params(ToolName.mp3_to_midi, {"instrument": "bass"})
        assert result["instrument"] == "acoustic_bass"


class TestNormalizeProgressionChange:

    def test_string_dashes(self):
        result = normalize_params(ToolName.progression_change, {"progression": "1-4-5"})
        assert result["progression"] == [1, 4, 5]

    def test_string_spaces(self):
        result = normalize_params(ToolName.progression_change, {"progression": "1 4 5 1"})
        assert result["progression"] == [1, 4, 5, 1]

    def test_list(self):
        result = normalize_params(ToolName.progression_change, {"progression": [1, 4, 5]})
        assert result["progression"] == [1, 4, 5]

    def test_list_strings(self):
        result = normalize_params(ToolName.progression_change, {"progression": ["1", "4", "5"]})
        assert result["progression"] == [1, 4, 5]


class TestValidateRequiredParams:

    def test_switch_instrument_ok(self):
        assert validate_required_params(ToolName.switch_instrument, {"instrument": "piano"}) is None

    def test_switch_instrument_missing(self):
        assert validate_required_params(ToolName.switch_instrument, {}) is not None

    def test_pitch_shift_ok(self):
        assert validate_required_params(ToolName.pitch_shift, {"semitones": 12}) is None

    def test_pitch_shift_missing(self):
        assert validate_required_params(ToolName.pitch_shift, {}) is not None

    def test_repeat_track_ok(self):
        assert validate_required_params(ToolName.repeat_track, {"times": 3}) is None

    def test_repeat_track_missing(self):
        assert validate_required_params(ToolName.repeat_track, {}) is not None

    def test_mp3_to_midi_no_required(self):
        assert validate_required_params(ToolName.mp3_to_midi, {}) is None
