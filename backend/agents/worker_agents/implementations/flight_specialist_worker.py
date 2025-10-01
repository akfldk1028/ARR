"""
Flight Specialist Worker Agent - 항공편 예약 및 여행 정보 전문 에이전트
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

class FlightSpecialistWorkerAgent(BaseWorkerAgent):
    """Specialized worker agent for flight booking and travel information"""

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any]):
        super().__init__(agent_slug, agent_config)

        # Initialize OpenAI LLM with more focused temperature for factual responses
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.llm = ChatOpenAI(
            model=agent_config.get('model_name', 'gpt-3.5-turbo'),
            api_key=api_key,
            temperature=agent_config.get('config', {}).get('temperature', 0.3),  # Lower temp for factual info
            max_tokens=agent_config.get('config', {}).get('max_tokens', 1024)
        )

    @property
    def agent_name(self) -> str:
        return self.config.get('name', 'Flight Specialist Agent')

    @property
    def agent_description(self) -> str:
        return self.config.get('description', 'Specialized agent for flight booking and travel information')

    @property
    def capabilities(self) -> List[str]:
        return self.config.get('capabilities', ['text', 'flight_booking', 'travel_info', 'airline_data', 'route_planning'])

    @property
    def system_prompt(self) -> str:
        return self.config.get('system_prompt', '''You are a specialized flight booking agent with extensive knowledge of:

1. Flight schedules and routes between major cities
2. Airline information and recommendations
3. Travel times and connecting flights
4. Seasonal pricing and availability patterns
5. Airport information and codes
6. Travel documentation requirements

Provide detailed, helpful flight information including:
- Specific flight numbers and times (use realistic examples)
- Multiple airline options
- Price ranges and booking recommendations
- Travel tips and considerations

IMPORTANT: Never use emojis in your responses. Always respond in plain text without any emoji characters.

Always be specific and informative in your responses about flight-related queries.

Sample flight information for common routes:
- Seoul (ICN) to Tokyo (HND/NRT): 2-3 hours, airlines like Korean Air, JAL, ANA
- Seoul to Singapore: 6-7 hours, Korean Air, Singapore Airlines
- Seoul to Los Angeles: 11-12 hours, Korean Air, United, Delta

Provide realistic flight times, prices, and airline recommendations.''')

    async def _generate_response(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """Generate specialized flight booking response"""
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

            # Generate specialized response with timeout - temporarily use fallback first
            try:
                # Temporarily use fallback response to debug the issue
                logger.info("Using fallback response for debugging")
                flight_response = "안녕하세요! 항공편 예약을 도와드리겠습니다. 어디서 어디로 가는 항공편을 찾고 계신가요? 출발지와 목적지, 그리고 선호하는 날짜를 알려주시면 최적의 항공편을 찾아드리겠습니다."

                # Disabled temporarily: response = await asyncio.wait_for(self.llm.ainvoke(messages), timeout=30.0)
                # Disabled temporarily: flight_response = response.content
            except asyncio.TimeoutError:
                logger.warning("LLM response timeout, using fallback response")
                flight_response = "안녕하세요! 항공편 예약을 도와드리겠습니다. 어디서 어디로 가는 항공편을 찾고 계신가요? 출발지와 목적지, 그리고 선호하는 날짜를 알려주시면 최적의 항공편을 찾아드리겠습니다."

            # Check if we should coordinate with other agents
            if any(word in user_input.lower() for word in ['hotel', 'accommodation', 'stay', 'complete trip']):
                # Offer to coordinate with hotel specialist
                flight_response += "\n\n숙박도 필요하시다면 호텔 예약 전문가와 연결해드릴 수 있습니다. 완전한 여행 계획을 원하시나요?"

            # Remove emojis from response
            return remove_emojis(flight_response)

        except Exception as e:
            logger.error(f"Error generating response in FlightSpecialistWorkerAgent: {e}")
            return f"I apologize, but I encountered an error while looking up flight information: {str(e)}. Please try again or contact our general support."