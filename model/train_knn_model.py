"""Train and save the KNN OCR model from labeled digit images.

This script reads the manually labeled digit dataset stored in
model/training_data/<digit>, converts each image into the flattened feature
vector expected by OpenCV's KNearest model, and writes the trained model to
model/knn_ocr_model.yml.

The dataset is balanced by undersampling every digit class down to the size of
the smallest class. That keeps the model from being biased toward digits with
more saved examples.
"""

import random
from pathlib import Path

import cv2 as cv
import numpy as np

project_root = Path(__file__).resolve().parent.parent

TRAINING_IMAGE_SIZE = (30, 35)
RANDOM_SEED = 42


def preprocess_for_knn(image: np.ndarray) -> np.ndarray:
    """Convert a digit image into the feature format expected by the KNN model.

    Each image is resized to the standard OCR digit size and then flattened into
    a one-dimensional float32 array. This matches the shape used during live OCR
    inference in the main application.

    Args:
        image: A single-channel digit image.

    Returns:
        A flattened float32 feature vector.
    """
    resized = cv.resize(image, TRAINING_IMAGE_SIZE, interpolation=cv.INTER_AREA)
    return resized.flatten().astype(np.float32)


def get_digit_directories(training_data_path: Path) -> dict[int, list[Path]]:
    """Collect labeled image paths for each digit directory.

    Args:
        training_data_path: Root path containing subdirectories 0 through 9.

    Returns:
        A mapping of digit label to list of image paths.

    Raises:
        ValueError: If no labeled digit folders are found or any digit folder is empty.
    """
    digit_files: dict[int, list[Path]] = {}

    for digit_folder in sorted(training_data_path.iterdir()):
        if not digit_folder.is_dir() or not digit_folder.name.isdigit():
            continue

        digit_label = int(digit_folder.name)
        image_files = sorted(digit_folder.glob("*.png"))
        digit_files[digit_label] = image_files

    if not digit_files:
        raise ValueError("No digit folders with PNG training samples were found.")

    if empty_digits := [digit for digit, files in digit_files.items() if not files]:
        raise ValueError(f"Some digit folders are empty: {empty_digits}")

    return digit_files


def train_ocr_model() -> None:
    """Train a KNN OCR model from the saved digit dataset and write it to disk."""
    print("Starting OCR model training...")

    training_data_path = project_root / "model" / "training_data"
    model_path = project_root / "model" / "knn_ocr_model.yml"

    # Load the available files once so we can validate the dataset and compute
    # the balancing threshold before reading any images.
    digit_files = get_digit_directories(training_data_path)

    # Balance the dataset by undersampling each digit class to the size of the
    # smallest class. This avoids overweighting digits that happen to have more
    # saved examples.
    min_samples = min(len(files) for files in digit_files.values())
    print(f"Using {min_samples} samples per digit class.")

    random.seed(RANDOM_SEED)

    samples = []
    labels = []

    for digit_label, image_files in sorted(digit_files.items()):
        selected_files = random.sample(image_files, min_samples)

        for image_path in selected_files:
            img = cv.imread(str(image_path), cv.IMREAD_GRAYSCALE)
            if img is None:
                print(f"Skipping unreadable image: {image_path}")
                continue

            processed_sample = preprocess_for_knn(img)
            samples.append(processed_sample)
            labels.append(digit_label)

    if not samples:
        raise ValueError("No valid training images were loaded.")

    # OpenCV expects float32 numpy arrays for both samples and labels.
    sample_array = np.array(samples, dtype=np.float32)
    label_array = np.array(labels, dtype=np.float32)

    # Train a basic KNN classifier using one row per sample.
    knn = cv.ml.KNearest_create()
    knn.train(sample_array, cv.ml.ROW_SAMPLE, label_array)

    # Save the trained model so the main OCR pipeline can load it later.
    knn.save(str(model_path))
    print(f"Model saved to {model_path}")


if __name__ == "__main__":
    train_ocr_model()
