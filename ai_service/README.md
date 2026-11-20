# Real camera inference

See the root README for installation and authentication. The software-only college demonstration uses the main app simulator; no YOLO weights are required for that flow.

For real inference, install these requirements, supply trained local YOLO weights via YOLO_MODEL_PATH, and set AI_WEBHOOK_SECRET in the root .env. From the project root run:

    .venv\Scripts\python.exe -m uvicorn ai_service.detector:app --port 8100

Send multipart latitude, longitude and image to POST /detect with the x-ai-key header. The service validates coordinates and image size, opens temporary files safely on Windows, and forwards one detection per recognized class per frame. Continuous-stream deduplication and camera capture remain separate integration work.
