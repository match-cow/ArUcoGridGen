FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install Poppler (required for pdf2image)
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install dependencies first (for Docker layer caching)
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# Copy application files
COPY app.py ./
COPY static/ ./static/
COPY .streamlit/ ./.streamlit/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"]

CMD ["streamlit", "run", "app.py"]
