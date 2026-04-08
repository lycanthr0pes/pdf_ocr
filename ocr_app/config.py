from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class AppConfig:
    base_dir: Path
    input_dir: Path
    work_dir: Path
    output_dir: Path
    pdf_render_dpi: int
    allow_mock_ocr: bool


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> AppConfig:
    load_dotenv()
    base_dir = Path(os.getenv("APP_BASE_DIR", Path.cwd())).resolve()
    input_dir = (base_dir / os.getenv("INPUT_DIR", "data/input")).resolve()
    work_dir = (base_dir / os.getenv("WORK_DIR", "data/work")).resolve()
    output_dir = (base_dir / os.getenv("OUTPUT_DIR", "data/output")).resolve()

    input_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        base_dir=base_dir,
        input_dir=input_dir,
        work_dir=work_dir,
        output_dir=output_dir,
        pdf_render_dpi=int(os.getenv("PDF_RENDER_DPI", "220")),
        allow_mock_ocr=_bool_env("ALLOW_MOCK_OCR", True),
    )
