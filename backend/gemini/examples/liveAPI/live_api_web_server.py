#!/usr/bin/env python3
"""
Gemini Live API Web + WebSocket Server
실제 웹 서버로 브라우저 접속 가능
"""

import asyncio
import json
import time
import base64
import os
import sys
sys.path.append('../../src')

from dotenv import load_dotenv
import websockets
from websockets.server import serve
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Pipecat Live API
from pipecat.services.gemini_multimodal_live.gemini import GeminiMultimodalLiveLLMService
from pipecat.frames.frames import TextFrame, ImageRawFrame
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from PIL import Image
import io

# Direct Live API
from google import genai
from google.genai import types

load_dotenv(override=True)

# FastAPI 앱 생성
app = FastAPI(title="Gemini Live API Web Server")

class MultimodalLiveAPIServer:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key or self.api_key == "...":
            raise ValueError("GOOGLE_API_KEY not found")
        
        # Multimodal Live API Client
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash-live-001"  # Live API 전용 모델
        # Live API configuration for real-time video streaming
        # Use TEXT as response modality to get text responses
        self.config = types.LiveConnectConfig(
            response_modalities=["TEXT"],  # Use TEXT to get text responses
            temperature=0.9,
            max_output_tokens=2048,
            system_instruction="You are an AI assistant that can analyze real-time video streams and images. Provide detailed descriptions and analysis of visual content."
        )
        
        # Fallback to regular Gemini for image processing
        import google.generativeai as gemini_ai
        gemini_ai.configure(api_key=self.api_key)
        self.fallback_model = gemini_ai.GenerativeModel('gemini-1.5-flash')
        
        # Pipecat service for compatibility
        self.llm = GeminiMultimodalLiveLLMService(
            api_key=self.api_key,
            voice_id="Aoede"
        )
        
        print(f"Multimodal Live API Server Initialized")
        print(f"Model: {self.model}")
        print(f"Supported Modalities: Text, Video Stream (Real-time)")
        print(f"Video Streaming: Enabled")
    
    def image_to_video_chunk(self, pil_image, duration_ms=500):
        """Convert PIL Image to video chunk for Live API streaming"""
        import cv2
        import numpy as np
        import io
        
        # Convert PIL to OpenCV format
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        
        # Create a short video from the image (e.g., 500ms)
        height, width = cv_image.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        # Create in-memory video
        temp_video = io.BytesIO()
        
        # Use a temporary file approach for video encoding
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Create video writer with WebM format
        fps = 10  # 10 FPS for 500ms = 5 frames  
        frames = int(fps * duration_ms / 1000)
        
        # Try MP4 format as it's explicitly supported
        fourcc_mp4 = cv2.VideoWriter_fourcc(*'mp4v')  # MP4 codec
        
        out = cv2.VideoWriter(temp_path, fourcc_mp4, fps, (width, height))
        
        # Write the same frame multiple times to create duration
        for _ in range(max(1, frames)):
            out.write(cv_image)
        
        out.release()
        
        # Read video bytes
        with open(temp_path, 'rb') as f:
            video_bytes = f.read()
        
        # Cleanup
        import os
        os.unlink(temp_path)
        
        return video_bytes

    async def process_multimodal_content(self, content_type, data, prompt=None):
        """Stable processing: Live API for text, regular Gemini for images"""
        start_time = time.time()
        
        try:
            if content_type == 'text':
                # Text processing with Live API
                print(f"Processing text with Live API...")
                
                async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
                    await session.send_client_content(
                        turns={"parts": [{'text': data}]}
                    )
                    
                    # Wait for response
                    full_response = ""
                    timeout_seconds = 10
                    
                    try:
                        async with asyncio.timeout(timeout_seconds):
                            async for response in session.receive():
                                if hasattr(response, 'server_content') and response.server_content:
                                    if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                                        model_turn = response.server_content.model_turn
                                        
                                        if hasattr(model_turn, 'parts') and model_turn.parts:
                                            for part in model_turn.parts:
                                                if hasattr(part, 'text') and part.text:
                                                    full_response += part.text
                                    
                                    if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                                        break
                                        
                    except asyncio.TimeoutError:
                        print(f"Live API timeout after {timeout_seconds} seconds")
                
                response_time = time.time() - start_time
                
                return {
                    'text': full_response or "No response from Live API",
                    'response_time': response_time,
                    'model': self.model,
                    'type': 'live_api_text',
                    'success': bool(full_response)
                }
                
            elif content_type == 'image':
                # Image processing with Live API - direct image streaming
                print(f"Processing image with Live API direct streaming...")
                
                # Convert PIL image to JPEG bytes for Live API
                import io
                image_buffer = io.BytesIO()
                data.save(image_buffer, format='JPEG', quality=90)
                image_bytes = image_buffer.getvalue()
                
                async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
                    # Send image directly via realtimeInput
                    await session.send_realtime_input(
                        video=types.Blob(
                            mime_type="image/jpeg",
                            data=image_bytes
                        )
                    )
                    
                    # Wait a bit for image processing
                    await asyncio.sleep(0.1)
                    
                    # Send text prompt using correct new method
                    await session.send_client_content(
                        turns={"parts": [{'text': prompt or "Analyze what you see in this image"}]}
                    )
                    
                    # Wait for response
                    full_response = ""
                    timeout_seconds = 15
                    
                    try:
                        async with asyncio.timeout(timeout_seconds):
                            async for response in session.receive():
                                print(f"[DEBUG] Image response: {type(response)}")
                                
                                # Try multiple ways to extract text from response
                                if hasattr(response, 'text') and response.text:
                                    full_response += response.text
                                    print(f"[DEBUG] Direct text: {response.text}")
                                elif hasattr(response, 'server_content') and response.server_content:
                                    if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                                        model_turn = response.server_content.model_turn
                                        
                                        if hasattr(model_turn, 'parts') and model_turn.parts:
                                            for part in model_turn.parts:
                                                if hasattr(part, 'text') and part.text:
                                                    full_response += part.text
                                                    print(f"[DEBUG] Part text: {part.text}")
                                    
                                    if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                                        print(f"[DEBUG] Turn complete")
                                        break
                                
                                # Also try to get text from other possible attributes
                                if hasattr(response, 'content') and response.content:
                                    full_response += str(response.content)
                                    print(f"[DEBUG] Content: {response.content}")
                                
                                if full_response:  # Break if we got some response
                                    break
                                        
                    except asyncio.TimeoutError:
                        print(f"Live API image timeout after {timeout_seconds} seconds")
                
                response_time = time.time() - start_time
                
                return {
                    'text': full_response or "No response from Live API image stream",
                    'response_time': response_time,
                    'model': self.model,
                    'type': 'live_api_image_stream',
                    'success': bool(full_response)
                }
                
            else:
                raise ValueError(f"Unsupported content type: {content_type}")
            
        except Exception as e:
            response_time = time.time() - start_time
            return {
                'text': f"Processing Error ({content_type}): {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': f'error_{content_type}',
                'success': False
            }

    async def process_text_with_live_api(self, message):
        """Legacy wrapper for text processing"""
        return await self.process_multimodal_content('text', message)

    async def process_image_with_live_api(self, image_data, prompt):
        """Optimized image processing with Multimodal Live API"""
        # Convert base64 to PIL Image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        print(f"Image size: {image.width}x{image.height}")
        
        # Use PIL Image object for Live API
        return await self.process_multimodal_content('image', image, prompt)

