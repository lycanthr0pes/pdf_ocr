from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from ocr_app.config import AppConfig


ProgressCallback = Callable[[str, str, int, int], None]


class OwocrService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def ocr_images(
        self,
        image_paths: list[Path],
        work_dir: Path,
        progress_callback: ProgressCallback,
    ) -> str:
        if self.config.allow_mock_ocr:
            return self._mock_text(image_paths, progress_callback)

        total = len(image_paths)
        progress_callback("ocr", "Running owocr Chrome Screen AI on rendered page images", 0, total)

        engine = self._create_engine(work_dir)
        pages: list[str] = []
        for index, image_path in enumerate(image_paths, start=1):
            progress_callback("ocr", f"Processing page {index}/{total}", index - 1, total)
            pages.append(self._ocr_single_image(engine, image_path))
            progress_callback("ocr", f"Completed page {index}/{total}", index, total)
        return "\n\n".join(page for page in pages if page).strip()

    def _create_engine(self, work_dir: Path):
        env_updates = self.build_env(work_dir)
        old_env = {key: os.environ.get(key) for key in env_updates}
        os.environ.update(env_updates)
        try:
            from owocr.ocr import ChromeScreenAI
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        engine = ChromeScreenAI()
        if not getattr(engine, "available", False):
            raise RuntimeError("owocr Chrome Screen AI could not be initialized.")
        return engine

    def _ocr_single_image(self, engine, image_path: Path) -> str:
        success, result = engine(str(image_path))
        if not success:
            raise RuntimeError(f"owocr failed on {image_path.name}: {result}")
        return self._ocr_result_to_text(result)

    def _ocr_result_to_text(self, result) -> str:
        paragraphs: list[str] = []
        for paragraph in getattr(result, "paragraphs", []):
            lines: list[str] = []
            for line in getattr(paragraph, "lines", []):
                line_text = getattr(line, "text", None)
                if not line_text:
                    words = getattr(line, "words", []) or []
                    line_text = " ".join(word.text for word in words if getattr(word, "text", ""))
                line_text = (line_text or "").strip()
                if line_text:
                    lines.append(line_text)
            if lines:
                paragraphs.append("\n".join(lines))
        return "\n\n".join(paragraphs).strip()

    def build_env(self, work_dir: Path) -> dict[str, str]:
        temp_dir = work_dir / "tmp"
        home_dir = self.config.base_dir / ".owocr_home"
        config_dir = home_dir / ".config"
        temp_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["TMP"] = str(temp_dir)
        env["TEMP"] = str(temp_dir)
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _mock_text(self, image_paths: list[Path], progress_callback: ProgressCallback) -> str:
        total = len(image_paths)
        pages: list[str] = []
        for index, image_path in enumerate(image_paths, start=1):
            progress_callback("ocr", f"Mock owocr processing page {index}/{total}", index, total)
            pages.append(
                f"[mock page {index}]\n"
                f"Source image: {image_path.name}\n"
                f"This simulates Chrome Screen AI text output."
            )
        return "\n\n".join(pages)
