FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install Poppler (required for pdf2image)
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN uv pip install --system .

CMD ["streamlit", "run", "app.py"]
