import cv2
import sys

def main():
    # On Windows, use DirectShow backend for reliable webcam frames
    if sys.platform == "win32":
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    # Reduce buffer so we get fresh frames; helps on Windows
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Warm up: read a few frames (some webcams need this)
    for _ in range(5):
        cap.read()

    print("Webcam started. Press 'q' or ESC to quit.")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Error: Could not read frame.")
            break

        # Display the frame
        cv2.imshow("Webcam", frame)

        # Quit on 'q' or ESC (key 27)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Webcam closed.")


if __name__ == "__main__":
    main()
