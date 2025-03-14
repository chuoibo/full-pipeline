import asyncio
import os
import json
from google import genai
from pydub import AudioSegment
import edge_tts
import re
import time
from io import BytesIO
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('tts_server')

load_dotenv()

def preprocess_text(text):    
    text = re.sub(r'\bunk\b', '', text)
    return text

def gemini_text_generator(query: str):
    logging.info(f"Received query: {query}")
    client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'), vertexai=False)
    chat = client.chats.create(model="gemini-2.0-flash-001")
    
    pattern = re.compile(r'[.!?:]\s*')
    
    preprocess_query = preprocess_text(query)
    
    buffer = ""
    
    for chunk in chat.send_message_stream(preprocess_query):
        clean_text = chunk.text.replace("*", "")
        buffer += clean_text
        
        while True:
            match = pattern.search(buffer)
            
            if match:
                sentence = buffer[:match.end()].strip()
                yield sentence
                buffer = buffer[match.end():]
            else:
                break
    
    if buffer.strip():
        yield buffer.strip()

async def text_to_speech_stream(query: str):
    voice = "vi-VN-HoaiMyNeural"
    
    gen_text = gemini_text_generator(query)
    
    for chunk in gen_text:
        
        if not chunk or not chunk.strip():
            continue
        
        start_time_chunk = time.time()
        communicate = edge_tts.Communicate(chunk, voice)
        audio_data = bytearray()
        async for tts_chunk in communicate.stream():
            if tts_chunk["type"] == "audio":
                audio_data.extend(tts_chunk["data"])
    
        
        audio_segment = AudioSegment.from_mp3(BytesIO(audio_data))
        duration_seconds = len(audio_segment) / 1000.0
 
        processing_time = time.time() - start_time_chunk
        
        sleep_time = max(0, duration_seconds - processing_time)
        
        data = {
            "text": chunk,
            "audio": audio_data.hex(),
            "duration": sleep_time
        }
        yield f"event: ttsUpdate\ndata: {json.dumps(data)}\n\n"

        logging.info('Finish Chunk ---------------------')
        
        await asyncio.sleep(sleep_time)
 



