FROM python:3.10-slim

ENV HOST=0.0.0.0
ENV PORT=8000
ENV DEBUG=True

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn backend.app:app --host ${HOST} --port ${PORT}"]