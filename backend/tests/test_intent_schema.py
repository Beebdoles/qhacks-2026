import pytest
from pydantic import ValidationError

from intent.schema import (
    ToolName,
    ToolCall,
    ToolPickerOutput,
    AudioSegmentRef,
)


class TestToolCallValidation:

    def test_valid_mp3_to_midi(self):
        tc = ToolCall(
            tool=ToolName.mp3_to_midi,
            instruction="Convert humming to guitar",
            audio_segment=AudioSegmentRef(index=1, type="humming", path="/tmp/seg.mp3"),
            params={"instrument": "guitar"},
        )
        assert tc.tool == ToolName.mp3_to_midi
        assert tc.audio_segment.index == 1
        assert tc.params["instrument"] == "guitar"

    def test_valid_no_audio_segment(self):
        tc = ToolCall(
            tool=ToolName.repeat_track,
            instruction="Repeat 3 times",
            params={"times": 3},
        )
        assert tc.audio_segment is None

    def test_valid_switch_instrument(self):
        tc = ToolCall(
            tool=ToolName.switch_instrument,
            instruction="Change piano to guitar",
            params={"instrument": "guitar", "target_description": "the piano track"},
        )
        assert tc.tool == ToolName.switch_instrument

    def test_valid_pitch_shift(self):
        tc = ToolCall(
            tool=ToolName.pitch_shift,
            instruction="Transpose up an octave",
            params={"semitones": 12},
        )
        assert tc.params["semitones"] == 12

    def test_default_params_empty(self):
        tc = ToolCall(
            tool=ToolName.mp3_to_midi,
            instruction="Convert to MIDI",
        )
        assert tc.params == {}


class TestToolCallInvalid:

    def test_invalid_tool_name(self):
        with pytest.raises(ValidationError):
            ToolCall(tool="invalid", instruction="test")

    def test_missing_tool(self):
        with pytest.raises(ValidationError):
            ToolCall(instruction="test")

    def test_missing_instruction(self):
        with pytest.raises(ValidationError):
            ToolCall(tool=ToolName.mp3_to_midi)


class TestToolPickerOutput:

    def test_empty_list(self):
        out = ToolPickerOutput(tool_calls=[])
        assert out.tool_calls == []

    def test_single_tool_call(self):
        out = ToolPickerOutput(tool_calls=[
            ToolCall(
                tool=ToolName.mp3_to_midi,
                instruction="Convert humming to piano",
                audio_segment=AudioSegmentRef(index=0, type="humming", path="/tmp/seg.mp3"),
                params={"instrument": "piano"},
            )
        ])
        assert len(out.tool_calls) == 1

    def test_multiple_tool_calls(self):
        out = ToolPickerOutput(tool_calls=[
            ToolCall(tool=ToolName.mp3_to_midi, instruction="Convert", params={"instrument": "piano"}),
            ToolCall(tool=ToolName.repeat_track, instruction="Repeat 3x", params={"times": 3}),
        ])
        assert len(out.tool_calls) == 2

    def test_from_json(self):
        json_str = '{"tool_calls": [{"tool": "mp3_to_midi", "instruction": "Convert", "params": {"instrument": "piano"}}]}'
        out = ToolPickerOutput.model_validate_json(json_str)
        assert out.tool_calls[0].tool == ToolName.mp3_to_midi

    def test_invalid_json_raises(self):
        with pytest.raises(ValidationError):
            ToolPickerOutput.model_validate_json('{"tool_calls": [{"tool": "bad"}]}')
