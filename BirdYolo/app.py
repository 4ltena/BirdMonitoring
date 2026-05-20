from fastapi import FastAPI, File, UploadFile, HTTPException
from ultralytics import YOLO
from PIL import Image
import io

app = FastAPI()
model = YOLO("/app/yolov8n.pt")
BIRD_CLASS_ID  = 14
CONF_THRESHOLD = 0.40

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/detect")
async def detect_bird(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="image file required")
    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="cannot decode image")

    bird_detected = False
    confidence    = 0.0
    for result in model(image, verbose=False):
        for box in result.boxes:
            if int(box.cls) == BIRD_CLASS_ID:
                conf = float(box.conf)
                if conf >= CONF_THRESHOLD:
                    bird_detected = True
                    confidence = max(confidence, conf)

    return {"bird_detected": bird_detected, "confidence": round(confidence, 3)}
