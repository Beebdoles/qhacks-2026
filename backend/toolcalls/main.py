"""Hardcoded toolcall test — runs change_pitch on instruction upload.

Tracks are named by segment type: "singing", "humming", "beatboxing".
The piano instrument is on the "singing" track.
"""

from toolcalls.change_pitch import change_pitch
from toolcalls.change_scale import change_scale


def apply_instructions() -> str:
    """Apply hardcoded pitch change for testing.

    TODO: Replace with actual instruction parsing from audio.
    """
    try:
        #return change_pitch(layer="singing", pitch=12, shift_type="semitone")
        return change_scale(layer="singing", target_scale="C minor")
    except Exception as exc:
        msg = f"[apply_instructions] Tool call failed: {exc}"
        print(msg)
        return msg
