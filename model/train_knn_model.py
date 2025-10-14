import sys
from pathlib import Path
import cv2 as cv
import numpy as np
import random

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

def preprocess_for_knn(image: np.ndarray) -> np.ndarray:
    # Resize to standard size
    resized = cv.resize(image, (30, 35), interpolation=cv.INTER_AREA)
    return resized.flatten().astype(np.float32)

def train_ocr_model():
    print("Starting OCR model training...")
    
    training_data_path = project_root / "model" / "training_data"
    
    samples = []
    labels = []
    
    # ---Load training data---
    for digit_folder in training_data_path.iterdir():
        if not digit_folder.is_dir() or not digit_folder.name.isdigit():
            continue
        digit_label = int(digit_folder.name)
        image_files = list(digit_folder.glob("*.png"))
        
        # ---Undersample data---
        # Randomly select the minimum number of samples across all digits
        min_samples = min(len(list(f.glob("*.png"))) for f in training_data_path.iterdir() if f.is_dir() and f.name.isdigit())
        image_files = random.sample(image_files, min_samples)
        
        for image_path in image_files:
            img = cv.imread(str(image_path), cv.IMREAD_GRAYSCALE)
            if img is None:
                continue
            
            processed_sample = preprocess_for_knn(img)
            samples.append(processed_sample)
            labels.append(digit_label)
    
    # Convert lists to numpy arrays
    samples = np.array(samples, dtype=np.float32)
    labels = np.array(labels, dtype=np.float32)
    
    # ---Train KNN model---
    knn = cv.ml.KNearest_create()
    knn.train(samples, cv.ml.ROW_SAMPLE, labels)
    
    # ---Save the trained model---
    model_path = project_root / "model" / "knn_ocr_model.yml"
    knn.save(str(model_path))
    
if __name__ == "__main__":
    train_ocr_model()
        