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
