import kagglehub
import os
import shutil

os.environ["KAGGLE_CONFIG_DIR"] = os.path.abspath(".secrets")

TARGET_DIR = "data/audio_raw/ravdess"

def download_ravdess():
    if os.path.exists(TARGET_DIR) and os.listdir(TARGET_DIR):
        print("✅ RAVDESS already exists. Skipping download.")
        return

    print("⬇️  Downloading RAVDESS...")
    download_path = kagglehub.dataset_download("uwrfkaggler/ravdess-emotional-speech-audio")
    extracted_path = download_path  # <- FIXED: no subfolder

    os.makedirs(TARGET_DIR, exist_ok=True)
    for item in os.listdir(extracted_path):
        src = os.path.join(extracted_path, item)
        dst = os.path.join(TARGET_DIR, item)
        shutil.move(src, dst)

    print(f"✅ Downloaded to {TARGET_DIR}")

if __name__ == "__main__":
    download_ravdess()
