import logging
from uuid import uuid4
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

base_url = 'http://localhost:9999'

# Maintain chat history per context
chat_history_store: dict[str, list] = {}

async def book_flight(user_input: str) -> str:
    """Mock flight booking function that calls the actual flight booking agent"""
    try:
        async with httpx.AsyncClient() as httpx_client:
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
            agent_card = await resolver.get_agent_card()

            client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message={
                        "messageId": uuid4().hex,
                        "role": "user",
                        "parts": [{"text": user_input}],
                        "contextId": '123',
                    }
                )
            )
            response = await client.send_message(request)
            result = response.model_dump(mode='json', exclude_none=True)
            logger.info(f"Flight booking tool response: {result}")

            return result["result"]["parts"][0]["text"]
    except Exception as e:
        logger.error(f"Error calling flight booking agent: {e}")
        return f"I encountered an error while trying to book the flight: {str(e)}"

@app.post("/chat")
async def chat(user_input: str = Form(...), context_id: str = Form("default")):
    logger.info(f"Received chat request: {user_input} with context ID: {context_id}")

    # Get or create chat history for the context
    if context_id not in chat_history_store:
        chat_history_store[context_id] = []
        logger.info(f"Created new chat history for context ID: {context_id}")

    # Add user input to chat history
    chat_history_store[context_id].append({"role": "user", "content": user_input})

    # Simple keyword-based response system
    response_text = ""
    
    lower_input = user_input.lower()
    
    # Check for greetings
    if any(word in lower_input for word in ['hello', 'hi', 'hey', 'greetings']):
        response_text = "Hello! I'm your travel planning assistant. I can help you book flights and plan your trips. What destination are you interested in?"
    
    # Check for trip planning keywords
    elif any(word in lower_input for word in ['trip', 'travel', 'vacation', 'holiday', 'journey']):
        response_text = "I'd be happy to help you plan your trip! Could you tell me:\n1. Where would you like to go?\n2. When are you planning to travel?\n3. How many people will be traveling?"
    
    # Check for flight booking keywords
    elif any(word in lower_input for word in ['flight', 'fly', 'book', 'ticket', 'airline']):
        # If specific cities are mentioned, call the flight booking agent
        if any(city in lower_input for city in ['new york', 'london', 'paris', 'tokyo', 'seoul', 'san francisco', 'los angeles']):
            logger.info("Detected flight booking request with city names, calling flight booking agent...")
            flight_response = await book_flight(user_input)
            response_text = f"Let me help you with that flight booking.\n\n{flight_response}"
        else:
            response_text = "I can help you book a flight! Please provide:\n- Departure city\n- Destination city\n- Travel dates\n- Number of passengers"
    
    # Check for help/assistance
    elif any(word in lower_input for word in ['help', 'assist', 'support', 'what can you']):
        response_text = "I'm a travel planning assistant. I can help you with:\n• Flight bookings\n• Trip planning advice\n• Travel recommendations\n\nJust tell me what you need!"
    
    # Check for thank you
    elif any(word in lower_input for word in ['thank', 'thanks', 'appreciate']):
        response_text = "You're welcome! Is there anything else I can help you with for your travel plans?"
    
    # Default response
    else:
        response_text = "I understand you're interested in travel planning. Could you be more specific about what you need? I can help with flight bookings, trip planning, and travel recommendations."

    # Add assistant response to chat history
    chat_history_store[context_id].append({"role": "assistant", "content": response_text})

    logger.info(f"Response: {response_text}")

    return {"response": response_text}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        # Create a simple HTML interface if index.html doesn't exist
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Travel Planning Assistant</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                #chat-box { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin-bottom: 10px; }
                #input-form { display: flex; gap: 10px; }
                #user-input { flex: 1; padding: 10px; }
                button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
                button:hover { background: #0056b3; }
                .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
                .user { background: #e3f2fd; text-align: right; }
                .assistant { background: #f5f5f5; }
            </style>
        </head>
        <body>
            <h1>Travel Planning Assistant</h1>
            <div id="chat-box"></div>
            <form id="input-form">
                <input type="text" id="user-input" placeholder="Type your message..." required>
                <button type="submit">Send</button>
            </form>
            
            <script>
                const chatBox = document.getElementById('chat-box');
                const form = document.getElementById('input-form');
                const input = document.getElementById('user-input');
                const contextId = 'web-' + Date.now();
                
                form.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const message = input.value.trim();
                    if (!message) return;
                    
                    // Add user message to chat
                    chatBox.innerHTML += '<div class="message user">You: ' + message + '</div>';
                    input.value = '';
                    
                    // Send to server
                    try {
                        const formData = new FormData();
                        formData.append('user_input', message);
                        formData.append('context_id', contextId);
                        
                        const response = await fetch('/chat', {
                            method: 'POST',
                            body: formData
                        });
                        
                        const data = await response.json();
                        chatBox.innerHTML += '<div class="message assistant">Assistant: ' + data.response + '</div>';
                        chatBox.scrollTop = chatBox.scrollHeight;
                    } catch (error) {
                        chatBox.innerHTML += '<div class="message assistant">Error: ' + error.message + '</div>';
                    }
                });
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)