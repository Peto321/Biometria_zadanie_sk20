"""
Nasnima tvar z webkamery a ulozi ju ako referencnu snimku voci ktorej sa bude neskor overovat pristup
"""

import cv2
import os

REFERENCE_DIR = "reference_faces"
REFERENCE_IMAGE_PATH = os.path.join(REFERENCE_DIR, "owner.jpg")


def main():
    os.makedirs(REFERENCE_DIR, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Nepodarilo sa otvorit webkameru")
        return False

   
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    print("Zatlac MEDZERNIK pre odfotenie alebo ESC pre zrusenie")

    captured_frame = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Chyba pri citani z kamery")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)

        display_frame = frame.copy()
        for (x, y, w, h) in faces:
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.putText(
            display_frame,
            "SPACE = odfotit | ESC = zrusit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Registracia tvare", display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            print("Registracia zrusena")
            break
        elif key == 32:  # SPACE
            if len(faces) == 0:
                print("Nenasla sa ziadna tvar skus to znova")
                continue
            captured_frame = frame
            break

    cap.release()
    cv2.destroyAllWindows()

    if captured_frame is not None:
        cv2.imwrite(REFERENCE_IMAGE_PATH, captured_frame)
        print(f"Referencna tvar bola ulozena do: {REFERENCE_IMAGE_PATH}")
        return True
    return False


if __name__ == "__main__":
    main()
