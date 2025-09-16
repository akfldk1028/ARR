import logging
from uuid import uuid4
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from semantic_kernel.agents.chat_completion.chat_completion_agent import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions.kernel_function_decorator import kernel_function
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest
import os
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Configure logging to both console and file
def setup_logging():
    """Configure clean logging for agent communication"""
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Generate unique log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Clean conversation log (only important stuff)
    conversation_log_filename = f'logs/conversation_{timestamp}.log'
    
    # Configure root logger with less verbose output
    logging.basicConfig(
        level=logging.INFO,  # Changed from DEBUG to INFO
        format='%(asctime)s - %(levelname)s - %(message)s',  # Simplified format
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Create separate conversation logger
    conversation_logger = logging.getLogger('conversation')
    conversation_handler = logging.FileHandler(conversation_log_filename, encoding='utf-8')
    conversation_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    conversation_logger.addHandler(conversation_handler)
    conversation_logger.setLevel(logging.INFO)
    
    # Suppress noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('semantic_kernel').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('a2a').setLevel(logging.WARNING)
    
    # Also create a separate JSON log for structured communication data
    json_log_filename = f'logs/agent_communication_{timestamp}.json'
    
    return logging.getLogger(__name__), json_log_filename, conversation_logger, conversation_log_filename

logger, json_log_file, conversation_logger, conversation_log_file = setup_logging()

app = FastAPI()

base_url = 'http://localhost:9999'

# Maintain chat history per context
chat_history_store: dict[str, ChatHistory] = {}

# Store for structured communication logs
communication_logs = []

def save_communication_log(log_entry):
    """Save communication log entry to JSON file"""
    communication_logs.append(log_entry)
    
    # Append to JSON file
    with open(json_log_file, 'w', encoding='utf-8') as f:
        json.dump(communication_logs, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info(f"Communication log saved: {log_entry.get('type', 'Unknown')}")

class FlightBookingTool:
    @kernel_function(
        description="Book a flight using the flight booking agent",
        name="book_flight"
    )
    async def book_flight(self, user_input: str) -> str:
        communication_id = str(uuid4())
        
        # Log the start of agent communication (clean format)
        conversation_logger.info(f"TRAVEL AGENT -> FLIGHT AGENT: {user_input}")
        
        communication_log = {
            "id": communication_id,
            "timestamp": datetime.now().isoformat(),
            "type": "agent_to_agent_request",
            "from_agent": "TravelPlanningAgent",
            "to_agent": "FlightBookingAgent",
            "request": user_input,
            "base_url": base_url
        }
        
        async with httpx.AsyncClient() as httpx_client:
            try:
                # Log agent card resolution
                logger.debug(f"[A2A] Resolving agent card from {base_url}")
                resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
                agent_card = await resolver.get_agent_card()
                
                # Log agent card details
                logger.info(f"[A2A] Agent card resolved: {agent_card.name}")
                logger.debug(f"[A2A] Agent capabilities: {json.dumps(agent_card.model_dump(), indent=2)}")
                
                communication_log["agent_card"] = {
                    "name": agent_card.name,
                    "description": agent_card.description,
                    "version": agent_card.version,
                    "skills": [skill.model_dump() for skill in agent_card.skills] if agent_card.skills else []
                }

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
                
                # Log the full request
                logger.debug(f"[A2A-REQUEST] {json.dumps(request.model_dump(), indent=2)}")
                
                # Send request and get response
                response = await client.send_message(request)
                result = response.model_dump(mode='json', exclude_none=True)
                
                # Log the full response
                logger.info(f"[FLIGHT->TRAVEL] Response received")
                logger.debug(f"[A2A-RESPONSE] {json.dumps(result, indent=2)}")
                
                communication_log["response"] = result
                communication_log["status"] = "success"
                
                # Extract text from response
                if "result" in result and "parts" in result["result"]:
                    response_text = result["result"]["parts"][0]["text"]
                    conversation_logger.info(f"FLIGHT AGENT -> TRAVEL AGENT: {response_text}")
                    communication_log["response_text"] = response_text
                    save_communication_log(communication_log)
                    return response_text
                elif "error" in result:
                    error_msg = f"Error from Flight Booking Agent: {result['error']}"
                    logger.error(f"[AGENT-COMM-ERROR] ID: {communication_id} - {error_msg}")
                    communication_log["status"] = "error"
                    communication_log["error"] = result["error"]
                    save_communication_log(communication_log)
                    return error_msg
                else:
                    logger.error(f"[AGENT-COMM-ERROR] Unexpected response format: {result}")
                    communication_log["status"] = "error"
                    communication_log["error"] = "Unexpected response format"
                    save_communication_log(communication_log)
                    return "Unexpected response format from Flight Booking Agent"
                    
            except Exception as e:
                logger.error(f"[AGENT-COMM-ERROR] ID: {communication_id} - Exception: {str(e)}")
                communication_log["status"] = "exception"
                communication_log["error"] = str(e)
                save_communication_log(communication_log)
                return f"Error communicating with Flight Booking Agent: {str(e)}"

# Get OpenAI API key from environment variable or use placeholder
api_key = os.getenv("OPENAI_API_KEY", "<your-openai-api-key>")

travel_planning_agent = ChatCompletionAgent(
    service=OpenAIChatCompletion(
        api_key=api_key,
        ai_model_id="gpt-3.5-turbo",
    ),
    name="TravelPlanner",
    instructions="""You are a friendly and professional travel planning assistant. Your role is to:
1. Understand customer travel needs
2. Use the flight booking tool to communicate with the Flight Booking Agent
3. Relay information between the customer and the Flight Booking Agent
4. Help customers make informed decisions about their travel

When a customer wants to book a flight, always use the book_flight tool to communicate with our specialized Flight Booking Agent. 
Pass along the customer's requests clearly and relay the agent's responses back to the customer.
Be conversational and helpful, adding your own travel tips and suggestions when appropriate.""",
    plugins=[FlightBookingTool()]
)

@app.post("/chat")
async def chat(user_input: str = Form(...), context_id: str = Form("default")):
    chat_id = str(uuid4())
    
    # Log user interaction (clean format)
    conversation_logger.info(f"USER: {user_input}")
    
    # Log user interaction
    user_log = {
        "id": chat_id,
        "timestamp": datetime.now().isoformat(),
        "type": "user_interaction",
        "context_id": context_id,
        "user_input": user_input
    }

    # Get or create ChatHistory for the context
    chat_history = chat_history_store.get(context_id)
    if chat_history is None:
        chat_history = ChatHistory(
            messages=[],
            system_message="You are a travel planning assistant. Your task is to help the user with their travel plans, including booking flights."
        )
        chat_history_store[context_id] = chat_history
        logger.info(f"[CONTEXT] Created new context: {context_id}")

    # Add user input to chat history
    chat_history.messages.append(ChatMessageContent(role="user", content=user_input))

    # Create a new thread from the chat history
    thread = ChatHistoryAgentThread(chat_history=chat_history, thread_id=str(uuid4()))

    # Get response from the agent
    response = await travel_planning_agent.get_response(message=user_input, thread=thread)

    # Add assistant response to chat history
    chat_history.messages.append(ChatMessageContent(role="assistant", content=response.content.content))

    # Log travel agent response (clean format)
    conversation_logger.info(f"TRAVEL AGENT -> USER: {response.content.content}")
    conversation_logger.info("-" * 60)  # Separator line
    
    # Save user interaction log
    user_log["response"] = response.content.content
    save_communication_log(user_log)

    return {"response": response.content.content}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: index.html not found!</h1>", status_code=404)

@app.get("/logs")
async def get_logs():
    """Endpoint to retrieve communication logs"""
    return {
        "logs": communication_logs,
        "log_file": json_log_file,
        "total_communications": len(communication_logs)
    }

if __name__ == '__main__':
    import uvicorn
    print("="*60)
    print("TRAVEL PLANNING AGENT WITH CLEAN LOGGING")
    print("="*60)
    print(f"Conversation log: {conversation_log_file}")
    print(f"JSON log: {json_log_file}")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=8000)