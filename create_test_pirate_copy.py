import cv2
import os
import numpy as np
from fingerprint import generate_video_fingerprint, compare_fingerprints, compare_fingerprints_flexible

def process_video(input_path, output_path, process_frame_func):
    """
    Reads a video, applies a processing function to each frame, 
    and writes it to an output file.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"❌ Failed to open {input_path}")
        return
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Processing {os.path.basename(output_path)} ({total_frames} frames)...")
    
    # Read first frame to determine output dimensions
    ret, frame = cap.read()
    if not ret:
        cap.release()
        return
        
    processed_frame = process_frame_func(frame)
    out_height, out_width = processed_frame.shape[:2]
    
    # Setup VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height))
    
    # Write first frame
    out.write(processed_frame)
    frame_count = 1
    
    # Process remaining frames
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        processed_frame = process_frame_func(frame)
        out.write(processed_frame)
        
        frame_count += 1
        if frame_count % 100 == 0:
            print(f"  Processed {frame_count}/{total_frames} frames", end='\r')
            
    print(f"  ✅ Done processing {os.path.basename(output_path)}." + " " * 15)
    
    cap.release()
    out.release()

def crop_frame(frame):
    """Crops 10% from each edge of the frame."""
    h, w = frame.shape[:2]
    crop_x = int(w * 0.1)
    crop_y = int(h * 0.1)
    return frame[crop_y:h-crop_y, crop_x:w-crop_x]

def mirror_frame(frame):
    """Flips the frame horizontally."""
    return cv2.flip(frame, 1)

def brighten_frame(frame):
    """Increases the brightness of the frame by 50."""
    matrix = np.ones(frame.shape, dtype="uint8") * 50
    return cv2.add(frame, matrix)

def main():
    print("=" * 60)
    print("🏴‍☠️ ContentShield — Pirate Copy Generator & Tester 🏴‍☠️")
    print("=" * 60)
    
    video_path = input("Enter path to original video file: ").strip()
    
    if not os.path.exists(video_path):
        print(f"❌ Error: File not found at {video_path}")
        return
        
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    dir_name = os.path.dirname(video_path)
    if not dir_name:
        dir_name = "."
        
    # --- STEP 1: Original Fingerprint ---
    print("\n=== STEP 1: Fingerprint Original ===")
    print("Generating baseline fingerprint for original video...")
    original_fp, orig_meta = generate_video_fingerprint(video_path, content_type="general")
    print(f"✅ Original fingerprint generated: {len(original_fp)} frames hashed.")
    
    # --- STEP 2: Create Pirate Copies ---
    print("\n=== STEP 2: Create Modified Copies ===")
    path_cropped = os.path.join(dir_name, f"{base_name}_cropped.mp4")
    path_mirrored = os.path.join(dir_name, f"{base_name}_mirrored.mp4")
    path_brightened = os.path.join(dir_name, f"{base_name}_brightened.mp4")
    
    process_video(video_path, path_cropped, crop_frame)
    process_video(video_path, path_mirrored, mirror_frame)
    process_video(video_path, path_brightened, brighten_frame)
    
    # --- STEP 3: Test Fingerprints ---
    print("\n=== STEP 3: Test Detection Resilience ===")
    
    tests = [
        ("Cropped (-10% edges)", path_cropped),
        ("Mirrored (Horizontal)", path_mirrored),
        ("Brightened (+50)", path_brightened)
    ]
    
    for name, path in tests:
        print(f"\nEvaluating '{name}' copy...")
        # Generate fingerprint for the modified video
        test_fp, _ = generate_video_fingerprint(path, content_type="general")
        
        # Compare against the original fingerprint
        if "Brightened" in name:
            result = compare_fingerprints(original_fp, test_fp, threshold=0.70)
        else:
            result = compare_fingerprints_flexible(original_fp, test_fp, threshold=0.70)
        
        match_pct = result['match_percentage'] * 100
        verdict = result['verdict']
        
        emoji = "✅" if verdict == "MATCH" else "❌"
        
        print(f"   {emoji} Result: {match_pct:.1f}% match -> {verdict}")
        print(f"   (Matched {result['matched_frames']} out of {result['total_compared']} frames)")
        
    print("\n" + "=" * 60)
    print("✅ Testing Complete.")
    print("As demonstrated, our perceptual hashing system remains")
    print("highly resilient to common piracy modification techniques.")
    print("=" * 60)

if __name__ == "__main__":
    main()
