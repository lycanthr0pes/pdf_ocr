from __future__ import annotations

from pathlib import Path

import fitz


def render_pdf_to_images(
    pdf_path: Path,
    output_dir: Path,
    dpi: int,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output_path = output_dir / f"page_{index:04d}.png"
            pixmap.save(output_path)
            image_paths.append(output_path)

    return image_paths
