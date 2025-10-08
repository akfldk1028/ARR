"""
A2A Handler - Agent-to-Agent 통신 및 처리
워커 에이전트 간 통신, 의미적 라우팅, TTS 변환 처리
"""

import asyncio
import base64
import json
import logging
import re
from typing import Dict, Any, Optional
from uuid import uuid4
from datetime import datetime

logger = logging.getLogger('gemini.consumers')

class A2AHandler:
    """A2A (Agent-to-Agent) 관련 처리를 담당하는 핸들러"""

    def __init__(self, consumer):
        self.consumer = consumer
        self.websocket_send = consumer.send
        self.session_id = consumer.browser_session_id  # Django browser session ID
        self.user_obj = consumer.user_obj
        self.worker_manager = consumer.worker_manager
        self.gemini_service = consumer.gemini_service
        self.current_agent_slug = consumer.current_agent_slug

        # Neo4j Trackers (from consumer)
        self.neo4j_service = consumer.neo4j_service
        self.conversation_tracker = consumer.conversation_tracker
        self.task_manager = consumer.task_manager
        self.provenance_tracker = consumer.provenance_tracker
        self.conversation_id = consumer.conversation_id  # Neo4j conversation tracking ID

    async def handle_text(self, data):
        """Handle text messages with A2A integration + Neo4j tracking"""
        content = data.get('message', '').strip()
        if not content or len(content) > 10000:
            await self.consumer._send_error("Invalid message content")
            return

        try:
            # === LEVEL 1: Neo4j Turn & Message 생성 ===
            # 1. Turn 카운터 증가 및 Turn 생성
            self.consumer.turn_counter += 1
            turn_id = self.conversation_tracker.create_turn(
                conversation_id=self.conversation_id,
                sequence=self.consumer.turn_counter,
                user_query=content
            )
            logger.info(f"Neo4j Turn created: {turn_id} (sequence #{self.consumer.turn_counter})")

            # 2. User Message 노드 생성
            user_msg_id = self.conversation_tracker.add_message(
                conversation_id=self.conversation_id,
                turn_id=turn_id,
                role='user',
                content=content,
                sequence=1,  # User message is always first
                metadata={'django_session': self.session_id}
            )
            logger.info(f"Neo4j User Message created: {user_msg_id}")

            # Django 모델에도 저장 (기존 로직 유지)
            user_message = await self.consumer._save_message(content, 'text', 'user')

            # === SEMANTIC ROUTING: Determine which agent should handle this ===
            routing_result = await self._analyze_intent_with_similarity(content, self.consumer.current_agent_slug)

            # If should delegate, switch to specialist agent
            original_agent = self.consumer.current_agent_slug
            if routing_result.get('should_delegate', False):
                target_agent = routing_result.get('target_agent')
                # Normalize slug: replace underscore with hyphen for consistency with frontend
                target_agent = target_agent.replace('_', '-')
                logger.info(f"Semantic routing: Delegating from {original_agent} to {target_agent} (confidence: {routing_result.get('confidence', 0):.3f})")
                self.consumer.current_agent_slug = target_agent
            else:
                logger.info(f"Semantic routing: Staying with {original_agent} (confidence: {routing_result.get('confidence', 0):.3f})")

            # === LEVEL 2: AgentExecution 노드 생성 (시작) ===
            import time
            from uuid import uuid4
            execution_id = str(uuid4())
            execution_start = time.time()

            # AgentExecution 노드 생성 (Turn -[:EXECUTED_BY]-> AgentExecution -[:USED_AGENT]-> Agent)
            exec_query = """
            MATCH (t:Turn {id: $turn_id})
            MERGE (a:Agent {slug: $agent_slug})
            CREATE (ae:AgentExecution {
                id: $execution_id,
                agent_slug: $agent_slug,
                turn_id: $turn_id,
                started_at: datetime($started_at),
                status: 'processing',
                metadata: $metadata
            })
            CREATE (t)-[:EXECUTED_BY]->(ae)
            CREATE (ae)-[:USED_AGENT]->(a)
            RETURN ae.id as execution_id
            """
            self.neo4j_service.execute_write_query(exec_query, {
                'execution_id': execution_id,
                'turn_id': turn_id,
                'agent_slug': self.consumer.current_agent_slug,
                'started_at': datetime.utcnow().isoformat(),
                'metadata': json.dumps({
                    'user_query': content,
                    'original_agent': original_agent,
                    'routed_to': self.consumer.current_agent_slug,
                    'routing_confidence': routing_result.get('confidence', 0),
                    'was_delegated': routing_result.get('should_delegate', False)
                })
            })
            logger.info(f"Neo4j AgentExecution created: {execution_id} (agent: {self.consumer.current_agent_slug})")

            # Process with A2A (now using the routed agent)
            result = await self._process_with_a2a(content)

            # === LEVEL 2: AgentExecution 상태 업데이트 (완료) ===
            execution_time_ms = int((time.time() - execution_start) * 1000)
            update_query = """
            MATCH (ae:AgentExecution {id: $execution_id})
            SET ae.completed_at = datetime($completed_at),
                ae.status = $status,
                ae.execution_time_ms = $execution_time_ms,
                ae.error_message = $error_message
            RETURN ae.id
            """
            self.neo4j_service.execute_write_query(update_query, {
                'execution_id': execution_id,
                'completed_at': datetime.utcnow().isoformat(),
                'status': 'completed' if result['success'] else 'failed',
                'execution_time_ms': execution_time_ms,
                'error_message': None if result['success'] else result.get('error', 'Unknown error')
            })
            logger.info(f"Neo4j AgentExecution updated: {execution_id} (status: {'completed' if result['success'] else 'failed'}, time: {execution_time_ms}ms)")

            if result['success']:
                # 3. Assistant Message 노드 생성
                assistant_msg_id = self.conversation_tracker.add_message(
                    conversation_id=self.conversation_id,
                    turn_id=turn_id,
                    role='assistant',
                    content=result['response'],
                    sequence=2,  # Assistant message is second
                    metadata={
                        'agent_slug': self.consumer.current_agent_slug,
                        'agent_name': result.get('agent_name', 'AI'),
                        'processing_type': 'a2a_agent'
                    }
                )
                logger.info(f"Neo4j Assistant Message created: {assistant_msg_id}")

                # === 프론트엔드로 응답 전송 (누락된 부분!) ===
                await self.websocket_send(text_data=json.dumps({
                    'type': 'chat_response',
                    'message': result['response'],
                    'agent_name': result.get('agent_name', 'AI'),  # Frontend expects 'agent_name' not 'agent'
                    'agent_slug': self.consumer.current_agent_slug,
                    'success': True
                }))
                logger.info(f"A2A response sent to frontend: {result['response'][:50]}...")

                # === LEVEL 3: Decision/Task/Artifact 생성 ===

                # 1. Decision 노드 생성 (AgentExecution -[:MADE_DECISION]-> Decision)
                decision_id = self.provenance_tracker.create_decision(
                    turn_id=turn_id,
                    agent_slug=self.consumer.current_agent_slug,
                    decision_type='response_generation',
                    description=f'Generated response for user query: {content[:50]}...',
                    rationale='Processed user request and generated appropriate response using A2A protocol',
                    confidence=1.0,
                    metadata={'response_length': len(result['response']), 'agent_name': result.get('agent_name', 'AI')},
                    execution_id=execution_id
                )
                logger.info(f"Neo4j Decision created: {decision_id}")

                # 2. Task 노드 생성 (Decision -[:CREATES_TASK]-> Task)
                task_id = self.task_manager.create_task(
                    turn_id=turn_id,
                    description=f'Generate response for: {content[:100]}...',
                    priority=5,
                    status='DONE',
                    decision_id=decision_id
                )
                logger.info(f"Neo4j Task created: {task_id}")

                # 3. Task -[:EXECUTED_BY]-> AgentExecution 관계 생성
                self.task_manager.assign_task_to_agent(
                    task_id=task_id,
                    agent_slug=self.consumer.current_agent_slug,
                    execution_id=execution_id
                )
                logger.info(f"Neo4j Task assigned to AgentExecution: {task_id} -> {execution_id}")

                # 4. Artifact 노드 생성 (AgentExecution -[:PRODUCED]-> Artifact)
                artifact_id = self.provenance_tracker.create_artifact(
                    task_id=task_id,
                    artifact_type='assistant_response',
                    content=result['response'],
                    format='text',
                    metadata={
                        'agent_slug': self.consumer.current_agent_slug,
                        'agent_name': result.get('agent_name', 'AI'),
                        'response_length': len(result['response'])
                    },
                    execution_id=execution_id
                )
                logger.info(f"Neo4j Artifact created: {artifact_id}")

                # Django 모델에도 저장 (기존 로직 유지)
                await self.consumer._save_message(result['response'], 'text', 'assistant', {
                    'agent_slug': self.consumer.current_agent_slug,
                    'processing_type': 'a2a_agent'
                })

                # Response already sent at line 156-163, no need to send again
            else:
                # Fallback to Gemini (only if Gemini service available)
                if self.gemini_service:
                    await self._fallback_to_gemini(content, user_message)
                else:
                    # No Gemini fallback available (text-only mode)
                    await self.consumer._send_error(f"A2A processing failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            await self.consumer._send_error(f"Text processing failed: {str(e)}")

    async def handle_text_audio(self, data):
        """Handle text with audio response"""
        content = data.get('message', '').strip()
        voice_name = data.get('voice', 'Aoede')

        if not content:
            await self.consumer._send_error("Empty message content")
            return

        try:
            user_message = await self.consumer._save_message(content, 'text', 'user')

            # For debugging, skip A2A and go directly to Gemini
            logger.info(f"Processing text_audio with Gemini: {content}")
            await self._process_with_gemini_tts(content, voice_name, user_message)

        except Exception as e:
            logger.error(f"Text audio processing failed: {e}")
            await self.consumer._send_error(f"Text audio processing failed: {str(e)}")

    async def handle_audio(self, data):
        """Handle audio input with transcript and A2A processing"""
        audio_data = data.get('audio', '')
        voice_name = data.get('voice', 'Aoede')

        if not audio_data:
            await self.consumer._send_error("No audio data provided")
            return

        try:
            # Decode and validate audio
            audio_bytes = base64.b64decode(audio_data)
            if len(audio_bytes) > 50 * 1024 * 1024:
                await self.consumer._send_error("Audio too large (max 50MB)")
                return

            user_message = await self.consumer._save_message("[Audio Input] Voice message", 'audio', 'user')

            # Process with Gemini to get transcript
            gemini_result = await self.gemini_service.process_audio_with_audio(
                audio_bytes, voice_name, self.session_id
            )

            user_transcript = gemini_result.get('input_transcript', '')

            if user_transcript:
                # Try A2A processing with transcript
                a2a_result = await self._process_with_a2a(user_transcript)

                if a2a_result['success']:
                    # Generate TTS for A2A response
                    await self._send_a2a_audio_response(
                        a2a_result, user_transcript, voice_name, user_message
                    )
                    return

            # Fallback to original Gemini response
            await self._send_gemini_audio_response(gemini_result, voice_name, user_message)

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            await self.consumer._send_error(f"Audio processing failed: {str(e)}")

    async def handle_a2a_delegation(self, data):
        """Handle A2A delegation requests"""
        try:
            target_agent = data.get('target_agent')
            user_message = data.get('user_message', '')
            delegation_reason = data.get('reason', 'Semantic routing delegation')

            if not target_agent:
                await self.consumer._send_error("Target agent is required for delegation")
                return

            if not user_message:
                await self.consumer._send_error("User message is required for delegation")
                return

            # Verify target agent exists
            agent = await self.worker_manager.get_worker(target_agent)
            if not agent:
                await self.consumer._send_error(f"Target agent '{target_agent}' not found")
                return

            # Switch to target agent
            old_agent = self.consumer.current_agent_slug
            self.consumer.current_agent_slug = target_agent

            from .utils import safe_log_text
            logger.info(f"A2A delegation: {old_agent} -> {target_agent} for message: {safe_log_text(user_message[:50])}...")

            # Process message with new agent
            result = await self._process_with_a2a(user_message)

            if result['success']:
                # Save delegation message
                await self.consumer._save_message(user_message, 'text', 'user')
                await self.consumer._save_message(result['response'], 'text', 'assistant', {
                    'agent_slug': self.consumer.current_agent_slug,
                    'delegated_from': old_agent,
                    'delegation_reason': delegation_reason
                })

                # Get voice for target agent (Flight Agent = 'Kore')
                voice_name = data.get('voice', 'Kore' if target_agent == 'flight-specialist' else 'Aoede')

                # Convert Flight Agent response to TTS using existing Gemini service
                try:
                    audio_result = await self.gemini_service.process_text_with_audio_streaming(
                        result['response'], voice_name, self.session_id, callback=None
                    )

                    audio_base64 = None
                    if audio_result.get('audio') and audio_result['success']:
                        audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

                    # Send A2A response with audio (use existing a2a_response type)
                    await self.websocket_send(text_data=json.dumps({
                        'type': 'a2a_response',  # Use existing a2a_response type
                        'agent': agent.agent_name,
                        'message': result['response'],
                        'audio': audio_base64,
                        'voice': voice_name,
                        'agent_slug': target_agent,
                        'original_message': user_message,
                        'delegated_from': old_agent,
                        'reason': delegation_reason,
                        'success': True
                    }))

                except Exception as tts_error:
                    logger.error(f"TTS conversion failed for A2A response: {tts_error}")
                    # Fallback to text-only response
                    await self.websocket_send(text_data=json.dumps({
                        'type': 'a2a_response',
                        'agent': agent.agent_name,
                        'message': result['response'],
                        'audio': None,
                        'voice': voice_name,
                        'agent_slug': target_agent,
                        'original_message': user_message,
                        'delegated_from': old_agent,
                        'reason': delegation_reason,
                        'success': True
                    }))
            else:
                # Delegation failed, revert to original agent
                self.consumer.current_agent_slug = old_agent
                await self.consumer._send_error(f"Delegation to {target_agent} failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"A2A delegation failed: {e}")
            await self.consumer._send_error(f"A2A delegation failed: {str(e)}")

    async def handle_semantic_routing(self, data):
        """Handle LLM-based semantic routing for A2A delegation"""
        try:
            user_message = data.get('user_message', '').strip()
            current_agent = data.get('current_agent', self.consumer.current_agent_slug)

            if not user_message:
                await self.consumer._send_error("No user message provided for semantic routing")
                return

            from .utils import safe_log_text
            logger.info(f"LLM semantic routing analysis for: '{safe_log_text(user_message)}' with current agent: {current_agent}")

            # Use Gemini LLM for semantic intent analysis
            routing_result = await self._analyze_intent_with_similarity(user_message, current_agent)

            # Send semantic routing result
            await self.websocket_send(text_data=json.dumps({
                'type': 'semantic_routing_result',
                'should_delegate': routing_result['should_delegate'],
                'target_agent': routing_result['target_agent'],
                'confidence': routing_result['confidence'],
                'original_message': user_message,
                'current_agent': current_agent,
                'analysis': routing_result['analysis'],
                'reasoning': routing_result['reasoning'],
                'success': True
            }))

        except Exception as e:
            logger.error(f"Semantic routing failed: {e}")
            await self.consumer._send_error(f"Semantic routing failed: {str(e)}")

    async def _process_with_a2a(self, user_input: str) -> Dict[str, Any]:
        """Core A2A processing logic"""
        try:
            agent = await self.worker_manager.get_worker(self.consumer.current_agent_slug)
            if not agent:
                return {'success': False, 'error': 'Agent not available'}

            response = await agent.process_request(
                user_input=user_input,
                context_id=self.session_id,
                session_id=self.session_id,
                user_name=self.user_obj.username if self.user_obj else "user"
            )

            # DEBUG: Log response
            from .utils import safe_log_text
            logger.info(f"[DEBUG] Agent response type: {type(response)}, length: {len(str(response)) if response else 0}")
            logger.info(f"[DEBUG] Agent response content: {safe_log_text(str(response)[:200]) if response else 'EMPTY'}")

            return {
                'success': True,
                'response': response,
                'agent_name': agent.agent_name
            }

        except Exception as e:
            logger.error(f"A2A processing failed: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_a2a_response(self, a2a_response: str, voice_name: str, user_text: str):
        """A2A 응답을 TTS로 변환하여 전송"""
        try:
            # A2A 응답을 음성으로 변환
            audio_result = await self.gemini_service.process_text_with_audio_streaming(
                a2a_response, voice_name, self.session_id, callback=None
            )

            # 메시지 저장
            await self.consumer._save_message(user_text, 'text', 'user', {
                'delegated_to_a2a': True,
                'target_agent': voice_name
            })

            await self.consumer._save_message(
                audio_result.get('transcript', a2a_response), 'audio', 'assistant', {
                    'voice': voice_name,
                    'has_audio': audio_result['success'],
                    'from_a2a': True,
                    'input_transcript': user_text
                }
            )

            # 오디오 응답 전송
            audio_base64 = None
            if audio_result.get('audio') and audio_result['success']:
                audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

            await self.websocket_send(text_data=json.dumps({
                'type': 'a2a_audio_response',
                'transcript': a2a_response,
                'audio': audio_base64,
                'voice': voice_name,
                'input_transcript': user_text,
                'success': audio_result['success'],
                'source': 'a2a_agent'
            }))

            logger.info(f"A2A 응답 전송 완료: {voice_name} - {a2a_response[:50]}...")

            # Context7 패턴: interrupt 후 별도 resume 불필요
            logger.info("A2A response completed - Context7 interrupt pattern applied")

        except Exception as e:
            logger.error(f"A2A 응답 처리 실패: {e}")
            # Context7 패턴: interrupt 후 별도 resume 불필요
            await self.consumer._send_error(f"A2A 응답 처리 실패: {str(e)}")

    # Context7 패턴: TTS 재생 후 별도 resume 불필요 (메서드 제거)

    async def _analyze_intent_with_similarity(self, user_message: str, current_agent: str) -> dict:
        """Use semantic similarity with agent cards to determine routing"""
        try:
            # Import sentence transformers
            from sentence_transformers import SentenceTransformer, util
            from agents.worker_agents.card_loader import load_agent_cards
            import asyncio
            import concurrent.futures

            # Load agent cards dynamically (NO pre-filtering - pure semantic routing)
            agent_cards = load_agent_cards()

            # Build capability texts from agent cards (ONLY EXAMPLES - like semantic-router)
            agent_capabilities = {}
            for slug, card in agent_cards.items():
                # Normalize slug to hyphen format for consistency
                normalized_slug = slug.replace('_', '-')

                examples = []

                # ONLY use example utterances from skills (NO tags, NO descriptions)
                for skill in card.get('skills', []):
                    # Add example phrases only
                    examples.extend(skill.get('examples', []))

                # Filter out empty strings
                agent_capabilities[normalized_slug] = [ex for ex in examples if ex and ex.strip()]

            # Load model with caching
            if not hasattr(self, '_embedding_model'):
                self._embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("Embedding model loaded and cached")

            def compute_similarities():
                # Encode user message
                user_embedding = self._embedding_model.encode([user_message])

                # Compute similarities for each agent
                similarities = {}
                for agent, capabilities in agent_capabilities.items():
                    if not capabilities:
                        similarities[agent] = 0.0
                        continue

                    # Encode capabilities
                    capability_embeddings = self._embedding_model.encode(capabilities)

                    # Compute similarity between user message and each capability
                    sims = util.cos_sim(user_embedding, capability_embeddings)

                    # Take the maximum similarity across all capabilities
                    max_sim = float(sims.max())
                    similarities[agent] = max_sim

                return similarities

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                similarities = await loop.run_in_executor(executor, compute_similarities)

            # Determine best agent based on similarity
            sorted_agents = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
            best_agent, best_score = sorted_agents[0]
            second_score = sorted_agents[1][1] if len(sorted_agents) > 1 else 0.0

            # Best Practice Thresholds (based on semantic-router research)
            specialist_threshold = 0.75  # High confidence for specialists
            general_threshold = 0.5      # Medium confidence for general
            confidence_gap_threshold = 0.10  # Gap between 1st and 2nd score (relaxed from 0.15)

            # Calculate confidence gap
            confidence_gap = best_score - second_score

            # Check if best is specialist and meets threshold
            # Support both hyphen and underscore formats
            is_specialist = best_agent in [
                'flight-specialist', 'hotel-specialist',
                'flight_specialist', 'hotel_specialist'
            ]
            threshold = specialist_threshold if is_specialist else general_threshold

            # Decision logic with confidence gap consideration
            meets_threshold = best_score >= threshold
            has_confidence_gap = confidence_gap >= confidence_gap_threshold

            should_delegate = meets_threshold and has_confidence_gap

            # If specialist doesn't meet criteria, fallback to hostagent
            if is_specialist and not (meets_threshold and has_confidence_gap):
                best_agent = 'hostagent'
                best_score = similarities.get('hostagent', 0.0)
                # Recalculate gap and threshold for fallback scenario
                # Find the next highest score after hostagent
                hostagent_rank = next((i for i, (agent, _) in enumerate(sorted_agents) if agent == 'hostagent'), -1)
                if hostagent_rank >= 0 and hostagent_rank + 1 < len(sorted_agents):
                    second_score = sorted_agents[hostagent_rank + 1][1]
                else:
                    second_score = 0.0
                confidence_gap = best_score - second_score
                threshold = general_threshold  # hostagent uses general threshold
                # Hostagent doesn't need delegation from itself
                should_delegate = False

            from .utils import safe_log_text
            logger.info(f"Semantic similarity analysis: {safe_log_text(user_message)} | "
                       f"host: {similarities.get('hostagent', 0):.3f} | "
                       f"flight: {similarities.get('flight-specialist', 0):.3f} | "
                       f"hotel: {similarities.get('hotel-specialist', 0):.3f} | "
                       f"best: {best_agent}({best_score:.3f}) | gap: {confidence_gap:.3f} | "
                       f"threshold: {threshold:.2f} | delegate: {should_delegate}")

            # Additional validation
            if should_delegate and best_agent == current_agent:
                should_delegate = False

            return {
                'should_delegate': should_delegate,
                'target_agent': best_agent if should_delegate else None,
                'confidence': best_score,
                'analysis': f"Semantic similarity: {best_agent}({best_score:.3f})",
                'reasoning': f"최고 유사도: {best_score:.3f} (임계값: {threshold})"
            }

        except Exception as e:
            logger.error(f"Semantic similarity analysis failed: {e}", exc_info=True)
            return {
                'should_delegate': False,
                'target_agent': None,
                'confidence': 0.0,
                'analysis': "유사도 분석 실패, hostagent 처리",
                'reasoning': f"분석 중 오류 발생: {str(e)}"
            }

    # Helper methods for Gemini processing
    async def _process_with_gemini_tts(self, content: str, voice_name: str, user_message):
        """Process text with Gemini TTS"""
        try:
            result = await self.gemini_service.process_text_with_audio_streaming(
                content, voice_name, self.session_id, callback=None
            )

            await self.consumer._save_message(result.get('transcript', content), 'audio', 'assistant', {
                'voice': voice_name,
                'has_audio': result['success']
            })

            audio_base64 = None
            if result.get('audio') and result['success']:
                audio_base64 = base64.b64encode(result['audio']).decode('utf-8')

            await self.websocket_send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': result.get('transcript', ''),
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'success': result['success']
            }))

        except Exception as e:
            logger.error(f"Gemini TTS processing failed: {e}")
            await self.consumer._send_error(f"TTS processing failed: {str(e)}")

    async def _fallback_to_gemini(self, content: str, user_message):
        """Fallback to Gemini when A2A fails"""
        try:
            result = await self.gemini_service.process_text_with_streaming(
                content, self.session_id, callback=None
            )

            await self.consumer._save_message(result['text'], 'text', 'assistant', {
                'model': result['model'],
                'fallback_from_a2a': True
            })

            await self.websocket_send(text_data=json.dumps({
                'type': 'response',
                'message': result['text'],
                'user_message_id': str(user_message.id),
                'model': result['model'],
                'success': True
            }))

        except Exception as e:
            logger.error(f"Gemini fallback failed: {e}")
            await self.consumer._send_error(f"Processing failed: {str(e)}")

    async def _send_a2a_audio_response(self, a2a_result, user_transcript, voice_name, user_message):
        """Send A2A response with TTS"""
        try:
            # Generate TTS for A2A response
            audio_result = await self.gemini_service.process_text_with_audio_streaming(
                a2a_result['response'], voice_name, self.session_id, callback=None
            )

            audio_base64 = None
            if audio_result.get('audio') and audio_result['success']:
                audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

            await self.consumer._save_message(a2a_result['response'], 'audio', 'assistant', {
                'agent_slug': self.consumer.current_agent_slug,
                'voice': voice_name,
                'has_audio': audio_result['success'],
                'input_transcript': user_transcript
            })

            await self.websocket_send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': a2a_result['response'],
                'input_transcript': user_transcript,
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'agent_slug': self.consumer.current_agent_slug,
                'success': audio_result['success']
            }))

        except Exception as e:
            logger.error(f"A2A TTS failed: {e}")
            await self.consumer._send_error(f"A2A TTS failed: {str(e)}")

    async def _send_gemini_audio_response(self, gemini_result, voice_name, user_message):
        """Send Gemini audio response"""
        try:
            await self.consumer._save_message(
                gemini_result.get('transcript', 'No transcript available'),
                'audio', 'assistant', {
                    'voice': voice_name,
                    'has_audio': gemini_result['success'],
                    'input_transcript': gemini_result.get('input_transcript', '')
                }
            )

            audio_base64 = None
            if gemini_result.get('audio') and gemini_result['success']:
                audio_base64 = base64.b64encode(gemini_result['audio']).decode('utf-8')

            await self.websocket_send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': gemini_result.get('transcript', ''),
                'input_transcript': gemini_result.get('input_transcript', ''),
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'success': gemini_result['success']
            }))

        except Exception as e:
            logger.error(f"Gemini audio response failed: {e}")
            await self.consumer._send_error(f"Gemini audio response failed: {str(e)}")