"""Use the pinned vendor codecs, or an explicitly selected development checkout."""
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

DECOMP_ROOT = Path(os.environ.get("FFTA_DECOMP_ROOT",
    str(Path(__file__).resolve().parents[1] / "vendor/fftadecomp"))).resolve()
if not (DECOMP_ROOT / "tools/scene_text_codec.py").is_file():
    raise RuntimeError("Set FFTA_DECOMP_ROOT to the compatible decomp checkout")
sys.path.append(str(DECOMP_ROOT / "tools"))
