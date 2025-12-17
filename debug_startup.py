
import time
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

print("Ref: Starting import check...")
start_time = time.time()

try:
    print("Importing app.main...")
    import app.main
    end_time = time.time()
    print(f"Success! Import took {end_time - start_time:.2f} seconds.")
except Exception as e:
    print(f"FAILED to import app.main: {e}")
    import traceback
    traceback.print_exc()

print("Checking individual heavy imports...")
imports = ["torch", "torchaudio", "transformers", "funasr", "librosa"]
for mod in imports:
    t0 = time.time()
    try:
        __import__(mod)
        dt = time.time() - t0
        print(f"  import {mod}: {dt:.2f}s")
    except Exception as e:
        print(f"  import {mod}: FAILED ({e})")
