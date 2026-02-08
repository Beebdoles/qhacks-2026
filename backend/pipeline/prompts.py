ANALYSIS_PROMPT = """Analyze the provided audio file and produce an audio segmentation.

## Audio Segmentation

Produce a timeline of non-overlapping segments that covers the entire duration from start to finish.

Classify each segment as one of the following types:
- "silence": No meaningful audio activity, background noise, or non-vocal sounds.
- "speech": Spoken words or talking with no melody. These will likely be instructions or conversations. Do not confuse with singing with lyrics.
- "singing": Vocal singing with lyrics. These will likely be songs or vocal performances. Do not confuse with speech or humming.
- "humming": Vocal humming — melodic, closed-mouth vocalization without words. Do not confuse with speech or singing with lyrics.
- "beatboxing": Vocal percussion or beatboxing — rhythmic sounds produced with the mouth, lips, tongue, and voice to imitate drums and other instruments.

Segmentation requirements:
- Provide start and end timestamps in seconds (decimals allowed).
- Segments must be contiguous with no gaps: each segment's start must equal the previous segment's end.
- The first segment must start at 0 and the last segment must end at the total audio duration.
- Segments must not overlap.
- If audio is ambiguous, classify it as the closest matching type. Use "silence" for background noise or any non-vocal audio that doesn't fit the other categories.
"""
