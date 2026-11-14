import csv
import os
from datetime import datetime

import cv2
from deepface import DeepFace

from verify_face import (
    REFERENCE_IMAGE_PATH,
    MODEL_NAME,
    DISTANCE_METRIC,
    capture_current_face,
)
from liveness import run_liveness_check


FACE_LOG_PATH = "face_attempts_log.csv"


def log_face_attempt(tester, distance, threshold, verified):
    """Zapise pokus o overenie tvare do CSV na vyhodnotenie FAR/FRR"""
    new_file = not os.path.exists(FACE_LOG_PATH)
    with open(FACE_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "tester", "distance", "threshold", "verified"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), tester,
                    f"{distance:.4f}", f"{threshold:.4f}", int(verified)])


def verify_identity(tester="owner"):
    """overenie tvare vrati True/False"""
    current_frame = capture_current_face()
    if current_frame is None:
        print("Overenie zrusene.")
        return False

    current_image_path = "current_capture.jpg"
    cv2.imwrite(current_image_path, current_frame)

    try:
        result = DeepFace.verify(
            img1_path=REFERENCE_IMAGE_PATH,
            img2_path=current_image_path,
            model_name=MODEL_NAME,
            distance_metric=DISTANCE_METRIC,
            enforce_detection=True,
        )
    except Exception as e:
        print(f"Chyba pri spracovani: {e}")
        return False
    finally:
        if os.path.exists(current_image_path):
            os.remove(current_image_path)

    print(f"[Krok 1] Vzdialenost: {result['distance']:.4f} "
          f"(prah: {result['threshold']:.4f})")
    log_face_attempt(tester, result["distance"], result["threshold"], result["verified"])
    return bool(result["verified"])


def main():
    if not os.path.exists(REFERENCE_IMAGE_PATH):
        print("Referencna tvar neexistuje")
        return

    print("Krok 1: Overenie tvare")
    if not verify_identity():
        print("Tvar sa nezhoduje")
        return
    print("Tvar sa zhoduje pokracujem na liveness detection\n")

    print("Krok 2: Liveness detection")
    if not run_liveness_check():
        print("liveness test zlyhal")
        return

    print("\ntvar overena aj liveness splneny")
    


if __name__ == "__main__":
    main()
