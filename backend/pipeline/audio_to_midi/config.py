# ── Preprocessing ─────────────────────────────────────────────────────
SAMPLE_RATE = 16000
NOISE_GATE_DB = -40

# ── CREPE pitch detection ─────────────────────────────────────────────
CREPE_MODEL = "full"
FMIN = 65
FMAX = 1047
HOP = 160  # 10ms at 16kHz

# ── Pitch filtering ───────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.5
MEDIAN_FILTER_SIZE = 5
MIN_VOICED_DURATION = 0.03  # seconds

# ── Note segmentation ────────────────────────────────────────────────
PITCH_CHANGE_THRESHOLD = 80  # cents
MIN_NOTE_DURATION = 0.08  # seconds
CONFIDENCE_DIP_THRESHOLD = 0.3
MAX_MERGE_GAP = 0.1  # seconds -- merge consecutive same-pitch notes with gaps smaller than this

# ── Quantization ──────────────────────────────────────────────────────
GRID_SUBDIVISIONS = 4  # 16th notes
QUANTIZE_SNAP_TOLERANCE = 0.4
MIN_ONSETS_FOR_TEMPO = 4

# ── Percussion ────────────────────────────────────────────────────────
KICK_CENTROID_MAX = 200  # Hz
HIHAT_CENTROID_MIN = 5000  # Hz
HIT_WINDOW_PRE = 0.05  # seconds before onset
HIT_WINDOW_POST = 0.1  # seconds after onset
HIHAT_DECAY_THRESHOLD_MS = 30
HIHAT_DECAY_DB = -20
HIT_MIN_AMPLITUDE_DB = -30

# ── Onset detection ──────────────────────────────────────────────────
ONSET_DELTA = 0.05
