import sys
from pathlib import Path

# Make repo root importable (for `analysis`) and data-processing scripts importable.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data-processing"))
