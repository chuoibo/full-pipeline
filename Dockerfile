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

COPY scripts/dev.sh ./scripts/

COPY backend/asr.py ./backend/
COPY backend/app.py ./backend/

COPY frontend/index.html ./frontend/

EXPOSE ${PORT}
EXPOSE 5000

CMD ["sh", "scripts/dev.sh"]
