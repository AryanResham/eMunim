FROM python:3.12-slim
ARG TORCH_VERSION=2.11.0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/hf-cache HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
WORKDIR /app/backend
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
# Install the CPU build first; the application requirement accepts this version.
RUN pip install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt
COPY backend/ ./
EXPOSE 8000
CMD ["sh", "-c", "python manage.py init-db && exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
