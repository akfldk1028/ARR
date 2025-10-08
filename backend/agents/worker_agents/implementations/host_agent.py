"""
Host Agent - Primary coordinator with semantic routing and specialist delegation
"""

import os
import asyncio
import logging
import re
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ..base import BaseWorkerAgent

logger = logging.getLogger(__name__)

def remove_emojis(text: str) -> str:
    """Remove all emojis from text to prevent encoding issues"""
    emoji_pattern = re.compile(
        r'[\U0001F600-\U0001F64F]|'  # emoticons
        r'[\U0001F300-\U0001F5FF]|'  # symbols & pictographs
        r'[\U0001F680-\U0001F6FF]|'  # transport & map symbols
        r'[\U0001F700-\U0001F77F]|'  # alchemical symbols
        r'[\U0001F780-\U0001F7FF]|'  # Geometric Shapes Extended
        r'[\U0001F800-\U0001F8FF]|'  # Supplemental Arrows-C
        r'[\U0001F900-\U0001F9FF]|'  # Supplemental Symbols and Pictographs
        r'[\U0001FA00-\U0001FA6F]|'  # Chess Symbols
        r'[\U0001FA70-\U0001FAFF]|'  # Symbols and Pictographs Extended-A
        r'[\U00002600-\U000026FF]|'  # Miscellaneous Symbols
        r'[\U00002700-\U000027BF]',  # Dingbats
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)

class HostAgent(BaseWorkerAgent):
    """Primary coordinator agent for general conversation and semantic routing"""

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any]):
        super().__init__(agent_slug, agent_config)

        # Initialize memory for conversation history
        self.memory = {}

        # Initialize OpenAI LLM with conversational temperature
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.llm = ChatOpenAI(
            model=agent_config.get('model_name', 'gpt-3.5-turbo'),
            api_key=api_key,
            temperature=agent_config.get('config', {}).get('temperature', 0.7),  # Higher temp for natural conversation
            max_tokens=agent_config.get('config', {}).get('max_tokens', 2048)
        )

    @property
    def agent_name(self) -> str:
        return self.config.get('name', 'Host Agent')

    @property
    def agent_description(self) -> str:
        return self.config.get('description', 'Primary coordination agent with semantic routing')

    @property
    def capabilities(self) -> List[str]:
        return self.config.get('capabilities', ['text', 'conversation', 'routing', 'coordination'])

    @property
    def system_prompt(self) -> str:
        return self.config.get('system_prompt', '''You are a helpful AI assistant specialized in natural conversation and coordinating with specialist agents.

Your responsibilities:
1. Engage in friendly, helpful conversations with users
2. Understand user intent and needs
3. Provide general assistance and information
4. Coordinate with specialist agents when needed (flight bookings, hotel reservations, etc.)

Communication style:
- Be friendly and conversational
- Provide clear, concise responses
- Ask clarifying questions when needed
- IMPORTANT: Never use emojis in your responses. Always respond in plain text without any emoji characters.

When users ask about:
- General questions: Answer directly with helpful information
- Flight bookings/travel: Provide assistance (specialist agents may be engaged for complex requests)
- Hotel reservations: Provide guidance (specialist agents may be engaged for bookings)
- Other topics: Use your knowledge to help

Always maintain a helpful, professional tone while being approachable and easy to talk to.''')

    async def _generate_response(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """Generate general conversation response"""
        try:
            messages = [SystemMessage(content=self.system_prompt)]

            # Load recent conversation history
            history_messages = await self._load_history(session_id, context_id, limit=5)
            messages.extend(history_messages)

            # Add current user message
            messages.append(HumanMessage(content=user_input))

            # Generate response using LLM
            logger.info(f"Host agent processing request: {user_input[:100]}")
            response = await self.llm.ainvoke(messages)

            # Remove emojis from response
            response_text = remove_emojis(response.content)

            # Save to conversation history
            await self._save_message(context_id, session_id, 'user', user_input)
            await self._save_message(context_id, session_id, 'assistant', response_text)

            return response_text

        except Exception as e:
            logger.error(f"Error generating response in HostAgent: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request. Please try again."

    async def _load_history(self, session_id: str, context_id: str, limit: int = 5) -> List:
        """Load recent conversation history from memory"""
        try:
            history_key = f"history:{session_id}:{context_id}"
            history = self.memory.get(history_key, [])

            # Return last N messages
            recent = history[-limit*2:] if len(history) > limit*2 else history

            # Convert to LangChain message format
            messages = []
            for msg in recent:
                if msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    messages.append(AIMessage(content=msg['content']))

            return messages

        except Exception as e:
            logger.error(f"Error loading history: {e}")
            return []

    async def _save_message(self, context_id: str, session_id: str, role: str, content: str):
        """Save message to conversation history"""
        try:
            history_key = f"history:{session_id}:{context_id}"
            if history_key not in self.memory:
                self.memory[history_key] = []

            self.memory[history_key].append({
                'role': role,
                'content': content,
                'timestamp': asyncio.get_event_loop().time()
            })

            # Keep only last 20 messages to prevent memory bloat
            if len(self.memory[history_key]) > 20:
                self.memory[history_key] = self.memory[history_key][-20:]

        except Exception as e:
            logger.error(f"Error saving message: {e}")
