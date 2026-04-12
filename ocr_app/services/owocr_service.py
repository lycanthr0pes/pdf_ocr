from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ocr_app.config import AppConfig


ProgressCallback = Callable[[str, str, int, int], None]


@dataclass(slots=True)
class MarkdownBlock:
    text: str
    center_x: float
    center_y: float
    width: float
    height: float


class OwocrService:
    _shared_engine = None

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def ocr_images(
        self,
        image_paths: list[Path],
        work_dir: Path,
        progress_callback: ProgressCallback,
    ) -> tuple[str, str]:
        if self.config.allow_mock_ocr:
            return self._mock_text(image_paths, progress_callback)

        total = len(image_paths)
        progress_callback("ocr", "Running owocr Chrome Screen AI on rendered page images", 0, total)

        engine = self._create_engine(work_dir)
        text_pages: list[str] = []
        markdown_pages: list[str] = []
        for index, image_path in enumerate(image_paths, start=1):
            progress_callback("ocr", f"Processing page {index}/{total}", index - 1, total)
            text_page, markdown_page = self._ocr_single_image(engine, image_path)
            text_pages.append(text_page)
            if markdown_page:
                markdown_pages.append(f"## Page {index}\n\n{markdown_page}")
            progress_callback("ocr", f"Completed page {index}/{total}", index, total)
        return (
            "\n\n".join(page for page in text_pages if page).strip(),
            "\n\n".join(page for page in markdown_pages if page).strip(),
        )

    def _create_engine(self, work_dir: Path):
        if self.__class__._shared_engine is not None:
            return self.__class__._shared_engine

        env_updates = self.build_env(work_dir)
        old_env = {key: os.environ.get(key) for key in env_updates}
        os.environ.update(env_updates)
        try:
            from owocr.ocr import ChromeScreenAI
            self._patch_screenai_download(ChromeScreenAI)
            engine = ChromeScreenAI()
            if not getattr(engine, "available", False):
                raise RuntimeError("owocr Chrome Screen AI could not be initialized.")
            self.__class__._shared_engine = engine
            return engine
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _ocr_single_image(self, engine, image_path: Path) -> tuple[str, str]:
        success, result = engine(image_path)
        if not success:
            raise RuntimeError(f"owocr failed on {image_path.name}: {result}")
        return self._ocr_result_to_text(result), self._ocr_result_to_markdown(result)

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

    def _ocr_result_to_markdown(self, result) -> str:
        blocks: list[str] = []
        for paragraph in getattr(result, "paragraphs", []):
            lines = self._paragraph_lines(paragraph)
            if not lines:
                continue
            blocks.append("  \n".join(lines))
        return "\n\n".join(blocks).strip()

    def _markdown_blocks(self, result) -> list[MarkdownBlock]:
        blocks: list[MarkdownBlock] = []
        for paragraph in getattr(result, "paragraphs", []):
            lines = self._paragraph_lines(paragraph)
            if not lines:
                continue
            bbox = getattr(paragraph, "bounding_box", None)
            if bbox is None:
                continue
            blocks.append(
                MarkdownBlock(
                    text="\n".join(lines).strip(),
                    center_x=float(getattr(bbox, "center_x", 0.0)),
                    center_y=float(getattr(bbox, "center_y", 0.0)),
                    width=float(getattr(bbox, "width", 0.0)),
                    height=float(getattr(bbox, "height", 0.0)),
                )
            )
        return blocks

    def _group_blocks_into_rows(self, blocks: list[MarkdownBlock]) -> list[list[MarkdownBlock]]:
        rows: list[list[MarkdownBlock]] = []
        for block in sorted(blocks, key=lambda item: (item.center_y, item.center_x)):
            if not rows:
                rows.append([block])
                continue
            current_row = rows[-1]
            row_y = sum(item.center_y for item in current_row) / len(current_row)
            row_height = max((item.height for item in current_row), default=0.0)
            threshold = max(0.012, row_height * 0.75, block.height * 0.75)
            if abs(block.center_y - row_y) <= threshold:
                current_row.append(block)
            else:
                rows.append([block])
        for row in rows:
            row.sort(key=lambda item: item.center_x)
        return rows


    def _rows_to_markdown_sections(self, rows: list[list[MarkdownBlock]]) -> list[str]:
        sections: list[str] = []
        body_buffer: list[list[MarkdownBlock]] = []
        index = 0
        while index < len(rows):
            table_end = self._find_table_region_end(rows, index)
            if table_end is not None:
                sections.extend(self._flush_body_rows(body_buffer))
                body_buffer = []
                region_sections = self._render_table_region(rows[index:table_end])
                if region_sections:
                    sections.extend(region_sections)
                    index = table_end
                    continue
            body_buffer.append(rows[index])
            index += 1
        sections.extend(self._flush_body_rows(body_buffer))
        return [section for section in sections if section]

    def _find_table_region_end(self, rows: list[list[MarkdownBlock]], start: int) -> int | None:
        if len(rows[start]) < 2:
            return None
        end = start
        while end < len(rows):
            row = rows[end]
            if len(row) < 2:
                break
            if end > start:
                prev_y = sum(item.center_y for item in rows[end - 1]) / len(rows[end - 1])
                curr_y = sum(item.center_y for item in row) / len(row)
                if curr_y - prev_y > 0.035:
                    break
            end += 1
        if end - start < 2:
            return None
        return end

    def _render_table_region(self, rows: list[list[MarkdownBlock]]) -> list[str]:
        column_centers = self._cluster_column_centers(rows)
        if len(column_centers) < 2 or len(column_centers) > 6:
            return []

        sections: list[str] = []
        table_rows: list[list[MarkdownBlock]] = []
        body_rows: list[list[MarkdownBlock]] = []

        for row in rows:
            table_blocks, body_blocks = self._split_row_blocks_for_table(row, column_centers)
            if len(table_blocks) >= 2:
                if body_rows:
                    sections.extend(self._flush_body_rows(body_rows))
                    body_rows = []
                table_rows.append(table_blocks)
            else:
                if table_rows:
                    table = self._render_table(table_rows)
                    if table:
                        sections.append(table)
                    table_rows = []
            if body_blocks:
                if table_rows:
                    table = self._render_table(table_rows)
                    if table:
                        sections.append(table)
                    table_rows = []
                body_rows.append(body_blocks)

        if table_rows:
            table = self._render_table(table_rows)
            if table:
                sections.append(table)
        if body_rows:
            sections.extend(self._flush_body_rows(body_rows))
        return sections

    def _render_table(self, rows: list[list[MarkdownBlock]]) -> str:
        column_centers = self._cluster_column_centers(rows)
        if len(column_centers) < 2 or len(column_centers) > 6:
            return ""

        grid: list[list[str]] = []
        for row in rows:
            cells = [""] * len(column_centers)
            for block in row:
                column_index = min(
                    range(len(column_centers)),
                    key=lambda idx: abs(block.center_x - column_centers[idx]),
                )
                cell_text = block.text.replace("\n", "<br>")
                cells[column_index] = f"{cells[column_index]}<br>{cell_text}".strip("<br>") if cells[column_index] else cell_text
            if sum(1 for cell in cells if cell) >= 2:
                grid.append(cells)

        if len(grid) < 2:
            return ""

        header = [self._escape_markdown_table_text(cell or f"Col {idx + 1}") for idx, cell in enumerate(grid[0])]
        separator = ["---"] * len(header)
        body = [
            [self._escape_markdown_table_text(cell) for cell in row]
            for row in grid[1:]
        ]
        lines = [
            f"| {' | '.join(header)} |",
            f"| {' | '.join(separator)} |",
        ]
        lines.extend(f"| {' | '.join(row)} |" for row in body)
        return "\n".join(lines)

    def _is_table_row(self, row: list[MarkdownBlock], column_centers: list[float]) -> bool:
        if len(row) < 2:
            return False
        matched = 0
        for block in row:
            if not block.text.strip():
                continue
            distance = min(abs(block.center_x - center) for center in column_centers)
            if distance <= 0.05:
                matched += 1
        return matched >= 2

    def _split_row_blocks_for_table(
        self,
        row: list[MarkdownBlock],
        column_centers: list[float],
    ) -> tuple[list[MarkdownBlock], list[MarkdownBlock]]:
        table_blocks: list[MarkdownBlock] = []
        body_blocks: list[MarkdownBlock] = []
        occupied_columns: set[int] = set()

        for block in row:
            text = block.text.strip()
            if not text:
                continue

            column_index = min(
                range(len(column_centers)),
                key=lambda idx: abs(block.center_x - column_centers[idx]),
            )
            distance = abs(block.center_x - column_centers[column_index])

            if distance > 0.05:
                body_blocks.append(block)
                continue
            if column_index in occupied_columns:
                body_blocks.append(block)
                continue
            if self._should_treat_block_as_body(block, column_index, column_centers):
                body_blocks.append(block)
                continue

            occupied_columns.add(column_index)
            table_blocks.append(block)

        return table_blocks, body_blocks

    def _should_treat_block_as_body(
        self,
        block: MarkdownBlock,
        column_index: int,
        column_centers: list[float],
    ) -> bool:
        if len(column_centers) < 2:
            return False

        column_left, column_right = self._column_bounds(column_centers, column_index)
        overlap_ratio = self._column_overlap_ratio(block, column_left, column_right)
        if column_index == 0:
            return overlap_ratio < 0.92
        if column_index == len(column_centers) - 1:
            return overlap_ratio < 0.70
        return overlap_ratio < 0.80

    def _column_bounds(self, column_centers: list[float], column_index: int) -> tuple[float, float]:
        left_bound = 0.0 if column_index == 0 else (column_centers[column_index - 1] + column_centers[column_index]) / 2
        right_bound = 1.0 if column_index == len(column_centers) - 1 else (column_centers[column_index] + column_centers[column_index + 1]) / 2
        return left_bound, right_bound

    def _column_overlap_ratio(self, block: MarkdownBlock, column_left: float, column_right: float) -> float:
        block_left = max(0.0, block.center_x - block.width / 2)
        block_right = min(1.0, block.center_x + block.width / 2)
        block_width = max(block_right - block_left, 1e-6)
        overlap_left = max(block_left, column_left)
        overlap_right = min(block_right, column_right)
        overlap_width = max(0.0, overlap_right - overlap_left)
        return overlap_width / block_width

    def _cluster_column_centers(self, rows: list[list[MarkdownBlock]]) -> list[float]:
        centers: list[dict[str, float]] = []
        for row in rows:
            for block in row:
                for cluster in centers:
                    if abs(block.center_x - cluster["center"]) <= 0.045:
                        cluster["center"] = (cluster["center"] * cluster["count"] + block.center_x) / (cluster["count"] + 1)
                        cluster["count"] += 1
                        break
                else:
                    centers.append({"center": block.center_x, "count": 1})

        repeated = [cluster["center"] for cluster in centers if cluster["count"] >= 2]
        if len(repeated) >= 2:
            return sorted(repeated)
        return sorted(cluster["center"] for cluster in centers)

    def _escape_markdown_table_text(self, text: str) -> str:
        value = text.strip()
        if not value:
            return ""
        return value.replace("|", "\\|")

    def _render_row_as_text(self, row: list[MarkdownBlock]) -> str:
        parts = [block.text for block in row if block.text]
        if not parts:
            return ""
        if len(parts) == 1:
            lines = [line.strip() for line in parts[0].splitlines() if line.strip()]
            return self._paragraph_lines_to_markdown(lines)
        return "\n".join(self._normalize_bullet(part) or part for part in parts)

    def _flush_body_rows(self, rows: list[list[MarkdownBlock]]) -> list[str]:
        if not rows:
            return []

        merged_rows: list[list[list[MarkdownBlock]]] = []
        for row in rows:
            if not merged_rows:
                merged_rows.append([row])
                continue
            if self._should_merge_body_rows(merged_rows[-1][-1], row):
                merged_rows[-1].append(row)
            else:
                merged_rows.append([row])

        sections: list[str] = []
        for group in merged_rows:
            lines = [self._row_to_body_line(row) for row in group]
            lines = [line for line in lines if line]
            if not lines:
                continue
            if len(lines) == 1:
                sections.append(self._paragraph_lines_to_markdown(lines))
            else:
                sections.append("\n".join(lines))
        return sections

    def _should_merge_body_rows(self, previous: list[MarkdownBlock], current: list[MarkdownBlock]) -> bool:
        if len(previous) > 1 or len(current) > 1:
            return False

        previous_block = previous[0]
        current_block = current[0]
        previous_text = previous_block.text.strip()
        current_text = current_block.text.strip()
        if not previous_text or not current_text:
            return False

        vertical_gap = current_block.center_y - previous_block.center_y
        if vertical_gap > 0.035:
            return False

        if self._looks_like_heading(previous_text) or self._looks_like_heading(current_text):
            return False

        if current_text.startswith(("、", "。", "を", "が", "に", "で", "と", "は")):
            return True
        if previous_text.startswith("※") or current_text.startswith("※"):
            return True

        left_gap = abs((previous_block.center_x - previous_block.width / 2) - (current_block.center_x - current_block.width / 2))
        if left_gap <= 0.04 and (
            previous_block.width >= 0.08 or current_block.width >= 0.08
        ):
            return True

        return False

    def _row_to_body_line(self, row: list[MarkdownBlock]) -> str:
        parts = [block.text.strip() for block in row if block.text.strip()]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        return " ".join(parts)

    def _paragraph_lines(self, paragraph) -> list[str]:
        lines: list[str] = []
        for line in getattr(paragraph, "lines", []):
            line_text = getattr(line, "text", None)
            if not line_text:
                words = getattr(line, "words", []) or []
                line_text = " ".join(word.text for word in words if getattr(word, "text", ""))
            line_text = (line_text or "").strip()
            if line_text:
                lines.append(line_text)
        return self._merge_fragmented_lines(lines)

    def _paragraph_lines_to_markdown(self, lines: list[str]) -> str:
        if len(lines) == 1:
            line = lines[0]
            if self._looks_like_heading(line):
                return f"## {line}"
            bullet = self._normalize_bullet(line)
            if bullet is not None:
                return bullet
            return line

        bullet_lines = [self._normalize_bullet(line) for line in lines]
        if all(bullet is not None for bullet in bullet_lines):
            return "\n".join(bullet_lines)
        return "\n".join(lines)

    def _normalize_bullet(self, line: str) -> str | None:
        match = re.match(r"^\s*(?:[-*•●▪◦※]|[0-9]+[.)])\s+(.*\S)\s*$", line)
        if not match:
            return None
        return f"- {match.group(1)}"

    def _merge_fragmented_lines(self, lines: list[str]) -> list[str]:
        merged: list[str] = []
        for line in lines:
            if not merged:
                merged.append(line)
                continue
            previous = merged[-1]
            if self._should_merge_lines(previous, line):
                merged[-1] = self._join_lines(previous, line)
            else:
                merged.append(line)
        return merged

    def _should_merge_lines(self, previous: str, current: str) -> bool:
        prev = previous.strip()
        curr = current.strip()
        if not prev or not curr:
            return False
        if len(prev) == 1 or len(curr) == 1:
            return True
        token_pattern = r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9]+"
        if re.fullmatch(token_pattern, prev) and re.fullmatch(token_pattern, curr):
            return True
        if not re.search(r"[。.!?]$", prev) and len(prev) <= 20 and len(curr) <= 20:
            return True
        return False

    def _join_lines(self, previous: str, current: str) -> str:
        if re.search(r"[A-Za-z0-9]$", previous) and re.match(r"^[A-Za-z0-9]", current):
            return f"{previous} {current}"
        return f"{previous}{current}"

    def _looks_like_heading(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if len(stripped) < 2:
            return False
        if len(stripped) > 80:
            return False
        if re.search(r"[.!?;:]$", stripped):
            return False
        if re.fullmatch(r"[0-9０-９/()~〜\-:：\s]+", stripped):
            return False
        words = stripped.split()
        alphabetic = [word for word in words if re.search(r"[A-Za-z]", word)]
        contains_cjk = bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", stripped))
        if contains_cjk:
            return len(stripped) <= 40 and not re.search(r"[。！？]", stripped)
        if not words or len(words) > 10:
            return False
        if stripped.isupper() and alphabetic:
            return True
        titled = sum(1 for word in alphabetic if word[:1].isupper())
        return bool(alphabetic) and titled >= max(1, len(alphabetic) - 1)

    def build_env(self, work_dir: Path) -> dict[str, str]:
        temp_dir = work_dir / "tmp"
        home_dir = self.config.base_dir / ".owocr_home"
        config_dir = home_dir / ".config"
        temp_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["TMP"] = str(temp_dir)
        env["TEMP"] = str(temp_dir)
        if platform.system().lower() != "linux":
            env["HOME"] = str(home_dir)
            env["USERPROFILE"] = str(home_dir)
        env["PYTHONIOENCODING"] = "utf-8"
        system_site_packages = "/usr/lib/python3/dist-packages"
        existing_pythonpath = env.get("PYTHONPATH", "").strip()
        pythonpath_parts = [part for part in existing_pythonpath.split(os.pathsep) if part]
        if system_site_packages not in pythonpath_parts and Path(system_site_packages).exists():
            pythonpath_parts.append(system_site_packages)
        if pythonpath_parts:
            env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
        return env

    def _patch_screenai_download(self, chrome_screen_ai_cls) -> None:
        if platform.system().lower() != "linux":
            return
        if getattr(chrome_screen_ai_cls, "_pdf_ocr_linux_patch", False):
            return

        original = chrome_screen_ai_cls._download_files_if_needed

        def _download_files_if_needed(instance):
            dll_name = "chrome_screen_ai.dll" if os.name == "nt" else "libchromescreenai.so"
            if (instance.model_dir / dll_name).exists():
                return True

            import subprocess
            import shutil
            import tempfile
            import urllib.request
            import pwd

            target_path = instance.model_dir.parent
            real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
            shared_cache = real_home / ".config" / "screen_ai"
            shared_lib = shared_cache / "resources" / dll_name
            if target_path == shared_cache and shared_lib.exists():
                return True
            if shared_lib.exists():
                if target_path.exists():
                    self._clear_directory(target_path)
                shutil.copytree(shared_cache, target_path, dirs_exist_ok=True)
                return True

            if target_path.exists():
                self._clear_directory(target_path)
            os_name = platform.system().lower()
            arch = platform.machine().lower()
            if os_name == "darwin":
                os_name = "mac"
            if arch in ("x86_64", "amd64"):
                arch = "amd64"
            elif arch in ("aarch64", "arm64"):
                arch = "arm64"
            elif arch in ("x86", "i386", "i686"):
                arch = "386"

            cipd_platform = f"{os_name}-{arch}"
            package_name = "chromium/third_party/screen-ai/linux"
            ensure_content = f"{package_name} latest\n"

            with tempfile.TemporaryDirectory() as temp_dir:
                cipd_bin = "cipd.exe" if os.name == "nt" else "cipd"
                cipd_path = os.path.join(temp_dir, cipd_bin)
                cipd_url = (
                    f"https://chrome-infra-packages.appspot.com/client"
                    f"?platform={cipd_platform}&version=latest"
                )

                try:
                    urllib.request.urlretrieve(cipd_url, cipd_path)
                    if os.name != "nt":
                        os.chmod(cipd_path, 0o755)
                except Exception:
                    return original(instance)

                cmd = [cipd_path, "export", "-root", str(target_path), "-ensure-file", "-"]
                try:
                    subprocess.run(cmd, input=ensure_content, text=True, check=True)
                except Exception:
                    return original(instance)

            return True

        chrome_screen_ai_cls._download_files_if_needed = _download_files_if_needed
        chrome_screen_ai_cls._pdf_ocr_linux_patch = True

    def _clear_directory(self, path: Path) -> None:
        for child in path.iterdir():
            if child.is_dir() and not child.is_symlink():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()

    def _mock_text(self, image_paths: list[Path], progress_callback: ProgressCallback) -> tuple[str, str]:
        total = len(image_paths)
        text_pages: list[str] = []
        markdown_pages: list[str] = []
        for index, image_path in enumerate(image_paths, start=1):
            progress_callback("ocr", f"Mock owocr processing page {index}/{total}", index, total)
            body = (
                f"[mock page {index}]\n"
                f"Source image: {image_path.name}\n"
                f"This simulates Chrome Screen AI text output."
            )
            text_pages.append(body)
            markdown_pages.append(f"## Page {index}\n\n### Mock OCR\n\n{body}")
        return "\n\n".join(text_pages), "\n\n".join(markdown_pages)
