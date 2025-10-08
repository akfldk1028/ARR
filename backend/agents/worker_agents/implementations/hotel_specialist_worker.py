"""
Hotel Specialist Worker Agent - 호텔 예약 및 숙박 정보 전문 에이전트
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
    # Remove all Unicode emoji characters
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

class HotelSpecialistWorkerAgent(BaseWorkerAgent):
    """Specialized worker agent for hotel booking and accommodation information"""

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any]):
        super().__init__(agent_slug, agent_config)

        # Initialize OpenAI LLM with more focused temperature for factual responses
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Get model config from django.model_config
        django_config = agent_config.get('django', {})
        model_config = django_config.get('model_config', {})

        # Use model config or defaults
        model_name = model_config.get('model_name', 'gpt-3.5-turbo') if model_config else 'gpt-3.5-turbo'
        temperature = model_config.get('temperature', 0.3) if model_config else 0.3
        max_tokens = model_config.get('max_tokens', 1024) if model_config else 1024

        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens
        )

        logger.info(f"HotelSpecialist initialized with model: {model_name}")

    @property
    def agent_name(self) -> str:
        return self.config.get('name', 'Hotel Specialist Agent')

    @property
    def agent_description(self) -> str:
        return self.config.get('description', 'Specialized agent for hotel booking and accommodation recommendations')

    @property
    def capabilities(self) -> List[str]:
        return self.config.get('capabilities', ['text', 'hotel_booking', 'accommodation_info', 'pricing', 'recommendations'])

    @property
    def system_prompt(self) -> str:
        return self.config.get('system_prompt', '''You are a specialized hotel booking agent with extensive knowledge of:

1. Hotel availability and booking systems
2. Accommodation types and amenities
3. Location-based recommendations
4. Pricing and special offers
5. Room types and configurations
6. Customer preferences and requirements

Provide detailed, helpful hotel information including:
- Specific hotel names and locations (use realistic examples)
- Multiple accommodation options
- Price ranges and booking recommendations
- Amenities and facility information

IMPORTANT:
1. Never use emojis in your responses. Always respond in plain text without any emoji characters.
2. If the user does not specify location or dates, ASK for them. DO NOT assume or guess locations.
3. Only provide specific hotel information when location is clearly stated.

Always be specific and informative in your responses about hotel-related queries.

When user provides location and dates, provide realistic hotel options, prices, and recommendations based on typical accommodations in that area.''')

    async def _generate_response(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """Generate specialized hotel booking response"""
        try:
            messages = [SystemMessage(content=self.system_prompt)]

            # Load recent conversation history
            try:
                history_query = """
                MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
                WHERE m.agent_slug = $agent_slug OR m.type = 'user'
                RETURN m.content as content, m.type as role, m.timestamp as timestamp
                ORDER BY m.timestamp DESC
                LIMIT 6
                """

                history = self.neo4j_service.execute_query(
                    history_query,
                    {
                        'session_id': session_id,
                        'agent_slug': self.agent_slug
                    }
                )

                # Add history to messages
                for msg in reversed(history):
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))

            except Exception as e:
                logger.warning(f"Could not load conversation history: {e}")

            # Add current user message
            messages.append(HumanMessage(content=user_input))

            # Generate specialized response with timeout
            try:
                logger.info(f"Hotel specialist processing: {user_input[:100]}")
                response = await asyncio.wait_for(self.llm.ainvoke(messages), timeout=30.0)
                hotel_response = response.content
                logger.info(f"[DEBUG] OpenAI response type: {type(hotel_response)}")
                logger.info(f"[DEBUG] OpenAI response length: {len(hotel_response) if hotel_response else 0}")
                logger.info(f"[DEBUG] OpenAI response content (first 200 chars): {hotel_response[:200] if hotel_response else 'EMPTY'}")
            except asyncio.TimeoutError:
                logger.warning("LLM response timeout, using fallback response")
                hotel_response = "안녕하세요! 호텔 예약을 도와드리겠습니다. 어느 지역의 호텔을 찾고 계신가요? 목적지와 체크인/체크아웃 날짜를 알려주시면 최적의 숙소를 찾아드리겠습니다."

            # Check if we should coordinate with other agents
            if any(word in user_input.lower() for word in ['flight', 'airplane', 'travel', 'trip planning']):
                # Offer to coordinate with flight specialist
                hotel_response += "\n\n항공편도 필요하시다면 항공 예약 전문가와 연결해드릴 수 있습니다. 완전한 여행 계획을 원하시나요?"

            # Remove emojis from response
            final_response = remove_emojis(hotel_response)
            logger.info(f"[DEBUG] After emoji removal: {len(final_response) if final_response else 0} chars")
            logger.info(f"[DEBUG] Final response (first 200 chars): {final_response[:200] if final_response else 'EMPTY'}")
            return final_response

        except Exception as e:
            logger.error(f"Error generating response in HotelSpecialistWorkerAgent: {e}")
            return f"I apologize, but I encountered an error while looking up hotel information: {str(e)}. Please try again or contact our general support."
