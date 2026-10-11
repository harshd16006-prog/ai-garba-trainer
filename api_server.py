"""
Bridge between Flutter and the AI module.
Run:  python api_server.py      (listens on port 8000)

Flutter sends:  POST /analyze   {"image": "<base64 jpeg>"}
Flutter gets:   {"found":true,"step":"taali_clap","score":82.5,"tips":[...], ...}
Other routes:   GET /report   POST /reset   GET /health
"""
import base64, threading
import cv2, numpy as np
from flask import Flask, request, jsonify
from garba_ai import GarbaAI

app = Flask(__name__)
ai = GarbaAI(static=True)
lock = threading.Lock()          # MediaPipe handles one frame at a time


@app.get("/health")
def health():
    return jsonify({"status": "ok", "steps": list(ai.refs.keys())})


@app.post("/analyze")
def analyze():
    data = request.get_json(silent=True) or {}
    if "image" not in data:
        return jsonify({"error": "send JSON with an 'image' base64 field"}), 400
    try:
        raw = base64.b64decode(data["image"].split(",")[-1])
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("bad image")
    except Exception:
        return jsonify({"error": "could not read image"}), 400
    with lock:
        return jsonify(ai.analyze(frame))


@app.get("/report")
def report():
    with lock:
        return jsonify(ai.report())


@app.post("/reset")
def reset():
    with lock:
        ai.reset()
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    # port 8000 because port 5000 is used by macOS AirPlay
    app.run(host="0.0.0.0", port=8000, threaded=True)
