# scripts/download_TESS.py

import os
import kagglehub
import shutil

# Step 1: Set Kaggle credentials
os.environ["KAGGLE_CONFIG_DIR"] = os.path.abspath(".secrets")

# Step 2: Download dataset
print("📥 Downloading TESS from Kaggle...")
dataset_path = kagglehub.dataset_download("ejlok1/toronto-emotional-speech-set-tess")
print(f"✅ Dataset downloaded to: {dataset_path}")

# Step 3: Destination
target_dir = os.path.abspath("data/audio_raw/tess")
os.makedirs(target_dir, exist_ok=True)

# Step 4: Move all WAV files into flat structure for easier processing
print("📂 Organizing audio files...")

for root, _, files in os.walk(dataset_path):
    for file in files:
        if file.endswith(".wav"):
            src = os.path.join(root, file)
            dst = os.path.join(target_dir, file)
            shutil.copy(src, dst)

print(f"✅ All .wav files copied to: {target_dir}")
