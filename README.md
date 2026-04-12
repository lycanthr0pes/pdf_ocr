# PDF OCR Prototype

Streamlit + Python app for this workflow:

1. Select a PDF from a local list or upload it.
2. Render every PDF page to images.
3. Run `owocr` with Chrome Screen AI.
4. Save the result as `.txt` and `.md`.

## Runtime

The primary supported runtime is Docker on Linux / WSL.

- `compose.yaml` is the default way to build and run the app.
- Real OCR is the default container mode.
- Chrome Screen AI assets are persisted in the `screen_ai_cache` Docker volume so the first large download is reused.

Repository structure:

```text
.
|-- app.py
|-- compose.yaml
|-- Dockerfile
|-- ocr_app/
|   |-- config.py
|   |-- models.py
|   |-- orchestrator.py
|   |-- pdf_renderer.py
|   `-- services/
|       `-- owocr_service.py
|-- data/
|   |-- input/
|   |-- output/
|   `-- work/
|-- requirements.txt
`-- .env.example
```

## Docker Setup

Create local directories if needed:

```bash
mkdir -p data/input data/output data/work
```

Build the image:

```bash
docker compose build
```

Start the app:

```bash
docker compose up
```

Then open `http://localhost:8501`.

The app runs without a local `.env` file. If you want to override defaults such as `ALLOW_MOCK_OCR` or `PDF_RENDER_DPI`, you can create `.env` later using `.env.example` as a template.

The container mounts these repository directories:

- `data/input` for source PDFs
- `data/work` for rendered page images and temporary OCR files
- `data/output` for `.txt` and `.md` results

The Screen AI runtime cache is stored in the Docker-managed `screen_ai_cache` volume. The first real OCR run downloads the model assets into that volume.

## Docker Smoke Test

This checks real OCR end to end inside the container:

```bash
docker compose run --rm app python - <<'PY'
from pathlib import Path
from ocr_app.config import load_config
from ocr_app.orchestrator import OcrOrchestrator

config = load_config()
config = config.__class__(
    base_dir=config.base_dir,
    input_dir=config.input_dir,
    work_dir=config.work_dir,
    output_dir=config.output_dir,
    pdf_render_dpi=config.pdf_render_dpi,
    allow_mock_ocr=False,
)

result = OcrOrchestrator(config).run(
    Path("data/input/sample_owocr_test.pdf"),
    lambda stage, message, current, total: print(f"[{stage}] {current}/{total} {message}"),
)
print(result.output_path)
print(result.markdown_path)
PY
```

## Local Dev Alternative

If you want to work outside Docker, use the Linux-side `.venv` in WSL. This is a development path, not the primary distribution path.

Create the environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps owocr==1.26.8
.venv/bin/python -m pip install cffi "protobuf>=6.33.2" jaconv loguru pynputfix websockets desktop-notifier pystrayfix mss obsws-python psutil curl_cffi pyperclip pywayland
```

Ubuntu / Debian packages:

```bash
sudo apt install -y python3-gi build-essential pkg-config libcairo2-dev libgirepository-1.0-dev libwayland-dev python3-dev
```

Arch Linux packages:

```bash
sudo pacman -Sy --noconfirm python-gobject cairo gobject-introspection base-devel pkgconf wayland
```

Run locally:

```bash
ALLOW_MOCK_OCR=false .venv/bin/streamlit run app.py
```

## Current Behavior

- The app is `owocr`-only and always uses Chrome Screen AI.
- The Markdown output is generated from `owocr` paragraph and line structure. It is heuristic Markdown, not native Markdown from `owocr`.
- If `ALLOW_MOCK_OCR=true`, the UI still runs with mock output for flow validation.
- On Linux, `ocr_app/services/owocr_service.py` applies a runtime patch so `owocr` can use the current `screen-ai/linux` package naming and Linux package layout.

## Third-Party Software

This project depends on `owocr` by AuroraWright for OCR processing.

- Project: `owocr`
- Author: AuroraWright
- Repository: https://github.com/AuroraWright/owocr
- License: GPL-3.0

`owocr` is provided and licensed separately by its original author. This repository does not claim ownership of `owocr` itself.

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE).
