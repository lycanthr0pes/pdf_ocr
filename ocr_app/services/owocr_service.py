from __future__ import annotations

import shlex
import subprocess
import os
import time
from pathlib import Path
from typing import Callable

from ocr_app.config import AppConfig


ProgressCallback = Callable[[str, str, int, int], None]


class OwocrService:
    OUTPUT_POLL_SECONDS = 1.0
    OUTPUT_READY_STABLE_POLLS = 2
    PROCESS_SHUTDOWN_TIMEOUT = 10

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def ocr_images(
        self,
        image_paths: list[Path],
        work_dir: Path,
        progress_callback: ProgressCallback,
    ) -> str:
        output_dir = work_dir / "owocr_output"

        if not self.config.owocr_executable:
            if self.config.allow_mock_ocr:
                return self._mock_text(image_paths, progress_callback)
            raise RuntimeError("OWOCR_EXECUTABLE is not configured.")

        total = len(image_paths)
        progress_callback("ocr", "Running owocr with Chrome Screen AI on rendered page images", 0, total)

        command = self._build_command(
            input_dir=image_paths[0].parent,
            output_dir=output_dir,
        )
        process = subprocess.Popen(
            command,
            cwd=str(work_dir),
            env=self.build_env(work_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            self._wait_for_outputs(
                process=process,
                output_dir=output_dir,
                expected_count=total,
                progress_callback=progress_callback,
            )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=self.PROCESS_SHUTDOWN_TIMEOUT)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self.PROCESS_SHUTDOWN_TIMEOUT)

        stdout, stderr = process.communicate(timeout=5)
        if process.returncode not in (0, 1, -15):
            detail = (stderr or "").strip() or (stdout or "").strip() or "no output"
            raise RuntimeError(
                f"owocr command failed with code {process.returncode}: {detail}"
            )
        if not output_dir.exists():
            raise RuntimeError("owocr completed but did not create the expected output directory.")

        progress_callback("ocr", "owocr command completed", total, total)
        page_outputs = sorted(output_dir.glob("*.txt"))
        if not page_outputs:
            raise RuntimeError("owocr completed but no text files were produced.")
        return "\n\n".join(
            page_output.read_text(encoding="utf-8").strip()
            for page_output in page_outputs
        ).strip()

    def _build_command(self, input_dir: Path, output_dir: Path) -> list[str]:
        command = [
            self.config.owocr_executable,
            f"-r={input_dir}",
            f"-w={output_dir}",
        ]
        if self.config.owocr_extra_args.strip():
            command.extend(shlex.split(self.config.owocr_extra_args, posix=False))
        return command

    def _wait_for_outputs(
        self,
        process: subprocess.Popen,
        output_dir: Path,
        expected_count: int,
        progress_callback: ProgressCallback,
        timeout_seconds: int = 180,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_count = -1
        stable_polls = 0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                page_outputs = sorted(output_dir.glob("*.txt")) if output_dir.exists() else []
                if len(page_outputs) >= expected_count:
                    return
                stdout, stderr = process.communicate(timeout=5)
                detail = (stderr or "").strip() or (stdout or "").strip() or "no output"
                raise RuntimeError(
                    "owocr exited before producing the expected page outputs: "
                    f"{len(page_outputs)}/{expected_count}. {detail}"
                )

            page_outputs = sorted(output_dir.glob("*.txt")) if output_dir.exists() else []
            current_count = len(page_outputs)
            if current_count != last_count:
                progress_callback(
                    "ocr",
                    f"owocr produced {current_count}/{expected_count} page outputs",
                    current_count,
                    expected_count,
                )
                last_count = current_count
                stable_polls = 0
            elif current_count >= expected_count:
                stable_polls += 1
                if stable_polls >= self.OUTPUT_READY_STABLE_POLLS:
                    return

            time.sleep(self.OUTPUT_POLL_SECONDS)
        raise RuntimeError("owocr did not produce the expected page outputs before timeout.")

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
