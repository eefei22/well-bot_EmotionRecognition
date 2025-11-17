import os
import kagglehub
import zipfile
import shutil

# Set up Kaggle API key environment path
os.environ["KAGGLE_CONFIG_DIR"] = os.path.abspath(".secrets")

# Download CREMA-D dataset using kagglehub
print("📥 Downloading CREMA-D from Kaggle...")
dataset_path = kagglehub.dataset_download("ejlok1/cremad")  # Downloads to ~/.kagglehub

print(f"✅ Download complete. Dataset path: {dataset_path}")

# Destination for extracted files
target_dir = os.path.abspath("data/audio_raw/crema")
os.makedirs(target_dir, exist_ok=True)

# Move and extract WAV files
for root, _, files in os.walk(dataset_path):
    for file in files:
        if file.endswith(".zip"):
            zip_path = os.path.join(root, file)
            print(f"🗜️ Extracting: {zip_path}")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)
        elif file.endswith(".wav"):
            shutil.copy(os.path.join(root, file), os.path.join(target_dir, file))

print(f"✅ All audio files are now in: {target_dir}")
