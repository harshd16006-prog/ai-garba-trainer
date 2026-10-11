"""
AI Garba Trainer - Member 3 (AI module)

Usage (inside your venv):
  python garba_ai.py record taali_clap    # teach the AI one reference pose
  python garba_ai.py train                # live practice with score + corrections
"""
import cv2, json, os, sys, time
import numpy as np
import mediapipe as mp

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
L = mp_pose.PoseLandmark

# A "joint" = 3 body points. The angle at the MIDDLE point is what we measure.
JOINTS = {
    "left_elbow":     (L.LEFT_SHOULDER,  L.LEFT_ELBOW,  L.LEFT_WRIST),
    "right_elbow":    (L.RIGHT_SHOULDER, L.RIGHT_ELBOW, L.RIGHT_WRIST),
    "left_shoulder":  (L.LEFT_ELBOW,     L.LEFT_SHOULDER,  L.LEFT_HIP),
    "right_shoulder": (L.RIGHT_ELBOW,    L.RIGHT_SHOULDER, L.RIGHT_HIP),
    "left_hip":       (L.LEFT_SHOULDER,  L.LEFT_HIP,   L.LEFT_KNEE),
    "right_hip":      (L.RIGHT_SHOULDER, L.RIGHT_HIP,  L.RIGHT_KNEE),
    "left_knee":      (L.LEFT_HIP,       L.LEFT_KNEE,  L.LEFT_ANKLE),
    "right_knee":     (L.RIGHT_HIP,      L.RIGHT_KNEE, L.RIGHT_ANKLE),
}

TOLERANCE = 40   # degrees of error that gives 0 points for a joint
WRONG_AT = 25    # error above this = "incorrect movement"


def calc_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba, bc = a - b, c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))


# Tips in 3 languages: English (en), Hindi (hi), Gujarati (gu).
# Words for the voice coach. Check the Hindi/Gujarati once with a native speaker.
SIDE = {
    "left":  {"en": "left",  "hi": "बायाँ", "gu": "ડાબો"},
    "right": {"en": "right", "hi": "दायाँ", "gu": "જમણો"},
}
SIDE_F = {   # feminine form (elbow = kohni / koni)
    "left":  {"hi": "बायीं", "gu": "ડાબી"},
    "right": {"hi": "दायीं", "gu": "જમણી"},
}
PRAISE = {"en": "Great! Keep going", "hi": "शाबाश! ऐसे ही करते रहो",
          "gu": "શાબાશ! આમ જ ચાલુ રાખો"}


def make_tip(joint, diff):
    """English tip. diff = user angle - reference angle."""
    return make_tip_i18n(joint, diff)["en"]


# Tips in 3 languages (en / hi / gu) so the app can show AND speak them.
SIDE = {"left":  {"en": "left",  "hi_f": "बायीं", "hi_m": "बायां", "gu_f": "ડાબી",  "gu_m": "ડાબો"},
        "right": {"en": "right", "hi_f": "दायीं", "hi_m": "दायां", "gu_f": "જમણી", "gu_m": "જમણો"}}


def make_tip_i18n(joint, diff):
    """Returns {"en": ..., "hi": ..., "gu": ...}. diff = user angle - reference angle."""
    side, part = joint.split("_")
    more = diff > 0
    s = SIDE[side]
    if part == "elbow":
        return {
            "en": f"{'Bend' if more else 'Straighten'} your {s['en']} elbow",
            "hi": f"{s['hi_f']} कोहनी {'मोड़ो' if more else 'सीधी करो'}",
            "gu": f"{s['gu_f']} કોણી {'વાળો' if more else 'સીધી કરો'}",
        }
    if part == "shoulder":
        return {
            "en": f"{'Lower' if more else 'Raise'} your {s['en']} arm",
            "hi": f"{s['hi_m']} हाथ {'नीचे करो' if more else 'ऊपर उठाओ'}",
            "gu": f"{s['gu_m']} હાથ {'નીચે કરો' if more else 'ઉપર ઉઠાવો'}",
        }
    if part == "knee":
        return {
            "en": f"{'Bend' if more else 'Straighten'} your {s['en']} knee",
            "hi": f"{s['hi_m']} घुटना {'मोड़ो' if more else 'सीधा करो'}",
            "gu": f"{s['gu_m']} ઘૂંટણ {'વાળો' if more else 'સીધો કરો'}",
        }
    if more:
        return {"en": "Bend forward a little", "hi": "थोड़ा आगे झुको", "gu": "થોડા આગળ નમો"}
    return {"en": "Stand more upright", "hi": "सीधे खड़े रहो", "gu": "સીધા ઊભા રહો"}


