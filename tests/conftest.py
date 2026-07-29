from __future__ import annotations

import os
import sys
from uuid import uuid4
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TMP_ROOT = ROOT / ".test-work"

TMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["TMP"] = str(TMP_ROOT)
os.environ["TEMP"] = str(TMP_ROOT)
os.environ["TMPDIR"] = str(TMP_ROOT)

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def make_test_dir(name: str) -> Path:
    path = TMP_ROOT / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path
