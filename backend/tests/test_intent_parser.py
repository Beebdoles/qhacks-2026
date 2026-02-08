import json
from unittest.mock import patch, MagicMock

import pytest

from models import Segment, SegmentType, ChordData
from intent.parser import pick_tools, _build_segment_table
from intent.schema import ToolName, ToolPickerOutput, ToolCall, AudioSegmentRef


class TestBuildSegmentTable:
    """Test the segment table builder."""

    def test_empty_segments(self):
        assert _build_segment_table([]) == "(no musical segments)"

    def test_silence_only(self):
        segs = [Segment(type=SegmentType.silence, start=0, end=1)]
        assert _build_segment_table(segs) == "(no musical segments)"

    def test_speech_only(self):
        segs = [Segment(type=SegmentType.speech, start=0, end=1)]
        assert _build_segment_table(segs) == "(no musical segments)"

    def test_humming_segment(self):
        segs = [
            Segment(type=SegmentType.speech, start=0, end=3),
            Segment(
                type=SegmentType.humming,
                start=3,
                end=8,
                audio_clip_path="/tmp/seg_1.mp3",
                chords=[ChordData(degree=1, duration_beats=1), ChordData(degree=4, duration_beats=1), ChordData(degree=5, duration_beats=1)],
            ),
        ]
        table = _build_segment_table(segs)
        assert "| 1 | humming |" in table
        assert "/tmp/seg_1.mp3" in table
        assert "1 → 4 → 5" in table

    def test_multiple_musical_segments(self):
        segs = [
            Segment(type=SegmentType.humming, start=0, end=3, audio_clip_path="/tmp/a.mp3"),
            Segment(type=SegmentType.singing, start=3, end=6, audio_clip_path="/tmp/b.mp3"),
        ]
        table = _build_segment_table(segs)
        assert "| 0 | humming |" in table
        assert "| 1 | singing |" in table


class TestPickToolsMocked:
    """Test pick_tools with mocked Gemini calls."""

    @patch("intent.parser._get_client")
    def test_single_mp3_to_midi(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "tool_calls": [{
                "tool": "mp3_to_midi",
                "instruction": "Convert the humming into a guitar track",
                "audio_segment": {"index": 1, "type": "humming", "path": "/tmp/seg_1.mp3"},
                "params": {"instrument": "guitar"},
            }]
        })
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        segments = [
            Segment(type=SegmentType.speech, start=0, end=3),
            Segment(type=SegmentType.humming, start=3, end=8, audio_clip_path="/tmp/seg_1.mp3"),
        ]

        result = pick_tools("User said: make this guitar", segments)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool == ToolName.mp3_to_midi
        assert result.tool_calls[0].params["instrument"] == "guitar"
        assert result.tool_calls[0].audio_segment.index == 1

    @patch("intent.parser._get_client")
    def test_empty_tool_calls(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps({"tool_calls": []})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = pick_tools("Hmm let me think", [])
        assert result.tool_calls == []

    @patch("intent.parser._get_client")
    def test_multiple_tool_calls(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "tool_calls": [
                {
                    "tool": "mp3_to_midi",
                    "instruction": "Convert humming to piano",
                    "audio_segment": {"index": 0, "type": "humming", "path": "/tmp/seg.mp3"},
                    "params": {"instrument": "piano"},
                },
                {
                    "tool": "repeat_track",
                    "instruction": "Repeat the piano track 3 times",
                    "params": {"times": 3, "target_description": "the piano track"},
                },
            ]
        })
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        segments = [
            Segment(type=SegmentType.humming, start=0, end=5, audio_clip_path="/tmp/seg.mp3"),
        ]

        result = pick_tools("Make this piano and repeat 3 times", segments)
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].tool == ToolName.mp3_to_midi
        assert result.tool_calls[1].tool == ToolName.repeat_track
        assert result.tool_calls[1].params["times"] == 3

    @patch("intent.parser._get_client")
    def test_invalid_response_falls_back_empty(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.text = "completely broken json"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = pick_tools("test", [])
        assert result.tool_calls == []

    @patch("intent.parser._get_client")
    def test_switch_instrument(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "tool_calls": [{
                "tool": "switch_instrument",
                "instruction": "Change the piano to guitar",
                "params": {"instrument": "guitar", "target_description": "the piano track"},
            }]
        })
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = pick_tools("Change piano to guitar", [])
        assert result.tool_calls[0].tool == ToolName.switch_instrument
        assert result.tool_calls[0].audio_segment is None

    @patch("intent.parser._get_client")
    def test_pitch_shift(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "tool_calls": [{
                "tool": "pitch_shift",
                "instruction": "Transpose up an octave",
                "params": {"semitones": 12, "target_description": "the guitar track"},
            }]
        })
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = pick_tools("Transpose up an octave", [])
        assert result.tool_calls[0].tool == ToolName.pitch_shift
        assert result.tool_calls[0].params["semitones"] == 12


class TestGoldenExample:
    """Test the golden example from testSegmentation.mp3:
    User says "piano", then hums, then corrects to "guitar".
    Should produce ONE mp3_to_midi call with guitar.
    """

    @patch("intent.parser._get_client")
    def test_user_correction_produces_single_call(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "tool_calls": [{
                "tool": "mp3_to_midi",
                "instruction": "Convert the humming into a guitar track (user corrected from piano to guitar)",
                "audio_segment": {"index": 1, "type": "humming", "path": "/tmp/seg_1_humming.mp3"},
                "params": {"instrument": "guitar"},
            }]
        })
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        instruction_doc = (
            '[0.0s - 4.5s | SPEECH]: "Alright, so I want this song to be in piano."\n'
            '[4.5s - 9.5s | HUMMING]: Musical segment (3 chords, chords: 1 → 4 → 5) '
            '[file: /tmp/seg_1_humming.mp3]\n'
            '[9.5s - 13.5s | SPEECH]: "Um, actually, I want it in guitar."'
        )
        segments = [
            Segment(type=SegmentType.speech, start=0, end=4.5),
            Segment(
                type=SegmentType.humming,
                start=4.5,
                end=9.5,
                audio_clip_path="/tmp/seg_1_humming.mp3",
                chords=[ChordData(degree=1, duration_beats=1), ChordData(degree=4, duration_beats=1), ChordData(degree=5, duration_beats=1)],
            ),
            Segment(type=SegmentType.speech, start=9.5, end=13.5),
        ]

        result = pick_tools(instruction_doc, segments)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool == ToolName.mp3_to_midi
        assert result.tool_calls[0].params["instrument"] == "guitar"
        assert result.tool_calls[0].audio_segment.index == 1
        assert result.tool_calls[0].audio_segment.path == "/tmp/seg_1_humming.mp3"
