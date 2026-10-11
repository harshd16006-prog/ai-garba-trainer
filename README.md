# AI Garba Trainer - AI Module (Member 3)

Camera-based garba pose trainer. It detects the human body, compares the user's
joint angles with saved reference poses, gives a live score, tells the user what
to correct, and produces a performance report. A small REST API lets the Flutter
app use all of this.

**Tech:** Python, MediaPipe Pose, OpenCV, NumPy, Flask.

## How it works

```
Flutter app (phone)  --photo-->  api_server.py (laptop)  -->  garba_ai.py
   shows score/tips  <--JSON---                               MediaPipe + angles
```

1. MediaPipe finds 33 body landmarks in each camera frame.
2. We measure 8 joint angles (both elbows, shoulders, hips, knees).
3. Angles are compared with the saved reference poses in `references.json`.
4. The closest pose is the recognised step; the angle difference gives a 0-100 score.
5. Joints that are off by more than 25 degrees are flagged and turned into tips
   such as "Bend your left elbow".
6. At the end of a session a report is produced (average / best / worst score,
   steps practiced, weakest joints).

## Files

| File | Purpose |
|---|---|
| `garba_ai.py` | The AI: pose detection, scoring, tips, report. Also the live camera app (`record` and `train` commands). |
| `api_server.py` | Flask server so Flutter can use the AI. |
| `video_refs.py` | Teach reference poses by hand from a video file or from screenshot images. |
| `extract_poses.py` | Learn MANY poses of a step automatically from a video (k-means picks the typical poses). |
| `references.json` | The saved reference poses (joint angles). |
| `requirements.txt` | Python dependencies (versions are pinned on purpose). |
| `flutter_module/` | Drop-in Flutter folder `lib/garba_ai/` with the camera screen and report screen. |

## Setup (Windows, PowerShell)

Python **3.11** is required (MediaPipe does not work on the newest Python versions).

```powershell
py -3.11 -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If scripts are blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

macOS / Linux: `python3.11 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

> Note: the pinned MediaPipe 0.10.21 is intentional. Newer MediaPipe versions
> removed the `mp.solutions` API that this code uses.

## Teach reference poses

Stand 2-3 m back so the whole body (head to feet) is visible, in good light.

```powershell
python garba_ai.py record taali_clap      # 5 s countdown, then hold still
python garba_ai.py record arms_up
```
From a video or screenshots instead of dancing yourself:
```powershell
python video_refs.py dance.mp4
python video_refs.py pose1.png pose2.png
```
Automatically from a video (recommended - more poses means better recognition):
```powershell
python extract_poses.py dance.mp4 taali_step --poses 8
```
It samples the video, keeps frames where the body is clearly visible, groups similar
frames with k-means and stores the most typical pose of each group. A step can have
many reference poses; the user is matched to the closest one. Pictures of the chosen
poses are saved in `poses_<name>/`. Use `--split` to store each pose as its own step.

Poses are stored in `references.json`.

## Try it live (laptop webcam)

```powershell
python garba_ai.py train
```
Press `q` to finish and print the performance report (also saved to `report.json`).

## Run the API for the Flutter app

```powershell
python api_server.py          # listens on 0.0.0.0:8000
```
Allow Python through the firewall (Private networks) when Windows asks.
Find the laptop IP with `ipconfig` (IPv4 of the Wi-Fi adapter). The phone and the
laptop must be on the same network. Quick check from the phone browser:
`http://<laptop-ip>:8000/health`

### API

| Method | Route | Body / result |
|---|---|---|
| GET | `/health` | `{"status":"ok","steps":["taali_clap", ...]}` |
| POST | `/analyze` | Body `{"image": "<base64 JPEG>"}`. Returns `{"found":true,"step":"taali_clap","score":82.5,"grade":"Good","wrong":["left_elbow"],"tips":["Bend your left elbow"],"tips_i18n":{"en":[...],"hi":[...],"gu":[...]},"angles":{...}}`. If no body: `{"found":false,"message":"Stand fully in view of the camera"}` |
| GET | `/report` | `{"frames":120,"average_score":74.3,"best_score":96.1,"worst_score":31.0,"grade":"Good","steps_practiced":{...},"weakest_joints":[...]}` |
| POST | `/reset` | Starts a fresh session (clears the report) |

## Flutter integration

The folder `flutter_module/.../lib/garba_ai/` is self-contained (own camera,
own HTTP calls, own report screen). All class names start with `GarbaAi`, so they
should not clash with existing code.

1. Copy `lib/garba_ai/` into the app's `lib/`.
2. `flutter pub add camera http flutter_tts`
3. Android: in `AndroidManifest.xml` add
   `<uses-permission android:name="android.permission.CAMERA"/>`,
   `<uses-permission android:name="android.permission.INTERNET"/>`
   and `android:usesCleartextTraffic="true"` on `<application>`; set `minSdk` to 24.
4. Open the screen from any button:
```dart
import 'garba_ai/garba_ai.dart';

Navigator.push(context,
  MaterialPageRoute(builder: (_) => const GarbaAiTrainerScreen()));
```
5. Set the server address in `lib/garba_ai/garba_ai_config.dart`, or inside the app
   with the settings icon on the camera screen (no rebuild needed).
6. `flutter build apk --release`

The camera screen has a language menu (English / Hindi / Gujarati) and a voice
on/off button: tips are spoken aloud. The server returns `tips_i18n` with every
`/analyze` answer. Android 11+ needs a `<queries>` entry for text-to-speech, see
`README_MODULE.md`.

Full details: `flutter_module/README_MODULE.md`.

## Known limitations

- The AI runs on a computer (client-server design); the app needs the server to be
  reachable on the network.
- Scoring compares individual poses using 2D joint angles, so a front-facing camera
  and a fully visible body give the best results. Garba is movement over time; this
  version recognises key poses of each step.
- Reference poses with few visible joints (for example legs out of frame) are less
  reliable. Record references with the full body in view.