def grade(score):
    if score >= 85: return "Excellent"
    if score >= 70: return "Good"
    if score >= 50: return "Okay - keep practicing"
    return "Needs work"


class GarbaAI:
    def __init__(self, ref_file="references.json", static=False):
        self.pose = mp_pose.Pose(static_image_mode=static, model_complexity=1,
                                 min_detection_confidence=0.5,
                                 min_tracking_confidence=0.5)
        self.ref_file = ref_file
        self.refs = json.load(open(ref_file)) if os.path.exists(ref_file) else {}
        self.prev = {}
        self.log = []
        self.last_res = None

    # ---- 1. Pose detection ----
    def get_angles(self, bgr):
        h, w = bgr.shape[:2]
        res = self.pose.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        self.last_res = res
        if not res.pose_landmarks:
            return None
        lm = res.pose_landmarks.landmark
        out = {}
        for name, trio in JOINTS.items():
            pts = [lm[p.value] for p in trio]
            if min(p.visibility for p in pts) < 0.5:
                continue
            ang = calc_angle(*[(p.x * w, p.y * h) for p in pts])
            if name in self.prev:                      # smooth shaky numbers
                ang = 0.6 * ang + 0.4 * self.prev[name]
            self.prev[name] = ang
            out[name] = ang
        return out or None

    # ---- 2. Step recognition: closest saved reference pose ----
    # A step can have ONE saved pose (a dict) or MANY (a list of dicts, e.g.
    # extracted from a video). We pick the single closest saved pose.
    def recognize(self, ang):
        best, best_ref, best_err = None, None, 1e9
        for step, saved in self.refs.items():
            variants = saved if isinstance(saved, list) else [saved]
            for ref in variants:
                common = [j for j in ref if j in ang]
                if len(common) < 4:
                    continue
                err = np.mean([abs(ang[j] - ref[j]) for j in common])
                if err < best_err:
                    best, best_ref, best_err = step, ref, err
        return best, best_ref

    # ---- 3. Compare + score + wrong moves + tips ----
    def analyze(self, bgr):
        ang = self.get_angles(bgr)
        if ang is None:
            return {"found": False, "message": "Stand fully in view of the camera"}
        step, ref = self.recognize(ang)
        if step is None:
            return {"found": True, "step": None, "score": 0, "wrong": [], "tips": [],
                    "angles": {k: round(v, 1) for k, v in ang.items()},
                    "message": "No reference poses saved yet"}
        common = [j for j in ref if j in ang]
        errs = {j: ang[j] - ref[j] for j in common}
        score = float(np.mean([max(0, 1 - abs(e) / TOLERANCE) for e in errs.values()]) * 100)
        bad = sorted([j for j, e in errs.items() if abs(e) > WRONG_AT],
                     key=lambda j: -abs(errs[j]))
        tip_dicts = [make_tip_i18n(j, errs[j]) for j in bad[:2]]
        tips = [t["en"] for t in tip_dicts]
        tips_i18n = {lang: [t[lang] for t in tip_dicts] for lang in ("en", "hi", "gu")}
        self.log.append({"t": time.time(), "step": step, "score": score, "wrong": bad})
        out = {"found": True, "step": step, "score": round(score, 1), "grade": grade(score),
               "wrong": bad, "tips": tips, "tips_i18n": tips_i18n,
               "angles": {k: round(v, 1) for k, v in ang.items()}}
        if not tips and score >= 70:
            out["praise"] = PRAISE
        return out

    # ---- 4. Performance report ----
    def report(self):
        if not self.log:
            return {"frames": 0}
        scores = [x["score"] for x in self.log]
        wrong_count, step_count = {}, {}
        for x in self.log:
            step_count[x["step"]] = step_count.get(x["step"], 0) + 1
            for j in x["wrong"]:
                wrong_count[j] = wrong_count.get(j, 0) + 1
        avg = float(np.mean(scores))
        return {
            "frames": len(scores),
            "average_score": round(avg, 1),
            "best_score": round(max(scores), 1),
            "worst_score": round(min(scores), 1),
            "grade": grade(avg),
            "steps_practiced": step_count,
            "weakest_joints": sorted(wrong_count, key=wrong_count.get, reverse=True)[:3],
        }

    def reset(self):
        self.log, self.prev = [], {}

    def save_reference(self, name, angles):
        self.refs[name] = {k: round(v, 1) for k, v in angles.items()}
        json.dump(self.refs, open(self.ref_file, "w"), indent=2)

    def add_references(self, name, angle_list):
        """Save MANY poses for one step (used by extract_poses.py)."""
        self.refs[name] = [{k: round(v, 1) for k, v in a.items()} for a in angle_list]
        json.dump(self.refs, open(self.ref_file, "w"), indent=2)


