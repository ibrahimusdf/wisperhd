# whisper-render

Servicio de transcripción (faster-whisper) listo para Render, compatible con el cliente node.

## Endpoints

- `GET /` — health + modelo cargado.
- `POST /api/transcribe`:
  - multipart `audio_file=<archivo>` (compatible con `pipeline-transcribe.mjs`), **o**
  - form `url=<video/x>` (floegra con yt-dlp + ffmpeg).
  - Respuesta JSON: `{"text": "..."}`.

## Deploy en Render

1. Subí esta carpeta a un repo (git) y en Render → New → Blueprint usá `render.yaml`
   (o New Web Service con runtime Docker apuntando al repo).
2. Primer boot descarga el modelo de HuggingFace (tarda unos minutos).
3. Base URL resultante, p. ej. `https://whisper-webservice.onrender.com`.

## Probar

```bash
curl -F "audio_file=@clip.mp3" https://<tu-servicio>.onrender.com/api/transcribe
```

## Pipeline node (cliente)

```powershell
$env:WHISPER_URL="https://<tu-servicio>.onrender.com/api/transcribe"
node pipeline-transcribe.mjs   # resumible: mp3 ya cacheados se re-transcriben solos
```

## Notas / rendimiento (plan Free: 0.1 CPU, 512 MB)

- `base` (default): ~74 MB RAM int8, ~1–3 min por clip de 1–2 min. Es lo más seguro para el plan Free.
- Si querés más precisión: cambia `WHISPER_MODEL=small` (~486 MB, lento en CPU Free).
- Los cold starts vuelven a descargar el modelo (sin disco persistente en Free).
- El pool de `media/audio/*.mp3` ya extraído por el pipeline local se reutiliza;
  solo se re-suben los que faltan transcribir.