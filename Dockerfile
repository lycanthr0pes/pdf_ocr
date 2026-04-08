FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    APP_BASE_DIR=/app \
    INPUT_DIR=data/input \
    WORK_DIR=data/work \
    OUTPUT_DIR=data/output \
    PDF_RENDER_DPI=220 \
    ALLOW_MOCK_OCR=false \
    OWOCR_EXECUTABLE=owocr \
    OWOCR_EXTRA_ARGS="-el=screenai -e=screenai -t=false -n=false"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip install "owocr[screenai]"

COPY app.py .
COPY ocr_app ./ocr_app
COPY README.md .
COPY LICENSE .
COPY THIRD_PARTY_NOTICES.md .
COPY .env.example .

RUN mkdir -p /app/data/input /app/data/output /app/data/work /app/.owocr_home /app/.tmp

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
