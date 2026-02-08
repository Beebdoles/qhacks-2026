import os
import time

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.upload import router as upload_router, _executor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    print(f"[api] {request.method} {request.url.path} started")
    response = await call_next(request)
    elapsed = time.time() - start
    print(f"[api] {request.method} {request.url.path} completed — {response.status_code} ({elapsed:.2f}s)")
    return response


app.include_router(upload_router)


@app.on_event("startup")
def startup():
    os.makedirs("/tmp/audio_midi_jobs", exist_ok=True)
    print("[startup] Server ready to accept requests")


@app.on_event("shutdown")
def shutdown():
    _executor.shutdown(wait=False, cancel_futures=True)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from FastAPI!"}


# --- Convert audio to MIDI ---


@app.post("/api/convert")
async def convert_to_midi(
    file: UploadFile = File(...),
):
    """Convert an audio file (mp3, wav, etc.) to MIDI using basic-pitch."""
    try:
        audio_bytes = await file.read()
        midi_bytes = await asyncio.to_thread(
            convert_audio_to_midi, audio_bytes, file.filename or "input.mp3"
        )
        output_path = _create_output_midi_path()
        with open(output_path, "wb") as f:
            f.write(midi_bytes)
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="converted.mid",
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")


# --- Auto-tune audio then convert to MIDI ---


@app.post("/api/autotune")
async def autotune_to_midi(
    file: UploadFile = File(...),
    smooth: bool = Form(True),
    min_note_duration: float = Form(0.15),
    merge_gap: float = Form(0.05),
    quantize_bpm: Optional[float] = Form(None),
    quantize_grid: str = Form("sixteenth"),
):
    """Convert audio to MIDI with aggressive anti-jitter smoothing."""
    try:
        audio_bytes = await file.read()
        midi_bytes = await asyncio.to_thread(
            autotune_audio, audio_bytes, file.filename or "input.mp3",
            smooth, min_note_duration, merge_gap, quantize_bpm, quantize_grid,
        )
        output_path = _create_output_midi_path()
        with open(output_path, "wb") as f:
            f.write(midi_bytes)
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="autotuned.mid",
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Auto-tune failed: {e}")


# --- Feature 1: Generate from scratch ---


@app.post("/api/generate")
async def generate_music(request: GenerateRequest):
    try:
        # If a natural language prompt is given, resolve params via LLM first
        if request.prompt:
            from llm_service import interpret_generation_prompt

            gen_params = await interpret_generation_prompt(request.prompt)
            if gen_params.get("chord_progression"):
                request.chord_progression = gen_params["chord_progression"]
            if gen_params.get("tempo"):
                request.tempo = gen_params["tempo"]
            if gen_params.get("temperature"):
                request.temperature = gen_params["temperature"]
            if gen_params.get("nb_tokens"):
                request.nb_tokens = gen_params["nb_tokens"]
            ts = gen_params.get("time_signature")
            if ts and isinstance(ts, (list, tuple)) and len(ts) == 2:
                request.time_signature = tuple(ts)

        async with app.state.predict_lock:
            output_path = await asyncio.to_thread(
                app.state.music_service.generate,
                chord_progression=request.chord_progression,
                nb_tokens=request.nb_tokens,
                temperature=request.temperature,
                topp=request.topp,
                rng_seed=request.rng_seed,
                tempo=request.tempo,
                time_signature=request.time_signature,
            )
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="generated.mid",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


# --- Feature 2: Extend existing MIDI ---


@app.post("/api/extend")
async def extend_music(
    file: UploadFile = File(...),
    nb_tokens: int = Form(512),
    temperature: float = Form(0.9),
    topp: float = Form(1.0),
    rng_seed: int = Form(0),
    tempo: int = Form(120),
    time_signature_numerator: int = Form(4),
    time_signature_denominator: int = Form(4),
):
    try:
        raw_bytes = await file.read()
        midi_bytes = await asyncio.to_thread(
            ensure_midi_bytes, raw_bytes, file.filename or ""
        )
        time_signature = (time_signature_numerator, time_signature_denominator)

        async with app.state.predict_lock:
            output_path = await asyncio.to_thread(
                app.state.music_service.extend,
                midi_bytes=midi_bytes,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
                tempo=tempo,
                time_signature=time_signature,
            )
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="extended.mid",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extension failed: {e}")


# --- Feature 3: Edit via natural language ---


@app.post("/api/edit")
async def edit_music(
    file: UploadFile = File(...),
    instruction: str = Form(...),
    nb_tokens: int = Form(1024),
    temperature: float = Form(0.9),
    topp: float = Form(1.0),
    rng_seed: int = Form(0),
    tempo: int = Form(120),
    time_signature_numerator: int = Form(4),
    time_signature_denominator: int = Form(4),
):
    try:
        raw_bytes = await file.read()
        midi_bytes = await asyncio.to_thread(
            ensure_midi_bytes, raw_bytes, file.filename or ""
        )
        time_signature = (time_signature_numerator, time_signature_denominator)

        # Step 1: Analyze the MIDI for LLM context
        analysis = await asyncio.to_thread(
            app.state.music_service.analyze_midi, midi_bytes
        )

        # Step 2: Interpret the instruction via Gemini
        from llm_service import interpret_edit_instruction

        edit_plan = await interpret_edit_instruction(instruction, analysis)

        # Step 3: Apply the edit plan
        async with app.state.predict_lock:
            output_path = await asyncio.to_thread(
                app.state.music_service.apply_edit,
                midi_bytes=midi_bytes,
                edit_plan=edit_plan,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
                tempo=tempo,
                time_signature=time_signature,
            )
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="edited.mid",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Edit failed: {e}")


