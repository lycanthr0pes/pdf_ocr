FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    XDG_CONFIG_HOME=/root/.config \
    APP_BASE_DIR=/app \
    INPUT_DIR=data/input \
    WORK_DIR=data/work \
    OUTPUT_DIR=data/output \
    PDF_RENDER_DPI=220 \
    ALLOW_MOCK_OCR=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        libcairo2-dev \
        libglib2.0-0 \
        libgomp1 \
        libgirepository-1.0-dev \
        libwayland-dev \
        pkg-config \
        python3-gi \
        python3-dev \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip install \
        "cffi>=1.17.1" \
        "protobuf>=6.33.2" \
        "jaconv>=0.5.0" \
        "loguru>=0.7.3" \
        "pynputfix>=1.8.2" \
        "websockets>=16.0" \
        "desktop-notifier>=6.2.0" \
        "pystrayfix>=0.19.8" \
        "mss>=10.1.0" \
        "obsws-python>=1.8.0" \
        "psutil>=7.2.2" \
        "curl_cffi>=0.15.0" \
        "pyperclip>=1.11.0" \
        "pywayland>=0.4.18" \
        "owocr==1.26.8" --no-deps

COPY app.py .
COPY ocr_app ./ocr_app
COPY README.md .
COPY LICENSE .
COPY THIRD_PARTY_NOTICES.md .

RUN mkdir -p /app/data/input /app/data/output /app/data/work /app/.owocr_home /app/.tmp /root/.config/screen_ai

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl --fail http://127.0.0.1:8501/_stcore/health || exit 1

ENTRYPOINT ["tini", "--"]

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
