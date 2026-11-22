# Card reader service (specs/006-card-ocr research.md R2). Built with internet; runs without it.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    YOLO_OFFLINE=1 \
    YOLO_CONFIG_DIR=/app/.ultralytics \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    PADDLE_PDX_CACHE_HOME=/models/paddlex \
    OMP_NUM_THREADS=2 \
    WEIGHTS_DIR=/app/upstream/models/weights

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch first, so ultralytics does not pull the CUDA wheels (~2 GB).
RUN pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu

# Upstream, with its exact pins.
COPY upstream/requirements.txt upstream/pyproject.toml upstream/README.md upstream/LICENSE upstream/
COPY upstream/src upstream/src
RUN pip install -r upstream/requirements.txt && pip install --no-deps -e upstream

# Our thin HTTP wrapper.
COPY service-requirements.txt ./
RUN pip install -r service-requirements.txt

# Weights from the v1.0.0 release, verified against SHA256SUMS (the build fails on a mismatch).
COPY upstream/models upstream/models
COPY upstream/scripts upstream/scripts
RUN python upstream/scripts/download_weights.py \
      --base-url https://github.com/Hai800Z/ID_Iraqi_Project/releases/download/v1.0.0 \
    && python upstream/scripts/download_weights.py --verify

# The Arabic text recognition model, fetched now so the service never needs the network.
RUN python -c "from paddleocr import TextRecognition; TextRecognition(model_name='arabic_PP-OCRv5_mobile_rec', device='cpu')"

COPY LICENSE UPSTREAM.md ./
COPY service service
COPY tests tests

RUN useradd --create-home --uid 10002 ocr \
    && mkdir -p /app/.ultralytics && chown -R ocr:ocr /app/.ultralytics /models

USER ocr
EXPOSE 8080
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
