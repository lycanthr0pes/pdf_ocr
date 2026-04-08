# PDF OCR Prototype

Streamlit + Python prototype for validating this workflow:

1. Select a PDF from a local list or upload it.
2. Render every PDF page to images.
3. Run `owocr` with Chrome Screen AI.
4. Save the result as `.txt`.

## Structure

```text
.
|-- app.py
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

## Setup

```powershell
.\.venv_nopip\Scripts\Activate.ps1
Copy-Item .env.example .env
```

This repository currently uses `.venv_nopip` as the canonical local environment.
It already contains the verified `streamlit`, `PyMuPDF`, and `owocr[screenai]`
installation used during development and testing.

## Run

```powershell
.\.venv_nopip\Scripts\python.exe -m streamlit run app.py
```

## Docker

Build:

```powershell
docker build -t pdf-ocr-streamlit .
```

Run:

```powershell
docker run --rm -p 8501:8501 ^
  -v ${PWD}\\data\\input:/app/data/input ^
  -v ${PWD}\\data\\output:/app/data/output ^
  -v ${PWD}\\data\\work:/app/data/work ^
  pdf-ocr-streamlit
```

## Current behavior

- The app is `owocr`-only. It always runs `owocr` with Chrome Screen AI and writes `.txt`.
- The service uses the `owocr` Python package directly and calls Chrome Screen AI without going through the full CLI watcher flow.
- If `owocr` is not configured and `ALLOW_MOCK_OCR=true`, the app still runs with mock output so the UI and job flow can be validated.

## Notes on owocr

The `owocr` repository documents folder input via `-r=<folder path>` and file output via `-w=<txt file path>`, which matches this app's image-first pipeline. Recent `owocr` releases list Chrome Screen AI as a local engine and describe installation with `pip install "owocr[screenai]"`. This prototype therefore fixes the product requirement at the application level: when the user chooses `owocr`, the intended engine is Chrome Screen AI.

## Feasibility summary

This prototype confirms the architecture is practical in Streamlit:

- PDF pre-processing can be done up front with PyMuPDF.
- Streamlit can handle file upload, local-file selection, progress display, and result download in one screen.
- `owocr` fits cleanly behind a dedicated adapter class.

The remaining work for production use is mainly operational:

- verifying the local `owocr` installation and any version-specific Screen AI startup options
- handling longer jobs and cancellations more robustly
- improving logs and error recovery

## Third-Party Software

This project depends on `owocr` by AuroraWright for OCR processing.

- Project: `owocr`
- Author: AuroraWright
- Repository: https://github.com/AuroraWright/owocr
- License: GPL-3.0

`owocr` is provided and licensed separately by its original author. This repository does not claim ownership of `owocr` itself.

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE).
