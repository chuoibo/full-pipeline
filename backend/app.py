import asyncio
import logging
import re
import requests
import json
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.tts import text_to_speech_stream
from backend.client import ASRClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('full_pipeline')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")


active_asr_clients = {}

@app.get("/response")
def receive_response(query: str = Query(...)):
    """Process the query and return a response."""
    logger.info(f"Received query: {query}")
    processed_query = re.sub(r'\bunk\b', '', query)
    return processed_query


@app.websocket("/asr-tts-full-pipeline")
async def asr_tts_full_pipeline(websocket: WebSocket):
    """WebSocket endpoint for complete end-to-end ASR → Process → TTS pipeline"""
    await websocket.accept()
    client_id = id(websocket)
    
    logger.info(f"WebSocket connection established for client {client_id}")
    
    asr_client = ASRClient('ws://localhost:5000')
    active_asr_clients[client_id] = asr_client
    
    async def process_transcription_and_generate_tts(text):
        if not text:
            return
            
        await websocket.send_json({
            "type": "transcription",
            "data": text
        })
        
        processed_text = receive_response(query=text)
        
        await websocket.send_json({
            "type": "response",
            "data": processed_text
        })
        
        await websocket.send_json({
            "type": "tts_starting",
            "data": "Starting TTS audio stream"
        })
        
        try:
            tts_stream = text_to_speech_stream(processed_text)
            
            async for chunk in tts_stream:
                if not chunk:
                    continue
                    
                event_lines = chunk.split('\n')
                data_line = next((line for line in event_lines if line.startswith('data: ')), None)
                
                if data_line:
                    json_data = json.loads(data_line[6:]) 
                    
                    await websocket.send_json({
                        "type": "tts_update",
                        "data": json_data
                    })
            
            await websocket.send_json({
                "type": "tts_complete",
                "data": "TTS audio stream complete"
            })
            
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            await websocket.send_json({
                "type": "error",
                "data": f"TTS generation error: {str(e)}"
            })
        
    try:
        if not await asr_client.connect():
            await websocket.send_json({
                "type": "error",
                "data": "Failed to connect to ASR server"
            })
            return
            
        asr_client.set_transcription_callback(process_transcription_and_generate_tts)
        
        await asr_client.start_streaming()
        
        await websocket.send_json({
            "type": "status",
            "data": "ready"
        })
        
        await asr_client.listen_continuously()
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for client {client_id}")
    except Exception as e:
        logger.error(f"Error in ASR-TTS pipeline: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": str(e)
            })
        except:
            pass
    finally:
        # Clean up
        if client_id in active_asr_clients:
            await asr_client.stop_streaming()
            await asr_client.disconnect()
            del active_asr_clients[client_id]
            logger.info(f"Cleaned up resources for client {client_id}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)