# Orca: Voice-to-MIDI Composer Agent


An AI-powered music creation tool that converts voice recordings (singing, humming, beatboxing) into multi-track MIDI, then lets you edit the result with voice instructions.

Built at QHacks 2026.

## How It Works

1. **Record or upload** an audio file (MP3 or WebM) containing singing, humming, or beatboxing
2. The backend runs a **5-stage pipeline** to convert it into a multi-track MIDI file:
   - **BasicPitch** extracts raw note events from the audio
   - **Gemini** segments the audio timeline and classifies each segment (singing, humming, beatboxing, speech, silence), generates chord progressions
   - **Score Builder** routes each segment type to the appropriate MIDI generation strategy (BasicPitch direct notes for dense melodies, MusicLang for sparse/percussive parts)
   - **Instrument Mapper** assigns MIDI channels and programs (singing/humming to piano/flute, beatboxing to drums)
   - **MIDI Merger** combines all tracks into a single multi-track MIDI file
3. The frontend displays the result in a **piano-roll editor** with per-track mute/visibility controls and soundfont playback
4. **Record voice instructions** to modify the MIDI (e.g. change scale, shift pitch) via tool calls

## Tech Stack

**Backend:** Python 3.12, FastAPI, BasicPitch, Google Gemini API, MusicLang, PrettyMIDI, music21, mido

**Frontend:** Next.js 16, React 19, TypeScript, TailwindCSS v4, Tone.js, soundfont-player, @tonejs/midi

## Project Structure

```
qhacks-2026/
├── backend/
│   ├── main.py                  # FastAPI app + CORS
│   ├── models.py                # Pydantic models (JobStatus, Segments, NoteEvent, etc.)
│   ├── routers/
│   │   └── upload.py            # /api/upload, /api/jobs/{id}, /api/jobs/{id}/midi, /api/jobs/{id}/instructions
│   ├── pipeline/
│   │   ├── orchestrator.py      # 5-stage pipeline runner with retry on overload
│   │   ├── melody.py            # Stage 1: BasicPitch note extraction
│   │   ├── stage_gemini.py      # Stage 2: Gemini audio analysis + segmentation
│   │   ├── prompts.py           # Gemini prompt templates
│   │   ├── stage_score_builder.py   # Stage 3: MIDI generation per segment type
│   │   ├── stage_instrument_mapper.py # Stage 4: MIDI channel/instrument assignment
│   │   └── stage_midi_merger.py     # Stage 5: Merge tracks into final output
│   └── toolcalls/
│       ├── change_pitch.py      # Shift pitch by semitones/octaves
│       ├── change_scale.py      # Transpose to a new key/scale
│       └── main.py              # Tool call dispatcher
├── frontend/
│   └── src/
│       ├── app/page.tsx         # Main page with MIDI loading + editor
│       ├── components/          # UI components (LayerPanel, InstructionsCard, Toolbar, Canvas)
│       ├── hooks/               # useJobPolling, useAudioRecorder
│       ├── stores/              # Zustand editor store (tracks, transport, viewport)
│       └── lib/
│           ├── AudioEngine.ts   # Soundfont-based MIDI playback
│           ├── midi-utils.ts    # MIDI fetch + parse via @tonejs/midi
│           └── constants.ts     # GM instrument names, track colors
├── jobs/                        # Per-job directories (audio + MIDI + debug files)
└── latest-job -> jobs/<uuid>    # Symlink to most recent job
```

## Setup

### Environment Variables

```
GEMINI_API_KEY=<your Google Gemini API key>
```

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && ../.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`, backend on `http://localhost:8000`.

## Pipeline Details

| Stage | Module | What it does |
|-------|--------|-------------|
| 1 | `melody.py` | BasicPitch note extraction with smoothing (filters noise, merges adjacent notes, fills gaps) |
| 2 | `stage_gemini.py` | Gemini classifies audio segments and generates chord progressions per segment |
| 3 | `stage_score_builder.py` | Routes segments to MIDI: dense singing uses BasicPitch notes directly, sparse/beatboxing uses MusicLang |
| 4 | `stage_instrument_mapper.py` | Maps segment types to MIDI channels (singing ch1, beatboxing ch9 drums) |
| 5 | `stage_midi_merger.py` | Combines per-type MIDIs into a single Type 1 multi-track MIDI |

The pipeline retries up to 3 times with backoff if Gemini returns an overload error.

## Tool Calls

Voice instructions trigger tool calls that modify the MIDI in-place:

- **change_pitch** - Shift notes up/down by semitones or octaves on a specific track
- **change_scale** - Detect current key (via music21) and re-map notes to a target scale

Both tools include fallback logic: if the requested track name isn't found, they default to the "singing" track or the first non-drum instrument.