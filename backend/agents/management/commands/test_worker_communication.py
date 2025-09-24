"""
Django management command to test worker-to-worker A2A communication
Usage: python manage.py test_worker_communication
"""

import asyncio
from django.core.management.base import BaseCommand
from agents.a2a_client import A2ACardResolver, A2AClient, a2a_registry
from agents.database.neo4j import initialize_neo4j

class Command(BaseCommand):
    help = 'Test worker-to-worker A2A communication'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-agent',
            type=str,
            default='test-agent',
            help='Source agent slug (default: test-agent)'
        )
        parser.add_argument(
            '--target-agent',
            type=str,
            default='flight-specialist',
            help='Target agent slug (default: flight-specialist)'
        )

    def handle(self, *args, **options):
        source_agent = options['source_agent']
        target_agent = options['target_agent']

        self.stdout.write(f'Testing worker-to-worker communication:')
        self.stdout.write(f'Source Agent: {source_agent}')
        self.stdout.write(f'Target Agent: {target_agent}')

        # Initialize Neo4j
        if initialize_neo4j():
            self.stdout.write(
                self.style.SUCCESS('Neo4j connection established')
            )

        # Run async test
        asyncio.run(self._test_worker_communication(source_agent, target_agent))

    async def _test_worker_communication(self, source_agent: str, target_agent: str):
        """Test A2A communication between workers"""
        try:
            self.stdout.write('\n=== Step 1: Agent Discovery ===')

            # Discover target agent
            target_url = f'http://localhost:8002'
            resolver = A2ACardResolver(target_url)

            self.stdout.write(f'Discovering {target_agent} agent card...')
            target_card = await resolver.get_agent_card(target_agent)

            if not target_card:
                self.stdout.write(
                    self.style.ERROR(f'Failed to discover {target_agent} agent card')
                )
                return

            self.stdout.write(
                self.style.SUCCESS(f'SUCCESS: Discovered: {target_card.name}')
            )
            self.stdout.write(f'Description: {target_card.description}')
            self.stdout.write(f'Capabilities: {target_card.capabilities}')
            self.stdout.write(f'Endpoints: {target_card.endpoints}')

            self.stdout.write('\n=== Step 2: Worker-to-Worker Communication ===')

            # Create A2A client
            client = A2AClient(target_card)

            # Test messages - simulating one agent asking another for help
            test_scenarios = [
                {
                    "message": "Hello! I'm the general assistant. A user is asking me about flights from Seoul to Tokyo. Can you help with flight information?",
                    "context": "inter_agent_collaboration_1"
                },
                {
                    "message": "What are the typical flight times between Seoul and Tokyo?",
                    "context": "flight_inquiry_1"
                },
                {
                    "message": "Can you recommend the best airlines for Seoul to Tokyo route?",
                    "context": "flight_recommendation_1"
                }
            ]

            for i, scenario in enumerate(test_scenarios, 1):
                self.stdout.write(f'\n--- Test Message {i} ---')
                self.stdout.write(f'Sending: {scenario["message"][:80]}...')

                response = await client.send_message(
                    message=scenario["message"],
                    context_id=scenario["context"],
                    session_id=f'worker_test_{i}'
                )

                if response:
                    self.stdout.write(
                        self.style.SUCCESS(f'SUCCESS: Response received')
                    )
                    self.stdout.write(f'Response: {response[:200]}...')
                else:
                    self.stdout.write(
                        self.style.ERROR(f'ERROR: No response received')
                    )

            self.stdout.write('\n=== Step 3: Bidirectional Communication Test ===')

            # Now test the reverse - flight agent could potentially call general agent
            self.stdout.write('Testing reverse communication (if possible)...')

            general_card = await resolver.get_agent_card(source_agent)
            if general_card:
                reverse_client = A2AClient(general_card)

                reverse_response = await reverse_client.send_message(
                    message="Hi! I'm the flight specialist. I have flight information that might be useful for general travel questions.",
                    context_id="reverse_communication_test",
                    session_id="reverse_test_1"
                )

                if reverse_response:
                    self.stdout.write(
                        self.style.SUCCESS('SUCCESS: Reverse communication successful')
                    )
                    self.stdout.write(f'Reverse Response: {reverse_response[:200]}...')
                else:
                    self.stdout.write(
                        self.style.WARNING('WARNING: Reverse communication failed')
                    )

            self.stdout.write('\n=== Step 4: Multi-Agent Collaboration Simulation ===')

            # Simulate a complex scenario where agents need to collaborate
            collaboration_message = """
            I'm coordinating a complex travel request. A user wants to:
            1. Fly from Seoul to Tokyo on December 15th
            2. Stay for 3 days
            3. Return on December 18th

            Can you provide detailed flight options and recommendations?
            This is part of a multi-agent collaboration where I handle general coordination
            and you handle flight specifics.
            """

            self.stdout.write('Testing multi-agent collaboration scenario...')

            collab_response = await client.send_message(
                message=collaboration_message,
                context_id="multi_agent_collaboration",
                session_id="complex_travel_request"
            )

            if collab_response:
                self.stdout.write(
                    self.style.SUCCESS('SUCCESS: Multi-agent collaboration successful')
                )
                self.stdout.write('Collaboration Response:')
                self.stdout.write(f'{collab_response}')
            else:
                self.stdout.write(
                    self.style.ERROR('ERROR: Multi-agent collaboration failed')
                )

            self.stdout.write('\n=== Worker Communication Test Complete ===')
            self.stdout.write(
                self.style.SUCCESS('SUCCESS: Worker-to-worker A2A communication test finished!')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'ERROR: Worker communication test failed: {str(e)}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())