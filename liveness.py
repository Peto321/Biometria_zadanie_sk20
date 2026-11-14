"""
Liveness detection: systém nahodne vyberie vyzvu: usmej sa / zmurkni a overi, ci ju pouzivatel v casovom limite splnil
"""

import os
import random
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)


CHALLENGE_TIMEOUT_S = 10      # kolko sekund na splnenie vyzvy
SMILE_THRESHOLD = 0.5         # priemer mouthSmileLeft/Right nad touto hodnotou = usmev
SMILE_FRAMES_REQUIRED = 5     # usmev musi trvat aspon tolko framov po sebe
BLINK_CLOSED_THRESHOLD = 0.5  # eyeBlink nad touto hodnotou = oci zatvorene
BLINK_OPEN_THRESHOLD = 0.3    # eyeBlink pod touto hodnotou = oci otvorene
NUM_CHALLENGES = 1            # kolko nahodnych vyziev po sebe sa ma splnit

CHALLENGES = {
    "SMILE": "Usmej sa",
    "BLINK": "Zmurkni",
}


def ensure_model():
    """Stiahne model pre MediaPipe ak nie je na disku"""
    if os.path.exists(MODEL_PATH):
        return
    os.makedirs(MODEL_DIR, exist_ok=True)
    print("Stahujem MediaPipe model")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Model stiahnuty")


def create_landmarker():
    ensure_model()
    options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        output_face_blendshapes=True,
        num_faces=1,
    )
    return vision.FaceLandmarker.create_from_options(options)


def get_blendshapes(landmarker, frame_bgr):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)
    if not result.face_blendshapes:
        return None
    return {c.category_name: c.score for c in result.face_blendshapes[0]}


def smile_score(bs):
    return (bs.get("mouthSmileLeft", 0) + bs.get("mouthSmileRight", 0)) / 2


def blink_score(bs):
    return (bs.get("eyeBlinkLeft", 0) + bs.get("eyeBlinkRight", 0)) / 2


def run_challenge(cap, landmarker, challenge):
    """Spusti jednu vyzvu, vrati True ak bola splnena v case inak False"""
    start = time.time()
    smile_frames = 0
    eyes_were_open = False  

    while True:
        elapsed = time.time() - start
        remaining = CHALLENGE_TIMEOUT_S - elapsed
        if remaining <= 0:
            return False

        ret, frame = cap.read()
        if not ret:
            return False

        bs = get_blendshapes(landmarker, frame)
        passed = False
        status = "Hladam tvar"

        if bs is not None:
            status = ""
            if challenge == "SMILE":
                s = smile_score(bs)
                smile_frames = smile_frames + 1 if s > SMILE_THRESHOLD else 0
                status = f"usmev: {s:.2f}"
                if smile_frames >= SMILE_FRAMES_REQUIRED:
                    passed = True
            elif challenge == "BLINK":
                b = blink_score(bs)
                status = f"zmurknutie: {b:.2f}"
                if b < BLINK_OPEN_THRESHOLD:
                    eyes_were_open = True
                if eyes_were_open and b > BLINK_CLOSED_THRESHOLD:
                    passed = True

        display = frame.copy()
        cv2.putText(display, CHALLENGES[challenge], (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        cv2.putText(display, f"Cas: {remaining:.0f}s  {status}", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Liveness detection", display)

        if passed:
            return True
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            return False


def run_liveness_check():
    """Vrati True ak pouzivatel splnil vsetky nahodne vyzvy"""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Nepodarilo sa otvorit webkameru")
        return False

    landmarker = create_landmarker()
    chosen = random.sample(list(CHALLENGES.keys()),
                           k=min(NUM_CHALLENGES, len(CHALLENGES)))
    print(f"Liveness vyzvy: {chosen}")

    success = True
    for challenge in chosen:
        if not run_challenge(cap, landmarker, challenge):
            success = False
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    return success


if __name__ == "__main__":
    ok = run_liveness_check()
    print("LIVENESS OK" if ok else "LIVENESS ZLYHALO")