# Global multimodal server instance
live_server = MultimodalLiveAPIServer()

# HTML 페이지
@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Gemini Live API Web Test</title>
    <meta charset="UTF-8">
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            max-width: 1000px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 20px;
        }}
        .chat {{ 
            border: 2px solid #ddd; 
            height: 500px; 
            overflow-y: auto; 
            padding: 15px; 
            margin: 15px 0;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .message {{ 
            margin: 15px 0; 
            padding: 12px; 
            border-radius: 8px; 
            max-width: 80%;
            word-wrap: break-word;
        }}
        .user {{ 
            background-color: #e3f2fd; 
            margin-left: auto;
            text-align: right;
            border: 1px solid #bbdefb;
        }}
        .ai {{ 
            background-color: #f3e5f5; 
            margin-right: auto;
            border: 1px solid #e1bee7;
        }}
        .controls {{ 
            margin: 15px 0; 
            padding: 15px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        input, button {{ 
            padding: 12px; 
            margin: 5px; 
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }}
        button {{
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s;
        }}
        button:hover {{
            background-color: #45a049;
        }}
        #messageInput {{ width: 60%; }}
        #imagePrompt {{ width: 40%; }}
        .status {{
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }}
        .connected {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .disconnected {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        .image-preview {{ max-width: 300px; margin: 10px 0; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Gemini Live API Real-time Test</h1>
        <p>Model: {live_server.llm._model_name} | Web Server + WebSocket</p>
    </div>
    
    <div id="status" class="status disconnected">Connecting...</div>
    
    <div id="chat" class="chat"></div>
    
    <div class="controls">
        <h3>Image Analysis</h3>
        <input type="file" id="imageInput" accept="image/*">
        <input type="text" id="imagePrompt" placeholder="What do you want to ask about the image?" value="What do you see in this image?">
        <button onclick="uploadImage()">Analyze Image</button>
    </div>
    
    <div class="controls">
        <h3>Text Chat</h3>
        <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">Send</button>
        <button onclick="clearChat()">Clear Chat</button>
    </div>

    <script>
        const ws = new WebSocket('ws://localhost:8080/ws');
        const chat = document.getElementById('chat');
        const status = document.getElementById('status');

        ws.onopen = () => {{
            status.textContent = 'Live API Connected!';
            status.className = 'status connected';
            addMessage('Gemini Live API Connected!', 'ai');
        }};

        ws.onclose = () => {{
            status.textContent = 'Connection Closed';
            status.className = 'status disconnected';
        }};

        ws.onerror = () => {{
            status.textContent = 'Connection Error';
            status.className = 'status disconnected';
        }};

        ws.onmessage = (event) => {{
            const data = JSON.parse(event.data);
            if (data.type === 'response') {{
                const time = data.response_time ? ` [Response: ${{data.response_time.toFixed(3)}}s]` : '';
                const model = data.model || 'unknown';
                const icon = data.analysis_type === 'live_api_image' ? '[IMG]' : '[TXT]';
                addMessage(`${{icon}} ${{data.message}}${{time}} [${{model}}]`, 'ai');
            }} else if (data.type === 'error') {{
                addMessage(`[ERROR] ${{data.message}}`, 'ai');
            }}
        }};

        function addMessage(msg, sender) {{
            const div = document.createElement('div');
            div.className = 'message ' + sender;
            div.textContent = msg;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }}

        function sendMessage() {{
            const input = document.getElementById('messageInput');
            const msg = input.value.trim();
            if (msg && ws.readyState === WebSocket.OPEN) {{
                addMessage(msg, 'user');
                ws.send(JSON.stringify({{type: 'text', message: msg}}));
                input.value = '';
            }} else if (ws.readyState !== WebSocket.OPEN) {{
                alert('WebSocket connection lost. Please refresh the page.');
            }}
        }}

        function uploadImage() {{
            const file = document.getElementById('imageInput').files[0];
            const prompt = document.getElementById('imagePrompt').value || '이 이미지에 뭐가 보이나요?';
            
            if (file && ws.readyState === WebSocket.OPEN) {{
                const reader = new FileReader();
                reader.onload = (e) => {{
                    addMessage(`[IMG] Image Upload: ${{prompt}}`, 'user');
                    
                    // 이미지 미리보기
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.className = 'image-preview';
                    chat.appendChild(img);
                    chat.scrollTop = chat.scrollHeight;
                    
                    ws.send(JSON.stringify({{
                        type: 'image',
                        image: e.target.result,
                        prompt: prompt
                    }}));
                }};
                reader.readAsDataURL(file);
            }} else if (!file) {{
                alert('Please select an image!');
            }} else {{
                alert('WebSocket connection lost.');
            }}
        }}

        function clearChat() {{
            chat.innerHTML = '';
            addMessage('Chat cleared.', 'ai');
        }}

        // 엔터키로 전송
        document.getElementById('messageInput').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                sendMessage();
            }}
        }});
    </script>
</body>
</html>"""
    return html_content

# WebSocket 엔드포인트
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"WebSocket client connected")
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get('type') == 'text':
                user_message = message_data.get('message', 'Hello Live API!')
                result = await live_server.process_text_with_live_api(user_message)
                
                print(f"Text processed: {result['response_time']:.3f}s")
                
                await websocket.send_text(json.dumps({
                    'type': 'response',
                    'message': result['text'],
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'analysis_type': result['type'],
                    'success': result['success']
                }))
                
            elif message_data.get('type') == 'image':
                image_data = message_data.get('image', '')
                prompt = message_data.get('prompt', 'What do you see?')
                result = await live_server.process_image_with_live_api(image_data, prompt)
                
                print(f"Image processed: {result['response_time']:.3f}s")
                
                await websocket.send_text(json.dumps({
                    'type': 'response',
                    'message': result['text'],
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'analysis_type': result['type'],
                    'success': result['success']
                }))
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket client disconnected")

def main():
    print("=" * 60)
    print("Gemini Live API Web + WebSocket Server")
    print("=" * 60)
    print(f"Website: http://localhost:8080")
    print(f"WebSocket: ws://localhost:8080/ws") 
    print(f"Live API Model: {live_server.llm._model_name}")
    print(f"Voice: Aoede")
    print("=" * 60)
    print("Open http://localhost:8080 in browser to test!")
    print("=" * 60)
    
    # FastAPI 서버 실행
    uvicorn.run(app, host="localhost", port=8080, log_level="info")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nWeb Server stopped")