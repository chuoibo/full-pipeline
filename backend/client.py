import asyncio
import websockets
import json
import logging
import pyaudio
import queue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('asr_client')

class ASRClient:
    def __init__(self, server_url='ws://localhost:5000'):
        self.server_url = server_url
        self.websocket = None
        self.is_connected = False
        self.is_streaming = False
        
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16
        self.chunk_size = 480  
        
        self.audio = pyaudio.PyAudio()
        
        self.audio_queue = queue.Queue()
        
        self.transcription_callback = None
        
    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.is_connected = True
            logger.info(f"Connected to ASR server at {self.server_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to ASR server: {e}")
            return False
            
    async def disconnect(self):
        self.is_streaming = False
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info(f"Disconnected from ASR server")
            
    def audio_callback(self, in_data, frame_count, time_info, status):
        if self.is_streaming and self.is_connected:
            self.audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)
        
    async def audio_sender(self):
        while self.is_streaming and self.is_connected:
            try:
                try:
                    audio_data = self.audio_queue.get(block=True, timeout=0.1)
                except queue.Empty:
                    continue
                
                await self.websocket.send(audio_data)
                self.audio_queue.task_done()
            except Exception as e:
                logger.error(f"Error in audio sender: {e}")
                if not self.is_connected:
                    break
            
            await asyncio.sleep(0.001)
            
    async def start_streaming(self):
        if not self.is_connected:
            logger.error("Not connected to ASR server")
            return False
            
        # Open audio stream
        self.stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self.audio_callback
        )
        
        self.is_streaming = True
        self.stream.start_stream()
        logger.info("Started audio streaming")
        
        asyncio.create_task(self.audio_sender())
        
        return True
        
    async def stop_streaming(self):
        self.is_streaming = False
        
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()
            logger.info("Stopped audio streaming")
    
    def set_transcription_callback(self, callback):
        self.transcription_callback = callback
            
    async def listen_continuously(self):
        if not self.is_connected:
            logger.error("Not connected to ASR server")
            return
            
        try:
            while self.is_connected:
                response = await self.websocket.recv()
                try:
                    response_json = json.loads(response)
                    
                    if "text" in response_json:
                        current_text = response_json["text"]
                        logger.info(f"Received transcription: {current_text}")
                    
                    if response_json.get("reset_session", False) and "text" in response_json:
                        final_text = response_json["text"]
                        logger.info(f"Final transcription received (reset_session=True): {final_text}")
                        
                        if self.transcription_callback:
                            asyncio.create_task(self.transcription_callback(final_text))
                        
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON response: {response}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection to ASR server closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error in continuous listener: {e}")
    

    async def listen_for_transcription(self):
        if not self.is_connected:
            logger.error("Not connected to ASR server")
            return None
            
        try:
            while self.is_connected:
                response = await self.websocket.recv()
                try:
                    response_json = json.loads(response)
                    
                    if "text" in response_json:
                        current_text = response_json["text"]
                        logger.info(f"Received transcription: {current_text}")
                    
                    if response_json.get("reset_session", False) and "text" in response_json:
                        final_text = response_json["text"]
                        logger.info(f"Final transcription received (reset_session=True): {final_text}")
                        return final_text
                        
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON response: {response}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection to ASR server closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error receiving transcription: {e}")
            
        return None

async def process_transcription(text):
    print(f"\nProcessing transcription: {text}")

async def continuous_main():
    """Example of continuous listening mode"""
    client = ASRClient('ws://localhost:5000')
    
    if not await client.connect():
        return
    
    try:
        client.set_transcription_callback(process_transcription)
        
        await client.start_streaming()
        
        print("Speak now... (Ctrl+C to exit)")
        print("The system will continuously listen and process each utterance")
        
        await client.listen_continuously()
            
    finally:
        await client.stop_streaming()
        await client.disconnect()
        client.audio.terminate()

async def single_transcription_main():
    client = ASRClient('ws://localhost:5000')
    
    if not await client.connect():
        return
    
    try:    
        await client.start_streaming()
        
        print("Speak now... (Ctrl+C to exit)")
        
        final_text = await client.listen_for_transcription()
        
        if final_text:
            print(f"\nFinal transcription: {final_text}")
        else:
            print("\nNo transcription received.")
            
    finally:
        # Clean up
        await client.stop_streaming()
        await client.disconnect()
        client.audio.terminate()

if __name__ == "__main__":
    try:
        asyncio.run(continuous_main())

    except KeyboardInterrupt:
        print("\nClient stopped by user")
    except Exception as e:
        logger.error(f"Client error: {e}")