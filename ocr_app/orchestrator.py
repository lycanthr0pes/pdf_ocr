from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from ocr_app.config import AppConfig
from ocr_app.models import OcrJobResult
from ocr_app.pdf_renderer import render_pdf_to_images
from ocr_app.services.owocr_service import OwocrService


ProgressCallback = Callable[[str, str, int, int], None]


class OcrOrchestrator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.owocr_service = OwocrService(config)

    def run(
        self,
        pdf_path: Path,
        progress_callback: ProgressCallback,
    ) -> OcrJobResult:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        engine = "owocr"
        job_name = f"{pdf_path.stem}_{engine}_{timestamp}"
        work_dir = self.config.work_dir / job_name
        output_dir = self.config.output_dir / job_name
        page_dir = work_dir / "pages"
        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        progress_callback("prepare", f"Rendering PDF pages from {pdf_path.name}", 0, 1)
        image_paths = render_pdf_to_images(
            pdf_path=pdf_path,
            output_dir=page_dir,
            dpi=self.config.pdf_render_dpi,
        )
        page_count = len(image_paths)
        if page_count == 0:
            raise RuntimeError("The PDF produced no pages.")
        progress_callback("prepare", f"Rendered {page_count} pages", 1, 1)

        text = self.owocr_service.ocr_images(image_paths, work_dir, progress_callback)
        suffix = ".txt"

        output_path = output_dir / f"{pdf_path.stem}{suffix}"
        output_path.write_text(text, encoding="utf-8")
        progress_callback("finalize", f"Saved output to {output_path.name}", 1, 1)

        return OcrJobResult(
            engine=engine,
            page_count=page_count,
            output_path=output_path,
            text=text,
        )
