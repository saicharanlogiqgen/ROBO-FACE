"""
Simple Camera Test Script
Tests if camera is accessible and face detection works
"""

import cv2
import os

def test_camera():
    """Test camera access and face detection"""
    
    print("=" * 50)
    print("Camera Test Script")
    print("=" * 50)
    
    # Test 1: Load Haar Cascade
    print("\n[1] Loading face detector...")
    try:
        # Try local file first
        local_cascade = "haarcascade_frontalface_default.xml"
        if os.path.exists(local_cascade):
            cascade_path = local_cascade
            print(f"   Using local file: {cascade_path}")
        else:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            print(f"   Using OpenCV built-in: {cascade_path}")
        
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            print("   ❌ ERROR: Could not load cascade file!")
            return False
        print("   ✓ Face detector loaded successfully")
    except Exception as e:
        print(f"   ❌ ERROR loading face detector: {e}")
        return False
    
    # Test 2: Try to open camera
    print("\n[2] Testing camera access...")
    camera = None
    camera_index = None
    
    for i in range(5):  # Try cameras 0-4
        print(f"   Trying camera index {i}...")
        try:
            test_cam = cv2.VideoCapture(i)
            if test_cam.isOpened():
                # Try to read a frame to confirm it works
                ret, frame = test_cam.read()
                if ret and frame is not None:
                    print(f"   ✓ Camera {i} is working!")
                    camera = test_cam
                    camera_index = i
                    break
                else:
                    test_cam.release()
                    print(f"   ✗ Camera {i} opened but can't read frames")
            else:
                test_cam.release()
                print(f"   ✗ Camera {i} failed to open")
        except Exception as e:
            print(f"   ✗ Error with camera {i}: {e}")
    
    if camera is None:
        print("\n   ❌ ERROR: No working camera found!")
        print("   Make sure:")
        print("   - Camera is connected")
        print("   - No other app is using the camera")
        print("   - Camera permissions are granted")
        return False
    
    # Test 3: Test face detection
    print(f"\n[3] Testing face detection with camera {camera_index}...")
    print("   Press 'q' to quit, 's' to capture a test frame")
    
    # Set camera properties
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    frame_count = 0
    faces_detected = 0
    
    while True:
        ret, frame = camera.read()
        if not ret:
            print("   ❌ ERROR: Can't read from camera!")
            break
        
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50)
        )
        
        # Draw rectangles around faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, "Face", (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            faces_detected += 1
        
        # Add info text
        info_text = f"Faces: {len(faces)} | Frame: {frame_count}"
        cv2.putText(frame, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Press 'q' to quit, 's' to save frame", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Show frame
        cv2.imshow('Camera Test - Press Q to quit', frame)
        
        frame_count += 1
        
        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # Save current frame
            filename = f"test_frame_{frame_count}.jpg"
            cv2.imwrite(filename, frame)
            print(f"   ✓ Frame saved as {filename}")
    
    # Cleanup
    camera.release()
    cv2.destroyAllWindows()
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    print(f"   Camera Index: {camera_index}")
    print(f"   Frames Processed: {frame_count}")
    print(f"   Total Faces Detected: {faces_detected}")
    print("=" * 50)
    
    if faces_detected > 0:
        print("\n✓ SUCCESS: Camera and face detection are working!")
    else:
        print("\n⚠ WARNING: Camera works but no faces detected.")
        print("   Make sure you're in front of the camera!")
    
    return True

if __name__ == "__main__":
    try:
        test_camera()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
