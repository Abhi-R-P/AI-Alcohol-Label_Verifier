FROM python:3.11-slim

# Tesseract is a system binary that pytesseract shells out to — it must be
# installed in the image or OCR fails at runtime with TesseractNotFoundError.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render/Railway inject $PORT; bind to it (default 8000 for local `docker run`).
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
