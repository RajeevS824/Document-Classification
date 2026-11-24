"""Pre-download the Nutrient v1 model files (used by setup.bat). Safe to skip: the app downloads them on first use."""
import sys

from huggingface_hub import hf_hub_download

from . import config

repo = config.load()["image_model"]["repo"]
print(f"Downloading {repo} (about 2.2 GB, one time) ...", flush=True)
for name in ("image_model.onnx", "text_model.onnx", "config.json"):
    p = hf_hub_download(repo_id=repo, filename=f"modules/omni-image/{name}"); print("  ok:", p, flush=True)
try:
    from transformers import AutoImageProcessor, AutoTokenizer
    AutoImageProcessor.from_pretrained(repo, subfolder="modules/omni-image"); AutoTokenizer.from_pretrained(repo, subfolder="modules/omni-image")
    print("  ok: processor + tokenizer", flush=True)
except Exception as e:
    print("  warning: processor/tokenizer not cached:", e); sys.exit(0)
print("Model ready.")
