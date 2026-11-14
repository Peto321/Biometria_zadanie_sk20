"""
Nasnima tvar z webkamery a porovna ju s ulozenou referencnou tvarou 
"""

import cv2
import os
from deepface import DeepFace

REFERENCE_IMAGE_PATH = os.path.join("reference_faces", "owner.jpg")

MODEL_NAME = "Facenet"
DISTANCE_METRIC = "cosine"


def capture_current_face():
    """Odfoti snimku z webkamery po stlaceni medzernika"""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Nepodarilo sa otvorit webkameru")
        return None

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    print("Zatlac MEDZERNIK pre overenie, alebo ESC pre zrusenie")
    captured_frame = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)

        display_frame = frame.copy()
        for (x, y, w, h) in faces:
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.putText(
            display_frame,
            "SPACE = overit | ESC = zrusit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Overenie tvare", display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        elif key == 32:
            if len(faces) == 0:
                print("Tvar sa nenasla")
                continue
            captured_frame = frame
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured_frame


def main():
    if not os.path.exists(REFERENCE_IMAGE_PATH):
        print("Referencna tvar neexistuje")
        return

    current_frame = capture_current_face()
    if current_frame is None:
        print("Overenie zrusene.")
        return

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
        return

    print("-" * 40)
    print(f"distance: {result['distance']:.4f}")
    print(f"threshold: {result['threshold']:.4f}")

    if result["verified"]:
        print("Tvar sa zhoduje")
    else:
        print("Tvar sa nezhoduje")
    print("-" * 40)

    os.remove(current_image_path)


if __name__ == "__main__":
    main()
