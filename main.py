import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

MODEL_NAME = os.environ.get("WHISPER_MODEL", "base")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")
THREADS = int(os.environ.get("WHISPER_THREADS", "4"))
MAX_AUDIO_MB = int(os.environ.get("MAX_AUDIO_MB", "100"))

model = None

app = FastAPI(title="whisper-webservice", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def load_model():
    global model
    from faster_whisper import WhisperModel

    model = WhisperModel(
        MODEL_NAME, device=DEVICE, compute_type=COMPUTE, cpu_threads=THREADS
    )


def transcribe(path: Path) -> str:
    segments, _info = model.transcribe(str(path), beam_size=5, vad_filter=True)
    return "".join(seg.text for seg in segments).strip()


def transcribe_audio_bytes(data: bytes, suffix: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"audio{suffix}"
        src.write_bytes(data)
        return transcribe(src)


@app.get("/")
def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute": COMPUTE,
    }


@app.post("/api/transcribe")
async def api_transcribe(
    audio_file: UploadFile = File(None),
    url: str = Form(None),
):
    if not audio_file and not url:
        raise HTTPException(400, "envía `audio_file` (multipart) o `url`")

    if url:
        data = await transcribe_url(url, Path(tempfile.gettempdir()))
        return {"text": data}

    raw = await audio_file.read()
    if len(raw) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(413, f"audio mayor a {MAX_AUDIO_MB} MB")
    name = audio_file.filename or "clip.mp3"
    suffix = Path(name).suffix or ".mp3"
    try:
        text = transcribe_audio_bytes(raw, suffix)
    except Exception as e:
        raise HTTPException(500, f"transcripción falló: {e}")
    if not text:
        raise HTTPException(422, "no se detectó voz en el audio")
    return {"text": text}


async def transcribe_url(url: str, workdir: Path) -> str:
    import asyncio
    import subprocess

    outdir = workdir / "whisper-url"
    outdir.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "5",
        "-o",
        str(outdir / "%(id)s.%(ext)s"),
        url,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(502, f"yt-dlp falló: {stderr.decode(errors='ignore')[:500]}")

    candidates = sorted(outdir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(502, "yt-dlp no generó audio")
    return transcribe(candidates[0])