import asyncio
import logging
from uuid import uuid4
from dotenv import load_dotenv

from semantic_kernel.agents.chat_completion.chat_completion_agent import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.chat_history import ChatHistory
import os

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SemanticKernelFlightBookingAgent:

    def __init__(self):
        logger.info("Initializing SemanticKernelFlightBookingAgent.")
        
        # Get OpenAI API key from environment variable or use placeholder
        api_key = os.getenv("OPENAI_API_KEY", "<your-openai-api-key>")
        
        self.chat_agent = ChatCompletionAgent(
            service=OpenAIChatCompletion(
                api_key=api_key,  # Use your OpenAI API key
                ai_model_id="gpt-3.5-turbo",  # or "gpt-4" for better performance
            ),
            name="Assistant",
        )

        # Mapping of context_id -> ChatHistory
        self.history_store: dict[str, ChatHistory] = {}

        logger.info("SemanticKernelFlightBookingAgent initialized successfully.")

    async def book_flight(self, user_input: str, context_id: str) -> str:
        """
        Book a flight based on user input.
        :param user_input: The user's request for flight booking.
        :param context_id: The context ID for the request.
        :return: The response from the flight booking agent.
        """
        logger.info(f"Received flight booking request: {user_input} with context ID: {context_id}")

        if not user_input:
            logger.error("User input is empty.")
            raise ValueError("User input cannot be empty.")

        # Get or create ChatHistory for the context
        chat_history = self.history_store.get(context_id)
        if chat_history is None:
            chat_history = ChatHistory(
                messages=[],
                system_message="""You are a professional flight booking assistant AI. Your role is to:
1. Understand flight booking requests
2. Ask for any missing information (dates, times, passenger details)
3. Search for available flights (simulate realistic flight options)
4. Provide flight options with details (flight numbers, times, prices)
5. Confirm bookings when the user agrees

When you receive a flight request, respond professionally and helpfully. Simulate realistic flight information including:
- Flight numbers (e.g., KE901, AF267)
- Departure and arrival times
- Airlines
- Prices in USD
- Duration

Always be helpful and conversational, as if you're a real booking agent."""
            )
            self.history_store[context_id] = chat_history
            logger.info(f"Created new ChatHistory for context ID: {context_id}")

        # Add user input to chat history
        chat_history.messages.append(ChatMessageContent(role="user", content=user_input))

        # Create a new thread from the chat history
        thread = ChatHistoryAgentThread(chat_history=chat_history, thread_id=str(uuid4()))

        # Get response from the agent
        response = await self.chat_agent.get_response(message=user_input, thread=thread)

        # Add assistant response to chat history
        chat_history.messages.append(ChatMessageContent(role="assistant", content=response.content.content))

        logger.info(f"Flight booking agent response: {response.content.content}")

        # Return only the agent's response without additional text
        return response.content.content
