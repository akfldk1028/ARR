"""
Test Agent-to-Agent Conversations
Django management command to test multi-agent conversation functionality
"""

import asyncio
import json
import logging
from typing import List, Dict, Any

from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async

from agents.worker_agents.conversation_coordinator import (
    conversation_coordinator, ConversationRule,
    start_multi_agent_conversation, get_conversation_summary
)
from agents.worker_agents.conversation_types import ConversationState


class Command(BaseCommand):
    help = 'Test agent-to-agent conversation functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--agents',
            type=str,
            default='general-worker,flight-specialist',
            help='Comma-separated list of agent slugs'
        )
        parser.add_argument(
            '--topic',
            type=str,
            default='Travel Planning Discussion',
            help='Conversation topic'
        )
        parser.add_argument(
            '--message',
            type=str,
            default='I need help planning a trip to Korea. Can you help me with flights and accommodation?',
            help='Initial message to start conversation'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=60,
            help='Test duration in seconds'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging'
        )

    def handle(self, *args, **options):
        # Configure logging
        if options['verbose']:
            logging.basicConfig(level=logging.INFO)
            logging.getLogger('agents.conversation_coordination').setLevel(logging.INFO)
            logging.getLogger('agents.a2a_streaming').setLevel(logging.INFO)

        # Run async test
        asyncio.run(self.run_test(options))

    async def run_test(self, options: Dict[str, Any]):
        """Run agent conversation test"""
        agent_slugs = [slug.strip() for slug in options['agents'].split(',')]
        topic = options['topic']
        initial_message = options['message']
        duration = options['duration']

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Agent-to-Agent Conversation Test\n"
                f"Topic: {topic}\n"
                f"Agents: {', '.join(agent_slugs)}\n"
                f"Message: {initial_message}\n"
                f"Duration: {duration}s\n"
            )
        )

        # Test conversation events
        conversation_events = []

        async def websocket_callback(event_data):
            """Capture conversation events"""
            conversation_events.append({
                'timestamp': event_data.get('timestamp', 0),
                'type': event_data.get('type', 'unknown'),
                'event': event_data
            })

            # Real-time event display
            event_type = event_data.get('type', 'unknown')
            if event_type == 'conversation_started':
                self.stdout.write(
                    self.style.WARNING(f"[START] Conversation started: {event_data.get('conversationId')}")
                )
            elif event_type == 'agent_turn_started':
                agent_name = event_data.get('agent', {}).get('agentName', 'Unknown')
                self.stdout.write(
                    self.style.HTTP_INFO(f"[SPEAK] {agent_name} is speaking...")
                )
            elif event_type == 'agent_turn_completed':
                agent_name = event_data.get('agent', {}).get('agentName', 'Unknown')
                response = event_data.get('response', '')[:100] + "..."
                self.stdout.write(
                    self.style.SUCCESS(f"[DONE] {agent_name}: {response}")
                )
            elif event_type == 'conversation_continuation':
                next_agent = event_data.get('nextAgent', {}).get('agentName', 'Unknown')
                self.stdout.write(
                    self.style.WARNING(f"[SWITCH] Switching to {next_agent}")
                )
            elif event_type == 'conversation_error':
                error = event_data.get('error', 'Unknown error')
                self.stdout.write(
                    self.style.ERROR(f"[ERROR] Error: {error}")
                )

        try:
            # Start conversation
            conversation_id = await start_multi_agent_conversation(
                topic=topic,
                agent_slugs=agent_slugs,
                initial_message=initial_message,
                initiator_id="test_command",
                rules=ConversationRule(
                    max_participants=len(agent_slugs),
                    max_turn_duration=30,
                    max_conversation_duration=duration,
                    auto_escalation=True
                ),
                websocket_callback=websocket_callback
            )

            if not conversation_id:
                self.stdout.write(
                    self.style.ERROR("❌ Failed to start conversation")
                )
                return

            self.stdout.write(
                self.style.SUCCESS(f"✅ Conversation started with ID: {conversation_id}")
            )

            # Monitor conversation
            await self.monitor_conversation(conversation_id, duration)

            # Get final summary
            summary = await get_conversation_summary(conversation_id)
            self.display_conversation_summary(summary, conversation_events)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Test failed: {str(e)}")
            )
            import traceback
            traceback.print_exc()

    async def monitor_conversation(self, conversation_id: str, duration: int):
        """Monitor conversation progress"""
        start_time = asyncio.get_event_loop().time()

        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time

            if elapsed >= duration:
                self.stdout.write(
                    self.style.WARNING(f"[TIMEOUT] Test duration ({duration}s) reached")
                )
                break

            # Check conversation status
            status = conversation_coordinator.get_conversation_status(conversation_id)
            if status:
                state = status['conversation']['context']['state']
                if state in [ConversationState.COMPLETED.value, ConversationState.FAILED.value]:
                    self.stdout.write(
                        self.style.SUCCESS(f"[FINISH] Conversation {state}")
                    )
                    break

            await asyncio.sleep(2)  # Check every 2 seconds

        # Complete conversation if still active
        try:
            await conversation_coordinator.complete_conversation(
                conversation_id,
                reason="test_completed"
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"⚠️  Cleanup warning: {e}")
            )

    def display_conversation_summary(self, summary: Dict[str, Any], events: List[Dict[str, Any]]):
        """Display conversation test results"""
        self.stdout.write(
            self.style.SUCCESS("\n" + "="*60)
        )
        self.stdout.write(
            self.style.SUCCESS("CONVERSATION TEST SUMMARY")
        )
        self.stdout.write(
            self.style.SUCCESS("="*60)
        )

        if summary:
            self.stdout.write(f"Topic: {summary.get('topic', 'N/A')}")
            self.stdout.write(f"Duration: {summary.get('duration', 0):.2f}s")
            self.stdout.write(f"Total Turns: {summary.get('totalTurns', 0)}")
            self.stdout.write(f"Participants: {', '.join(summary.get('participants', []))}")
            self.stdout.write(f"State: {summary.get('state', 'unknown')}")

            # Metrics
            metrics = summary.get('metrics', {})
            if metrics:
                self.stdout.write(f"\nMETRICS:")
                self.stdout.write(f"   - Total Duration: {metrics.get('total_duration', 0):.2f}s")
                self.stdout.write(f"   - Message Count: {metrics.get('message_count', 0)}")
                self.stdout.write(f"   - Successful Delegations: {metrics.get('successful_delegations', 0)}")

                participation = metrics.get('agent_participation', {})
                if participation:
                    self.stdout.write(f"   - Agent Participation:")
                    for agent, count in participation.items():
                        self.stdout.write(f"     * {agent}: {count} turns")

        # Event summary
        self.stdout.write(f"\nEVENTS CAPTURED: {len(events)}")
        event_types = {}
        for event in events:
            event_type = event['event'].get('type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1

        for event_type, count in event_types.items():
            self.stdout.write(f"   - {event_type}: {count}")

        # Test verdict
        self.stdout.write(f"\nTEST VERDICT:")
        if summary and summary.get('state') == ConversationState.COMPLETED.value:
            self.stdout.write(
                self.style.SUCCESS("   [PASSED] Conversation completed successfully")
            )
        elif summary and summary.get('totalTurns', 0) > 0:
            self.stdout.write(
                self.style.WARNING("   [PARTIAL] Conversation started but didn't complete")
            )
        else:
            self.stdout.write(
                self.style.ERROR("   [FAILED] Conversation failed to start or progress")
            )

        self.stdout.write(
            self.style.SUCCESS("="*60 + "\n")
        )


class ConversationTestSuite:
    """Extended test suite for comprehensive testing"""

    @staticmethod
    async def run_basic_test():
        """Basic two-agent conversation test"""
        # Implementation would go here
        pass

    @staticmethod
    async def run_multi_agent_test():
        """Multi-agent conversation test"""
        # Implementation would go here
        pass

    @staticmethod
    async def run_stress_test():
        """Stress test with multiple concurrent conversations"""
        # Implementation would go here
        pass

    @staticmethod
    async def run_error_handling_test():
        """Test error handling and recovery"""
        # Implementation would go here
        pass