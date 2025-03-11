import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
import re
from pathlib import Path
from asr import ASRWebSocketServer
from tts import text_to_speech_stream

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('server')

app = FastAPI(title="Speech Processing API")

app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def preprocess_text(text):
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\b[a-zA-Z]\b', '', text)
    text = re.sub(r'\bunk\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
    
asr_server = ASRWebSocketServer()

@app.websocket("/asr")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        await asr_server.handle_client(websocket)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {e}")
        await websocket.close()

@app.get("/tts")
async def tts_endpoint(query: str = Query(..., description="The text to convert to speech")):
    processed_text = preprocess_text(query)
    logger.info(f"Original text: {query}")
    logger.info(f"Processed text: {processed_text}")
    
    return StreamingResponse(
        text_to_speech_stream(processed_text),
        media_type="text/event-stream"
    )

@app.get("/")
async def read_root():
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    uvicorn.run("server:app", host=host, port=port, reload=True)