# ---------------- Camera app (OpenCV) ----------------
def run_record(step_name):
    ai, cap = GarbaAI(), cv2.VideoCapture(0)
    if not cap.isOpened():
        sys.exit("Camera not opening. Allow Terminal/VS Code in System Settings > Privacy > Camera")
    start, samples = time.time(), []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        left = 5 - (time.time() - start)
        if left > 0:
            ai.get_angles(frame)
            if ai.last_res.pose_landmarks:
                mp_draw.draw_landmarks(frame, ai.last_res.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            frame = cv2.flip(frame, 1)
            cv2.putText(frame, f"Get into '{step_name}' pose: {int(left) + 1}", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        else:
            ang = ai.get_angles(frame)
            if ang:
                samples.append(ang)
            frame = cv2.flip(frame, 1)
            cv2.putText(frame, "Hold still...", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            if len(samples) >= 20:
                break
        cv2.imshow("Record reference", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release(); cv2.destroyAllWindows()
    if samples:
        keys = set.intersection(*[set(s) for s in samples])
        ai.save_reference(step_name, {k: np.mean([s[k] for s in samples]) for k in keys})
        print(f"Saved reference '{step_name}' with {len(keys)} joints -> references.json")
    else:
        print("Nothing saved - body not detected.")


def run_train():
    ai, cap = GarbaAI(), cv2.VideoCapture(0)
    if not ai.refs:
        sys.exit("No references yet. Run: python garba_ai.py record <step_name>")
    if not cap.isOpened():
        sys.exit("Camera not opening. Allow Terminal/VS Code in System Settings > Privacy > Camera")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        r = ai.analyze(frame)                       # analyze the NORMAL frame (left/right stay correct)
        if ai.last_res.pose_landmarks:
            mp_draw.draw_landmarks(frame, ai.last_res.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        frame = cv2.flip(frame, 1)                  # mirror only for display
        if r["found"] and r.get("step"):
            s = r["score"]
            color = (0, 200, 0) if s >= 70 else (0, 165, 255) if s >= 50 else (0, 0, 255)
            cv2.putText(frame, f"Step: {r['step']}   Score: {s:.0f}  {r['grade']}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            for i, t in enumerate(r["tips"]):
                cv2.putText(frame, t, (20, 80 + 35 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        else:
            cv2.putText(frame, r.get("message", ""), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, "q = finish + report", (20, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imshow("AI Garba Trainer", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release(); cv2.destroyAllWindows()
    rep = ai.report()
    json.dump(rep, open("report.json", "w"), indent=2)
    print("\n===== PERFORMANCE REPORT =====")
    for k, v in rep.items():
        print(f"{k}: {v}")
    print("Saved to report.json")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "record":
        run_record(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "train":
        run_train()
    else:
        print(__doc__)
