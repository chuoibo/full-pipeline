import asyncio
import os
import json
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from pydub import AudioSegment
import edge_tts
import re
import time
from io import BytesIO
from dotenv import load_dotenv
import uvicorn
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI()
app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_last_word(text):
    matches = re.findall(r'[\w.]+', text)
    return matches[-1] if matches else ""

def preprocess_text(text):    
    text = re.sub(r'\bunk\b', '', text)
    return text

def gemini_text_generator(query: str):
    # Start timing when Gemini receives the query
    gemini_start_time = time.time()
    
    client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'), vertexai=False)
    chat = client.chats.create(model="gemini-2.0-flash-001")
    
    pattern = re.compile(r'\.\s*')
    
    preprocess_query = preprocess_text(query)
    
    buffer = ""
    first_chunk = True
    generation_time = None
    
    for chunk in chat.send_message_stream(preprocess_query):
        if first_chunk:
            generation_time = time.time() - gemini_start_time
            print(f"Time from query to first generation: {generation_time:.4f} seconds")
            first_chunk = False
            
        clean_text = chunk.text.replace("*", "")
        buffer += clean_text
        
        while True:
            match = pattern.search(buffer)
            
            if match:
                sentence = buffer[:match.end()].strip()
                words = sentence.split()
                
                if len(words) <= 50:
                    yield sentence, gemini_start_time, generation_time
                    buffer = buffer[match.end():]
                else:
                    yield " ".join(words[:50]), gemini_start_time, generation_time
                    buffer = " ".join(words[50:]) + buffer[match.end():]
            else:
                words = buffer.split()
                if len(words) > 50:
                    yield " ".join(words[:50]), gemini_start_time, generation_time
                    buffer = " ".join(words[50:])
                else:
                    break
    
    buffer = buffer.strip()
    while buffer:
        words = buffer.split()
        if len(words) > 50:
            yield " ".join(words[:50]), gemini_start_time, generation_time
            buffer = " ".join(words[50:])
        else:
            yield buffer, gemini_start_time, generation_time
            buffer = ""

async def text_to_speech_stream(query: str):
    voice = "vi-VN-HoaiMyNeural"
    
    gen_text = gemini_text_generator(query)
    
    first_voice_stream = True
    first_voice_time = None
    
    for text_chunk_data in gen_text:
        chunk, gemini_start_time, generation_time = text_chunk_data
        
        if not chunk or not chunk.strip():
            break
        
        start_time_chunk = time.time()
        communicate = edge_tts.Communicate(chunk, voice)
        audio_data = bytearray()
        async for tts_chunk in communicate.stream():
            if tts_chunk["type"] == "audio":
                audio_data.extend(tts_chunk["data"])
        
        # Calculate time from query to first voice stream
        if first_voice_stream:
            first_voice_time = time.time() - gemini_start_time
            print(f"Time from query to first voice stream: {first_voice_time:.4f} seconds")
            first_voice_stream = False
        
        audio_segment = AudioSegment.from_mp3(BytesIO(audio_data))
        duration_seconds = len(audio_segment) / 1000.0
 
        processing_time = time.time() - start_time_chunk
        
        sleep_time = max(0, duration_seconds - processing_time)
        
        data = {
            "text": chunk,
            "audio": audio_data.hex(),
            "duration": sleep_time,
            "metrics": {
                "generation_time": generation_time,
                "first_voice_time": first_voice_time if first_voice_time is not None else None
            }
        }
        yield f"event: ttsUpdate\ndata: {json.dumps(data)}\n\n"
        
        await asyncio.sleep(sleep_time)
 

@app.get("/stream-tts")
async def stream_tts(query: str = Query(..., description="The query to process")):
    return StreamingResponse(text_to_speech_stream(query), media_type="text/event-stream")
