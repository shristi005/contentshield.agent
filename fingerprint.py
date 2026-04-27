import cv2
import imagehash
from PIL import Image
import numpy as np
import librosa
import os

# Profiles for different types of content
# Defines sample rate (frames), match threshold, and audio fingerprint weight
CONTENT_TYPES = {
    "sports": {"sample_rate": 30, "threshold": 0.70, "audio_weight": 0.3},
    "film": {"sample_rate": 24, "threshold": 0.75, "audio_weight": 0.4},
    "music_video": {"sample_rate": 25, "threshold": 0.65, "audio_weight": 0.6},
    "news": {"sample_rate": 30, "threshold": 0.80, "audio_weight": 0.2},
    "documentary": {"sample_rate": 30, "threshold": 0.75, "audio_weight": 0.3},
    "general": {"sample_rate": 30, "threshold": 0.70, "audio_weight": 0.35}
}


def generate_video_fingerprint(video_path, content_type="general"):
    """
    Generates a visual fingerprint for a video file.
    
    Opens the video, samples frames at a defined rate, and computes a perceptual 
    hash (phash) for each sampled frame. Returns the list of hashes and metadata.
    """
    if content_type not in CONTENT_TYPES:
        content_type = "general"
        
    sample_rate = CONTENT_TYPES[content_type]["sample_rate"]
    
    # Open video file using OpenCV
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
        
    # Extract metadata
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Calculate duration safely
    if fps > 0:
        duration_seconds = total_frames / fps
    else:
        duration_seconds = 0.0
        
    fingerprint = []
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            break
            
        # Sample one frame every 'sample_rate' frames
        if frame_idx % sample_rate == 0:
            # Convert BGR (OpenCV default) to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert numpy array to PIL Image
            pil_img = Image.fromarray(rgb_frame)
            
            # Generate perceptual hash using imagehash
            frame_hash = imagehash.phash(pil_img)
            
            # Append string representation of hash to the fingerprint list
            fingerprint.append(str(frame_hash))
            
        frame_idx += 1
        
    # Release the video capture object
    cap.release()
    
    metadata = {
        "duration_seconds": duration_seconds,
        "total_frames": total_frames,
        "fps": fps,
        "content_type": content_type
    }
    
    return fingerprint, metadata


def generate_audio_fingerprint(video_path):
    """
    Generates a simple audio fingerprint from the audio track of a video.
    
    Extracts audio, calculates RMS energy levels, normalizes them, and samples 
    them to create a signature. This helps with matching modified videos.
    """
    try:
        # Load audio using librosa. sr=None keeps original sample rate
        y, sr = librosa.load(video_path, sr=None, mono=True)
        
        # Check if audio was successfully extracted
        if y is None or len(y) == 0:
            return []
            
        # Calculate root-mean-square (RMS) energy for audio frames
        # This provides a basic representation of audio intensity over time
        hop_length = 512
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        
        # Normalize energy levels between 0 and 1
        max_rms = np.max(rms)
        if max_rms > 0:
            normalized_rms = rms / max_rms
        else:
            normalized_rms = rms
            
        # Subsample to create a manageable signature size
        # Taking 1 sample every 10 frames
        subsample_factor = 10
        audio_signature = normalized_rms[::subsample_factor].tolist()
        
        return audio_signature
        
    except Exception as e:
        print(f"Failed to generate audio fingerprint: {e}")
        return []


def compare_fingerprints(fp1, fp2, threshold=0.70):
    """
    Compares two video fingerprints and determines if they match.
    Uses strict position-based index-by-index comparison.
    
    Args:
        fp1 (list): First fingerprint (list of hash strings).
        fp2 (list): Second fingerprint (list of hash strings).
        threshold (float): Minimum match percentage to consider a match.
        
    Returns:
        dict: Results of the comparison including match percentage, verdict, etc.
    """
    if not fp1 or not fp2:
        return {
            "match_percentage": 0.0,
            "verdict": "NO MATCH",
            "matched_frames": 0,
            "total_compared": 0,
            "confidence_level": "LOW"
        }
        
    matched_frames = 0
    total_compared = min(len(fp1), len(fp2))
    
    # Strict mode: compare index-by-index
    for i in range(total_compared):
        hash1 = imagehash.hex_to_hash(fp1[i])
        hash2 = imagehash.hex_to_hash(fp2[i])
        
        # Calculate Hamming distance
        distance = hash1 - hash2
        
        # A distance < 10 is considered a match for this frame
        if distance < 10:
            matched_frames += 1
            
    # Calculate overall match percentage
    match_percentage = 0.0
    if total_compared > 0:
        match_percentage = matched_frames / total_compared
        
    # Determine verdict based on provided threshold
    if match_percentage >= threshold:
        verdict = "MATCH"
    else:
        verdict = "NO MATCH"
        
    # Determine confidence level of the match
    if match_percentage >= 0.85:
        confidence_level = "HIGH"
    elif match_percentage >= 0.70:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"
        
    return {
        "match_percentage": match_percentage,
        "verdict": verdict,
        "matched_frames": matched_frames,
        "total_compared": total_compared,
        "confidence_level": confidence_level
    }

def compare_fingerprints_flexible(original_fp, suspect_fp, threshold=0.70):
    """
    Compares two video fingerprints using a flexible best-match approach.
    For each frame in suspect_fp, it searches all frames in original_fp
    for the lowest Hamming distance.
    
    Args:
        original_fp (list): Original fingerprint (list of hash strings).
        suspect_fp (list): Suspect fingerprint (list of hash strings).
        threshold (float): Minimum match percentage to consider a match.
        
    Returns:
        dict: Results of the comparison including match percentage, verdict, etc.
    """
    if not original_fp or not suspect_fp:
        return {
            "match_percentage": 0.0,
            "verdict": "NO MATCH",
            "matched_frames": 0,
            "total_compared": 0,
            "confidence_level": "LOW"
        }
        
    matched_frames = 0
    total_compared = len(suspect_fp)
    
    # Pre-convert fp1 to ImageHash objects for faster comparison
    fp1_hashes = [imagehash.hex_to_hash(h) for h in original_fp]
    
    for suspect_str in suspect_fp:
        hash2 = imagehash.hex_to_hash(suspect_str)
        best_distance = float('inf')
        
        for hash1 in fp1_hashes:
            distance = hash1 - hash2
            if distance < best_distance:
                best_distance = distance
                if best_distance == 0:
                    break # perfect match
                    
        if best_distance < 10:
            matched_frames += 1
            
    # Calculate overall match percentage
    match_percentage = 0.0
    if total_compared > 0:
        match_percentage = matched_frames / total_compared
        
    # Determine verdict based on provided threshold
    if match_percentage >= threshold:
        verdict = "MATCH"
    else:
        verdict = "NO MATCH"
        
    # Determine confidence level of the match
    if match_percentage >= 0.85:
        confidence_level = "HIGH"
    elif match_percentage >= 0.70:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"
        
    return {
        "match_percentage": match_percentage,
        "verdict": verdict,
        "matched_frames": matched_frames,
        "total_compared": total_compared,
        "confidence_level": confidence_level
    }


def fingerprint_image(image_path):
    """
    Generates a perceptual hash for a single image file.
    
    Useful for promotional images, thumbnails, posters, etc.
    """
    try:
        # Open image using Pillow
        img = Image.open(image_path)
        
        # Generate perceptual hash
        img_hash = imagehash.phash(img)
        
        return str(img_hash)
    except Exception as e:
        raise ValueError(f"Could not fingerprint image {image_path}: {e}")
