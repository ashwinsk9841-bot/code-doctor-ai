import os
import sys
from pathlib import Path

# Ensure the project root is importable regardless of where pytest runs.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
