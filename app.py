from __future__ import annotations

from pathlib import Path

import streamlit as st

from ocr_app.config import AppConfig, load_config
from ocr_app.orchestrator import OcrOrchestrator


st.set_page_config(page_title="PDF OCR Prototype", layout="wide")


def _init_state() -> None:
    if "job_result" not in st.session_state:
        st.session_state.job_result = None


def _save_uploaded_pdf(uploaded_file, config: AppConfig) -> Path:
    target_path = config.input_dir / uploaded_file.name
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path


def _render_sidebar(config: AppConfig) -> None:
    st.sidebar.header("Configuration")
    st.sidebar.write(f"Input Dir: `{config.input_dir}`")
    st.sidebar.write(f"Work Dir: `{config.work_dir}`")
    st.sidebar.write(f"Output Dir: `{config.output_dir}`")
    st.sidebar.write(f"DPI: `{config.pdf_render_dpi}`")
    st.sidebar.write(f"Mock OCR Enabled: `{config.allow_mock_ocr}`")
    if config.allow_mock_ocr:
        st.sidebar.info(
            "owocr is not fully configured yet. "
            "The app will fall back to mock OCR output so we can verify the flow."
        )


def main() -> None:
    _init_state()
    config = load_config()
    orchestrator = OcrOrchestrator(config)

    st.title("PDF OCR Prototype")
    st.caption("PDF -> page images -> owocr (Chrome Screen AI) -> text output")

    _render_sidebar(config)

    local_pdfs = sorted(config.input_dir.glob("*.pdf"))

    st.subheader("Select PDF")
    selected_local = st.selectbox(
        "Local PDF list",
        options=[""] + [pdf.name for pdf in local_pdfs],
        help="Files are loaded from the configured input directory.",
    )
    uploaded_file = st.file_uploader(
        "Or drag and drop a PDF here",
        type=["pdf"],
        accept_multiple_files=False,
    )
    st.info("OCR engine: `owocr (Chrome Screen AI)`")

    selected_pdf_path: Path | None = None
    if uploaded_file is not None:
        selected_pdf_path = _save_uploaded_pdf(uploaded_file, config)
        st.success(f"Uploaded: `{selected_pdf_path.name}`")
    elif selected_local:
        selected_pdf_path = config.input_dir / selected_local
        st.info(f"Selected local file: `{selected_pdf_path.name}`")

    run_disabled = selected_pdf_path is None
    run_clicked = st.button("Start OCR", type="primary", disabled=run_disabled)

    if run_clicked and selected_pdf_path is not None:
        status_box = st.empty()
        progress_bar = st.progress(0.0)
        log_box = st.empty()
        logs: list[str] = []

        def on_progress(stage: str, message: str, current: int, total: int) -> None:
            ratio = 0.0 if total <= 0 else min(current / total, 1.0)
            progress_bar.progress(ratio)
            status_box.write(f"**{stage}**: {message}")
            logs.append(f"[{stage}] {message}")
            log_box.code("\n".join(logs), language="text")

        try:
            st.session_state.job_result = orchestrator.run(
                pdf_path=selected_pdf_path,
                progress_callback=on_progress,
            )
            st.success("OCR completed.")
        except Exception as exc:  # pragma: no cover - Streamlit UI branch
            st.session_state.job_result = None
            st.error(f"OCR failed: {exc}")

    result = st.session_state.job_result
    if result is not None:
        st.subheader("Result")
        st.write(f"Engine: `{result.engine}`")
        st.write(f"Pages: `{result.page_count}`")
        st.write(f"Output: `{result.output_path.name}`")
        st.download_button(
            "Download output",
            data=result.output_path.read_bytes(),
            file_name=result.output_path.name,
            mime="text/plain",
        )
        with st.expander("Preview"):
            st.text(result.text[:6000] or "(empty)")


if __name__ == "__main__":
    main()
