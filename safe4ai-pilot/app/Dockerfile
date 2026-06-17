FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    poppler-utils \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade \
    pip==26.1.2 \
    setuptools==81.0.0 \
    wheel==0.46.2 \
    jaraco.context==6.1.0

COPY pyproject.toml .
COPY app/ ./app/
COPY observability/ ./observability/
COPY scripts/ ./scripts/

RUN python -m pip install --no-cache-dir --timeout 300 torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu
RUN python -m pip install --no-cache-dir -e .

# Pre-bake cross-encoder to avoid runtime HuggingFace download in air-gapped deployments
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
