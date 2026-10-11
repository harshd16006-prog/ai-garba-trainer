"""
Teach the AI garba poses from a VIDEO file (instead of dancing yourself).

Put this file in the SAME folder as garba_ai.py, then run:
    python video_refs.py my_dance.mp4

Keys (click on the video window first):
  SPACE  pause / play
  d      next frame (pauses)         a   previous frame (pauses)
  l      jump forward 1 second       j   jump back 1 second
  s      SAVE this pose as a reference
         (then click the Terminal window and type a name, e.g. taali_clap)
  q      quit

Saved poses go into references.json (same file garba_ai.py uses).
"""
import sys
import cv2
from garba_ai import GarbaAI, mp_draw, mp_pose

MAX_WIDTH = 960  # shrink big videos so they fit on screen


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = sys.argv[1]
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit("Cannot open video: " + path)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    ai = GarbaAI(static=True)  # every frame judged on its own

    def read_at(i):
        i = max(0, min(total - 1, i))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        return i, (f if ok else None)

    pos, frame = read_at(0)
    if frame is None:
        sys.exit("Video has no readable frames")

    paused = True      # start paused so you can look around first
    changed = True     # recompute the skeleton only when the frame changes
    angles, shown = None, None

    print(__doc__)
    while True:
        if changed:
            ai.prev = {}  # no smoothing between unrelated frames
            angles = ai.get_angles(frame)
            shown = frame.copy()
            if ai.last_res is not None and ai.last_res.pose_landmarks:
                mp_draw.draw_landmarks(
                    shown, ai.last_res.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            h, w = shown.shape[:2]
            if w > MAX_WIDTH:
                shown = cv2.resize(shown, (MAX_WIDTH, int(h * MAX_WIDTH / w)))
            changed = False

        view = shown.copy()
        status = "PAUSED" if paused else "PLAYING"
        body = "body OK" if angles else "body NOT FOUND"
        color = (0, 255, 0) if angles else (0, 0, 255)
        cv2.putText(view, f"{pos / fps:6.1f}s  {status}  {body}", (15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.imshow("Teach poses from video", view)

        key = cv2.waitKey(30 if paused else 1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
        elif key == ord("d"):
            paused = True
            pos, frame = read_at(pos + 1)
            changed = True
        elif key == ord("a"):
            paused = True
            pos, frame = read_at(pos - 1)
            changed = True
        elif key == ord("l"):
            pos, frame = read_at(pos + int(fps))
            changed = True
        elif key == ord("j"):
            pos, frame = read_at(pos - int(fps))
            changed = True
        elif key == ord("s"):
            if angles:
                name = input("\nName this step (e.g. taali_clap), Enter to cancel: ").strip()
                if name:
                    ai.save_reference(name.replace(" ", "_"), angles)
                    print(f"Saved '{name}' ({len(angles)} joints) -> references.json")
            else:
                print("\nNo body found in this frame - pick another frame.")

        if frame is None:
            break
        if not paused and key not in (ord("l"), ord("j")):
            ok, nxt = cap.read()
            if ok:
                pos += 1
                frame = nxt
                changed = True
            else:
                paused = True  # end of video

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
