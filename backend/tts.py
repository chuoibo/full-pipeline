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

load_dotenv()

def get_last_word(text):
    matches = re.findall(r'[\w.]+', text)
    return matches[-1] if matches else ""

def incomplete_abbreviation(last_word, abbreviations):
    last_word_lower = last_word.lower()
    for abbr in abbreviations:
        if abbr.startswith(last_word_lower) and last_word_lower != abbr:
            return True
    return False

def gemini_text_generator(query: str):
    client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'), vertexai=False)
    chat = client.chats.create(model="gemini-2.0-flash-001")
    
    abbreviations = {"e.g.", "i.e.", "w.r.t.", "etc."}
    pattern = re.compile(r'\.\s*')

    prompt = f""" 
        Câu câu nói đầu vào của người dùng đã được xử lý bằng công nghệ nhận diện giọng nói tự động, điều này có thể xảy ra nhiễu hoặc sai sót trong câu từ, phiên âm. 
        Trước khi trả lời, hãy phân tích kỹ lưỡng ngữ cảnh tổng thể của câu nói đầu vào để đảm bảo câu trả lời chính xác và phù hợp:

        Đây là câu nói đầu vào: {query}
    """
    
    buffer = ""
    for chunk in chat.send_message_stream(prompt):
        clean_text = chunk.text.replace("*", "")
        buffer += clean_text
        
        while True:
            all_matches = list(pattern.finditer(buffer))
            if not all_matches:
                break
            
            selected_match = None
            for m in all_matches:
                candidate_sentence = buffer[:m.end()].strip()
                last_word = get_last_word(candidate_sentence)
                if not incomplete_abbreviation(last_word, abbreviations):
                    selected_match = m
                    break
            
            if selected_match is None:
                break
            
            sentence = buffer[:selected_match.end()].strip()
            if sentence:
                yield sentence
            buffer = buffer[selected_match.end():]
    
    if buffer.strip():
        yield buffer.strip()

async def text_to_speech_stream(query: str):
    voice = "vi-VN-HoaiMyNeural"
    
    gen_text = gemini_text_generator(query)
    
    total_duration = 0
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
        
        await asyncio.sleep(sleep_time)
    
    final_delay = max(0, total_duration)
    if final_delay > 0:
        yield f"event: ttsEnd\ndata: {json.dumps({'message': 'TTS completed', 'delay': final_delay})}\n\n"
        await asyncio.sleep(final_delay)
