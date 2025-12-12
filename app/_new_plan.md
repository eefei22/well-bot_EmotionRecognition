Nice, this stack is actually pretty clean once you see where each piece fits.
Let’s build you a roadmap that covers:

* local sandbox (ASR + SER using FunASR + emotion2vec)
* then wrap it into a service you can deploy to the cloud

---

## 0. Big-picture architecture

You’ll basically have **two FunASR pipelines**:

1. **ASR pipeline (speech → text)**

   * Use a Paraformer or UniASR model (offline vs streaming). FunASR is built exactly for this. ([GitHub][1])

2. **SER pipeline (speech → emotion)**

   * Use **emotion2vec+** via FunASR (`iic/emotion2vec_plus_seed/base/large`). These are pre-trained 9-class SER models. ([GitHub][2])

Your app then just orchestrates:

> audio → [ASR] transcript
> audio → [SER] emotion label + scores

---

## 1. Set up local environment

### 1.1. Python env

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

pip install -U funasr modelscope huggingface_hub soundfile
# if you have GPU: also ensure torch with cuda is installed
```

* FunASR docs recommend Linux, but they do have Windows and Docker instructions in the user manual. ([GitHub][1])

### 1.2. Pick initial models

* **ASR**: start with a generic Paraformer model, e.g. `paraformer-zh`, or another language variant from the FunASR model zoo. ([Hugging Face][3])
* **SER**: use `iic/emotion2vec_plus_base` or `iic/emotion2vec_plus_large` (better performance, heavier). ([GitHub][2])

---

## 2. Minimal local scripts (offline WAV → results)

### 2.1. ASR quick test (Paraformer via FunASR)

FunASR’s tutorial shows a “quick inference” snippet with `AutoModel` and `generate`. ([GitHub][4])

```python
from funasr import AutoModel

# Multi-functional ASR model (can attach VAD, punctuation, etc.)
asr_model = AutoModel(
    model="paraformer-zh",          # swap to other models if needed
    model_revision="v2.0.4",
    vad_model="fsmn-vad",           # optional VAD
    vad_model_revision="v2.0.4",
    punc_model="ct-punc-c",         # optional punctuation
    punc_model_revision="v2.0.4",
)

result = asr_model.generate(
    input="example.wav",            # 16kHz mono wav recommended
    sentence_timestamp=True         # get sentence-level timestamps if you want
)
print(result)
```

Once this prints sensible text, your ASR base is done.

---

### 2.2. SER quick test (emotion2vec+ via FunASR)

The emotion2vec README gives a ready-made FunASR snippet. ([GitHub][2])

```python
from funasr import AutoModel

ser_model = AutoModel(
    model="iic/emotion2vec_plus_base",  # or _plus_large
    hub="hf",                           # "hf" for Hugging Face; "ms" for ModelScope
)

# rec_result contains {'feats', 'labels', 'scores'}
rec_result = ser_model.generate(
    "example.wav",
    output_dir="./ser_out",
    extract_embedding=False   # False = just 9-class emotions + scores
)

print(rec_result)
```

Emotion index mapping from the README:([GitHub][2])

0: angry, 1: disgusted, 2: fearful, 3: happy, 4: neutral, 5: other, 6: sad, 7: surprised, 8: unknown

---

### 2.3. Combine ASR + SER into one local pipeline

Create a function that takes a wav path and returns both transcript + emotion:

```python
from funasr import AutoModel

# init once, at module import
asr_model = AutoModel(
    model="paraformer-zh",
    model_revision="v2.0.4",
    vad_model="fsmn-vad",
    vad_model_revision="v2.0.4",
    punc_model="ct-punc-c",
    punc_model_revision="v2.0.4",
)

ser_model = AutoModel(
    model="iic/emotion2vec_plus_base",
    hub="hf",
)

