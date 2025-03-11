import asyncio
import uvicorn
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sys
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from asr import ASRWebSocketServer
from tts import app as tts_app

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/tts", tts_app)

app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

def preprocess_text(text):
    text = re.sub(r'[.,!?;:"\'-]', '', text)
    text = ' '.join(text.split())
    
    return text

def run_asr_server():
    asr_server = ASRWebSocketServer()
    asyncio.run(asr_server.start_server())

if __name__ == "__main__":
    asr_thread = threading.Thread(target=run_asr_server)
    asr_thread.daemon = True
    asr_thread.start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)