# --- Feature 4: Change instrument ---


@app.post("/api/change_instrument")
async def change_instrument(
    file: UploadFile = File(...),
    target_instrument: str = Form(...),
    tempo: int = Form(120),
    time_signature_numerator: int = Form(4),
    time_signature_denominator: int = Form(4),
):
    try:
        raw_bytes = await file.read()
        midi_bytes = await asyncio.to_thread(
            ensure_midi_bytes, raw_bytes, file.filename or ""
        )
        time_signature = (time_signature_numerator, time_signature_denominator)

        output_path = await asyncio.to_thread(
            app.state.music_service.change_instrument,
            midi_bytes=midi_bytes,
            target_instrument=target_instrument,
            tempo=tempo,
            time_signature=time_signature,
        )
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="changed_instrument.mid",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Instrument change failed: {e}")


# --- Feature 5: Arrange (enhance existing MIDI with accompaniment) ---


@app.post("/api/arrange")
async def arrange_music(
    file: UploadFile = File(...),
    target_instrument: Optional[str] = Form(None),
    accompaniment_instruments: Optional[str] = Form(None),
    nb_tokens: int = Form(4096),
    temperature: float = Form(0.9),
    topp: float = Form(1.0),
    rng_seed: int = Form(0),
    tempo: Optional[int] = Form(None),
    time_signature_numerator: Optional[int] = Form(None),
    time_signature_denominator: Optional[int] = Form(None),
):
    """Arrange a MIDI/audio file with auto-detected parameters and LLM-suggested accompaniment."""
    try:
        raw_bytes = await file.read()
        midi_bytes = await asyncio.to_thread(
            ensure_midi_bytes, raw_bytes, file.filename or ""
        )

        # Step 1: Full analysis of the input MIDI
        analysis = await asyncio.to_thread(
            app.state.music_service.analyze_midi_full, midi_bytes
        )

        # Step 2: Get LLM arrangement suggestions
        from llm_service import interpret_arrangement
        arrangement = await interpret_arrangement(analysis)

        # Step 3: Resolve parameters (user override > LLM suggestion > auto-detected)
        if tempo is not None:
            final_tempo = tempo
        elif arrangement.get("tempo") is not None:
            final_tempo = arrangement["tempo"]
        else:
            final_tempo = analysis["tempo"]

        if time_signature_numerator is not None and time_signature_denominator is not None:
            final_time_sig = (time_signature_numerator, time_signature_denominator)
        else:
            final_time_sig = tuple(analysis["time_signature"])

        if accompaniment_instruments:
            acc_list = [i.strip() for i in accompaniment_instruments.split(",")]
        else:
            acc_list = arrangement["accompaniment_instruments"]

        enriched_chords = arrangement.get("chord_progression")

        # Step 4: Generate the arrangement
        async with app.state.predict_lock:
            output_path = await asyncio.to_thread(
                app.state.music_service.arrange,
                midi_bytes=midi_bytes,
                accompaniment_instruments=acc_list,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
                tempo=final_tempo,
                time_signature=final_time_sig,
                chord_progression=enriched_chords,
                target_instrument=target_instrument,
            )
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="arranged.mid",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Arrangement failed: {e}")


# --- Feature 5: Backtrack (generate backing track for a melody) ---


@app.post("/api/backtrack")
async def make_backtrack(
    file: UploadFile = File(...),
    style: Optional[str] = Form(None),
    backing_instruments: Optional[str] = Form(None),
    nb_tokens: int = Form(4096),
    temperature: float = Form(0.9),
    topp: float = Form(1.0),
    rng_seed: int = Form(0),
    tempo: int = Form(120),
    time_signature_numerator: int = Form(4),
    time_signature_denominator: int = Form(4),
):
    try:
        raw_bytes = await file.read()
        midi_bytes = await asyncio.to_thread(
            ensure_midi_bytes, raw_bytes, file.filename or ""
        )
        time_signature = (time_signature_numerator, time_signature_denominator)

        # Resolve backing instruments: explicit list > LLM style > defaults
        if backing_instruments:
            instruments_list = [i.strip() for i in backing_instruments.split(",")]
        elif style:
            from llm_service import interpret_backtrack_style

            style_result = await interpret_backtrack_style(style)
            instruments_list = style_result["instruments"]
        else:
            instruments_list = ["piano", "acoustic_bass", "drums_0"]

        async with app.state.predict_lock:
            output_path = await asyncio.to_thread(
                app.state.music_service.make_backtrack,
                midi_bytes=midi_bytes,
                backing_instruments=instruments_list,
                nb_tokens=nb_tokens,
                temperature=temperature,
                topp=topp,
                rng_seed=rng_seed,
                tempo=tempo,
                time_signature=time_signature,
            )
        return FileResponse(
            output_path,
            media_type="audio/midi",
            filename="backtrack.mid",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Backtrack generation failed: {e}")
