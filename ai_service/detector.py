"""Optional real YOLO bridge. Demonstrations use /api/demo/events instead."""
import math
import os
import tempfile
from pathlib import Path
from threading import Lock
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
import secrets

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
API_URL = os.getenv('FORESTGUARD_API_URL', 'http://localhost:8000/api/ai/detections')
AI_KEY = os.getenv('AI_WEBHOOK_SECRET', '')
MODEL_PATH = os.getenv('YOLO_MODEL_PATH', str(Path(__file__).parent / 'forestguard.pt'))
MIN_CONF = float(os.getenv('YOLO_CONFIDENCE', '0.50'))
model = None
model_lock = Lock()
app = FastAPI(title='VanRakshak YOLO Detection Bridge')

@app.get('/health')
def health():
    return {'status': 'ready' if Path(MODEL_PATH).is_file() else 'model_missing', 'modelLoaded': model is not None}

@app.post('/detect')
def detect(latitude: float = Form(...), longitude: float = Form(...), image: UploadFile = File(...), x_ai_key: str | None = Header(default=None)):
    global model
    if not AI_KEY: raise HTTPException(503, 'AI_WEBHOOK_SECRET is not configured.')
    if not secrets.compare_digest(x_ai_key or '', AI_KEY): raise HTTPException(401, 'Invalid camera credentials.')
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90<=latitude<=90 or not -180<=longitude<=180:
        raise HTTPException(400, 'Invalid GPS coordinates.')
    if image.content_type not in {'image/jpeg','image/png','image/webp'}:
        raise HTTPException(400, 'Upload a JPEG, PNG or WebP image.')
    raw=image.file.read(12*1024*1024+1)
    if len(raw)>12*1024*1024: raise HTTPException(413, 'Frame must be smaller than 12 MB.')
    if not raw: raise HTTPException(400, 'Image is empty.')
    if not Path(MODEL_PATH).is_file(): raise HTTPException(503, 'Trained YOLO weights are missing. Configure YOLO_MODEL_PATH.')
    with model_lock:
        if model is None:
            from ultralytics import YOLO
            model=YOLO(MODEL_PATH)
        # Close the file before inference; Windows prevents reopening an open temporary file.
        with tempfile.TemporaryDirectory() as directory:
            frame=Path(directory)/'frame.jpg'
            frame.write_bytes(raw)
            try: result=model.predict(str(frame),conf=MIN_CONF,verbose=False)[0]
            except Exception: raise HTTPException(422, 'Could not decode or process this image.')
    accepted={'forest_fire','smoke','illegal_logging','tree_cutting','wildlife','human'}
    detections={}
    for box in result.boxes:
        label=str(result.names[int(box.cls[0])]).lower().strip().replace(' ','_').replace('-','_')
        if label=='person': label='human'
        if label in accepted: detections[label]=max(detections.get(label,0),float(box.conf[0]))
    sent=[]
    for label,confidence in detections.items():
        try:
            response=requests.post(API_URL,json={'label':label,'confidence':confidence,'latitude':latitude,'longitude':longitude,'description':f'YOLO detection; confidence {confidence:.3f}. Human activity requires officer verification.'},headers={'x-ai-key':AI_KEY},timeout=15)
            response.raise_for_status()
            sent.append(response.json())
        except (requests.RequestException,ValueError): raise HTTPException(502, 'The incident API could not accept the detection.')
    return {'detections_created':len(sent),'results':sent}
