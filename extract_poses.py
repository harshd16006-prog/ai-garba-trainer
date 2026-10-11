"""
Learn many poses of one garba step AUTOMATICALLY from a video.

Run (inside the venv, in the garba_ai folder):

    python extract_poses.py dance.mp4 taali_step
    python extract_poses.py dance.mp4 taali_step --poses 10
    python extract_poses.py routine.mp4 dodhiyu --split

What it does:
  1. Looks at the video every ~0.3 s and measures the body angles.
  2. Keeps only moments where the dancer's body is clearly visible.
  3. Groups similar moments together (k-means) and keeps the most typical
     pose of each group.
  4. Saves them into references.json. The AI then recognises the step if the
     user matches ANY of those poses, so more poses = better recognition.
  5. Saves a picture of every chosen pose in the folder  poses_<name>/
     so you can look at them and delete bad ones.

Options:
  --poses N   how many different poses to keep (default 8)
  --split     save each pose as its own step: name_1, name_2, ...
              (use for a long routine video)
Tips for good videos: ONE dancer, camera in FRONT, whole body visible,
camera not moving, plain background.
"""
import os
import sys
import cv2
import numpy as np
from garba_ai import GarbaAI, mp_draw, mp_pose, JOINTS

SAMPLE_EVERY_SEC = 0.3
MAX_FRAMES = 800          # never analyse more than this many frames
MIN_JOINTS = 6            # a frame needs at least this many visible joints
JOINT_NAMES = list(JOINTS.keys())


# ---------- pure maths (no camera / video needed) ----------
def to_matrix(angle_dicts):
    """list of {joint: angle} -> (matrix, mask). Missing joints are filled
    with that joint's median so every row has the same length."""
    n, m = len(angle_dicts), len(JOINT_NAMES)
    X = np.full((n, m), np.nan)
    for i, a in enumerate(angle_dicts):
        for j, name in enumerate(JOINT_NAMES):
            if name in a:
                X[i, j] = a[name]
    med = np.nanmedian(X, axis=0)
    med = np.where(np.isnan(med), 90.0, med)
    X = np.where(np.isnan(X), med, X)
    return X


def kmeans(X, k, iters=40, seed=0):
    """Tiny k-means with k-means++ start. Returns (labels, centers)."""
    rng = np.random.default_rng(seed)
    n = len(X)
    k = max(1, min(k, n))
    centers = [X[rng.integers(n)]]
    for _ in range(1, k):
        d2 = np.min([((X - c) ** 2).sum(axis=1) for c in centers], axis=0)
        total = d2.sum()
        if total <= 0:
            centers.append(X[rng.integers(n)])
        else:
            centers.append(X[rng.choice(n, p=d2 / total)])
    centers = np.array(centers, dtype=float)
    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        dist = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new = dist.argmin(axis=1)
        if np.array_equal(new, labels) and _ > 0:
            break
        labels = new
        for c in range(k):
            members = X[labels == c]
            if len(members):
                centers[c] = members.mean(axis=0)
    return labels, centers


def pick_poses(angle_dicts, k):
    """Return indices of the most typical real frame of each pose group,
    biggest group first."""
    X = to_matrix(angle_dicts)
    labels, centers = kmeans(X, k)
    picked = []
    for c in range(len(centers)):
        idx = np.where(labels == c)[0]
        if len(idx) == 0:
            continue
        d = ((X[idx] - centers[c]) ** 2).sum(axis=1)
        picked.append((len(idx), int(idx[d.argmin()])))
    picked.sort(reverse=True)
    return [i for _, i in picked]


# ---------- video ----------
def read_video(path, ai):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit("Cannot open video: " + path +
                 "\n(Is the file inside this folder? Check with: dir)")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    step = max(1, int(round(fps * SAMPLE_EVERY_SEC)))
    if total and total / step > MAX_FRAMES:
        step = int(np.ceil(total / MAX_FRAMES))

    frames, seen = [], 0
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            seen += 1
            ai.prev = {}                      # no smoothing between samples
            ang = ai.get_angles(frame)
            if ang and len(ang) >= MIN_JOINTS:
                shown = frame.copy()
                mp_draw.draw_landmarks(
                    shown, ai.last_res.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                frames.append((ang, shown, i / fps))
        i += 1
        if seen % 50 == 0 and seen:
            print(f"  ...looked at {seen} moments, {len(frames)} usable")
    cap.release()
    return frames, seen


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return
    split = "--split" in args
    k = 8
    if "--poses" in args:
        try:
            k = int(args[args.index("--poses") + 1])
        except (ValueError, IndexError):
            sys.exit("Use it like:  --poses 10")
    pos = [a for a in args if not a.startswith("--") and not a.isdigit()]
    if len(pos) < 2:
        print(__doc__)
        return
    video, name = pos[0], pos[1].replace(" ", "_")

    ai = GarbaAI(static=True)
    print(f"Reading {video} ...")
    frames, seen = read_video(video, ai)
    print(f"Looked at {seen} moments, {len(frames)} had a clearly visible body.")
    if len(frames) < 5:
        sys.exit("Too few usable moments. Use a video where one dancer is "
                 "fully visible from the front.")

    idx = pick_poses([f[0] for f in frames], k)
    chosen = [frames[i] for i in idx]

    out_dir = "poses_" + name
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        if old.endswith(".jpg"):
            os.remove(os.path.join(out_dir, old))
    for n, (ang, img, t) in enumerate(chosen, 1):
        h, w = img.shape[:2]
        if w > 640:
            img = cv2.resize(img, (640, int(h * 640 / w)))
        cv2.imwrite(os.path.join(out_dir, f"pose_{n}.jpg"), img)

    if split:
        for n, (ang, _, _) in enumerate(chosen, 1):
            ai.save_reference(f"{name}_{n}", ang)
        print(f"\nSaved {len(chosen)} separate steps: {name}_1 ... {name}_{len(chosen)}")
    else:
        ai.add_references(name, [c[0] for c in chosen])
        print(f"\nSaved {len(chosen)} poses for step '{name}' -> references.json")
    print(f"Pictures of the chosen poses are in the folder: {out_dir}")
    print("Open them. Bad ones can be ignored, or run again with a cleaner video.")
    print("Now test:  python garba_ai.py train")


if __name__ == "__main__":
    main()
