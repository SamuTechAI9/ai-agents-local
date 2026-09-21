import gc, io, subprocess, threading, time, traceback
from pathlib import Path
import torch
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

VOICE_REF = str(Path(__file__).parent / "mi_voz.wav")
IDLE_SECONDS = 300
model = None
last_used = 0.0
lock = threading.Lock()

def get_model():
    global model
    if model is None:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        print("Cargando modelo en la GPU...")
        model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    return model

def unload_if_idle():
    global model
    while True:
        time.sleep(30)
        with lock:
            if model is not None and time.time() - last_used > IDLE_SECONDS:
                print("Sin uso: liberando la GPU")
                model = None
                gc.collect()
                torch.cuda.empty_cache()

app = FastAPI(title="Voz de Samuel")

class Req(BaseModel):
    text: str
    language_id: str = "es"
    exaggeration: float = 1.25   # emoción: 0.5 normal, 1.0 muy animado
    cfg_weight: float = 0.5     # ritmo: bajarlo hace la voz más lenta
    speed: float = 1.2          # velocidad final: 1.0 normal

@app.post("/synthesize")
def synthesize(req: Req):
    global last_used
    with lock:
        try:
            m = get_model()
            wav = m.generate(text=req.text, language_id=req.language_id,
                             audio_prompt_path=VOICE_REF,
                             exaggeration=req.exaggeration, cfg_weight=req.cfg_weight)
            last_used = time.time()
            buf = io.BytesIO()
            sf.write(buf, wav.squeeze().cpu().numpy(), m.sr, format="WAV")
            speed = min(max(req.speed, 0.5), 2.0)
            ogg = subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-i", "pipe:0",
                 "-filter:a", f"atempo={speed}",
                 "-c:a", "libopus", "-b:a", "48k", "-f", "ogg", "pipe:1"],
                input=buf.getvalue(), capture_output=True, check=True).stdout
            return Response(content=ogg, media_type="audio/ogg")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

threading.Thread(target=unload_if_idle, daemon=True).start()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