def analyze_audio(wav_path: str):
    asr_res = asr_model.generate(input=wav_path, sentence_timestamp=True)
    ser_res = ser_model.generate(wav_path, extract_embedding=False)

    # you’ll adapt this to the exact structure FunASR returns
    transcript = asr_res[0].get("text", "") if isinstance(asr_res, list) else asr_res
    emo_labels = ser_res[0]["labels"]
    emo_scores = ser_res[0]["scores"]

    return {
        "transcript": transcript,
        "emotion_labels": emo_labels,
        "emotion_scores": emo_scores,
    }
```

This is your **core logic** that you’ll later wrap in an API.

---

## 3. Move from scripts → local API service

Given your existing stack, you’ll likely want a **FastAPI** microservice.

### 3.1. Basic FastAPI layout

```python
# app/main.py
from fastapi import FastAPI, UploadFile, File
from funasr import AutoModel
import tempfile
import shutil

app = FastAPI()

asr_model = AutoModel(model="paraformer-zh", model_revision="v2.0.4")
ser_model = AutoModel(model="iic/emotion2vec_plus_base", hub="hf")

def run_pipeline(wav_path: str):
    asr_res = asr_model.generate(input=wav_path, sentence_timestamp=True)
    ser_res = ser_model.generate(wav_path, extract_embedding=False)
    # TODO: normalise result format
    return {"asr_raw": asr_res, "ser_raw": ser_res}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    result = run_pipeline(tmp_path)
    return result
```

Run locally:

```bash
uvicorn app.main:app --reload
```

Test by `curl` or Postman: upload an audio file to `/analyze`.

Later you can:

* add `/asr` and `/ser` endpoints separately,
* post-process the raw results into a clean schema (e.g., `emotion: "happy", confidence: 0.89`).

---

## 4. Streaming vs offline (optional next step)

* **Offline**: the above is enough for a first version; send full clips, get full transcript + emotion.
* **Streaming**: FunASR has streaming support for Paraformer (chunked input). The model card shows `chunk_size` and streaming usage. ([Hugging Face][5])

Roadmap wise, I’d first:

1. Make offline API solid.
2. Then, explore FunASR’s streaming `generate` API and adapt it to WebSockets (FastAPI) if you need live captions + emotion.

---

## 5. Cloud deployment roadmap

### 5.1. Containerise

High-level Dockerfile steps:

1. Base image: `nvidia/cuda` (if GPU) or `python:3.11-slim`.
2. Install system deps (ffmpeg, libsndfile).
3. Install your Python deps (`funasr`, `modelscope`, `huggingface_hub`, `fastapi`, `uvicorn`).
4. Copy your app code.
5. Expose port 8000 and set `CMD` to run `uvicorn`.

If CPU-only inference is too heavy, check **funasr-onnx** for exporting Paraformer to ONNX plus quantization for lightweight deployment. ([PyPI][6])

### 5.2. Deployment targets

* **GPU VM (GCP, AWS, etc.)**: simplest for heavy models (emotion2vec+ large).
* **Cloud Run / ECS / K8s**: if you want autoscaling; just treat the FastAPI container as a normal web service.

You’ll want to:

* preload models on startup (avoid downloading each request),
* mount a writable cache (FunASR / ModelScope will cache models on disk),
* set reasonable request timeouts based on clip length.

---

## 6. Key resources to bookmark

1. **emotion2vec README** – sections:

   * *“emotion2vec+: speech emotion recognition foundation model”*
   * *“Inference with checkpoints → Install from FunASR”* (includes SER example code + label mapping). ([GitHub][2])

2. **FunASR tutorial / quick start** – shows `AutoModel` usage for ASR and various tasks. ([GitHub][4])

3. **FunASR wiki (user manual)** – environment install, quick inference, model types (Paraformer for offline, UniASR for streaming). ([GitHub][1])

4. **Model zoo pages** (Hugging Face / ModelScope):

   * Paraformer ASR models (and example code). ([Hugging Face][3])
   * emotion2vec+ models (seed/base/large). ([GitHub][2])

5. **Optional alt**: **SenseVoice** – a single foundation model that already bundles ASR + SER + LID + AED in one. Might be interesting later if you want one model for many speech tasks. ([GitHub][7])
