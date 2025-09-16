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

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

base_url = 'http://localhost:9999'

# Maintain chat history per context
chat_history_store: dict[str, ChatHistory] = {}

class FlightBookingTool:
    @kernel_function(
        description="Book a flight using the flight booking agent",
        name="book_flight"
    )
    async def book_flight(self, user_input: str) -> str:
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

# Get OpenAI API key from environment variable or use placeholder
api_key = os.getenv("OPENAI_API_KEY", "<your-openai-api-key>")

travel_planning_agent = ChatCompletionAgent(
    service=OpenAIChatCompletion(
        api_key=api_key,  # Use your OpenAI API key
        ai_model_id="gpt-3.5-turbo",  # or "gpt-4" for better performance
    ),
    name="TravelPlanner",
    instructions="You are a helpful travel planning assistant. Use the provided tools to assist users with their travel plans.",
    plugins=[FlightBookingTool()]
)

@app.post("/chat")
async def chat(user_input: str = Form(...), context_id: str = Form("default")):
    logger.info(f"Received chat request: {user_input} with context ID: {context_id}")

    # Get or create ChatHistory for the context
    chat_history = chat_history_store.get(context_id)
    if chat_history is None:
        chat_history = ChatHistory(
            messages=[],
            system_message="You are a travel planning assistant. Your task is to help the user with their travel plans, including booking flights."
        )
        chat_history_store[context_id] = chat_history
        logger.info(f"Created new ChatHistory for context ID: {context_id}")

    # Add user input to chat history
    chat_history.messages.append(ChatMessageContent(role="user", content=user_input))

    # Create a new thread from the chat history
    thread = ChatHistoryAgentThread(chat_history=chat_history, thread_id=str(uuid4()))

    # Get response from the agent
    response = await travel_planning_agent.get_response(message=user_input, thread=thread)

    # Add assistant response to chat history
    chat_history.messages.append(ChatMessageContent(role="assistant", content=response.content.content))

    logger.info(f"Flight booking agent response: {response.content.content}")

    final_response = f"{response.content.content}"

    return {"response": final_response} # Return directly the text in a 'response' key


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: index.html not found!</h1>", status_code=404)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)