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

CMD ["streamlit", "run", "app.py"]
