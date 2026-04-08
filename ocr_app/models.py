from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class OcrJobResult:
    engine: str
    page_count: int
    output_path: Path
    text: str
