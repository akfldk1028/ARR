"""
Django management command to create second test agent for worker-to-worker communication
Usage: python manage.py create_second_agent
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from agents.models import Agent
from core.models import Organization, Tag

class Command(BaseCommand):
    help = 'Create second agent for worker-to-worker communication testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating second test agent...')

        # Get existing organization
        try:
            org = Organization.objects.get(name='Test Organization')
            user = User.objects.get(username='testuser')
        except (Organization.DoesNotExist, User.DoesNotExist):
            self.stdout.write(
                self.style.ERROR('Please run create_test_agent first to create organization and user')
            )
            return

        # Create specialized agent
        agent, created = Agent.objects.get_or_create(
            slug='flight-specialist',
            defaults={
                'name': 'Flight Specialist Agent',
                'agent_type': 'gpt',
                'description': 'Specialized agent for flight booking and travel information',
                'organization': org,
                'created_by': user,
                'model_name': 'gpt-3.5-turbo',
                'system_prompt': '''You are a specialized flight booking agent. You have access to flight information and can:
1. Search for available flights between cities
2. Provide flight schedules and pricing
3. Help with booking confirmations
4. Give travel advice and recommendations

Always be helpful and provide detailed flight information when requested.''',
                'capabilities': ['text', 'flight_booking', 'travel_info'],
                'status': 'active',
                'max_concurrent_sessions': 5,
                'rate_limit_per_minute': 30,
                'config': {
                    'temperature': 0.3,  # Lower temperature for more factual responses
                    'max_tokens': 1024,
                    'specialization': 'flight_booking'
                }
            }
        )

        if created:
            # Add tags
            try:
                tag1 = Tag.objects.get(name='AI Assistant', organization=org)
                tag2 = Tag.objects.get(name='LangGraph', organization=org)
                tag3, _ = Tag.objects.get_or_create(
                    name='Flight Specialist',
                    organization=org,
                    defaults={'color': '#ff6600'}
                )
                agent.tags.add(tag1, tag2, tag3)
            except Tag.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING('Some tags not found, agent created without tags')
                )

            self.stdout.write(
                self.style.SUCCESS(f'Second agent created: {agent.name} (slug: {agent.slug})')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Second agent already exists: {agent.name}')
            )

        self.stdout.write('Second agent creation completed!')
        self.stdout.write(f'Agent card URL: http://localhost:8000/.well-known/agent-card/{agent.slug}.json')
        self.stdout.write(f'Agent chat URL: http://localhost:8000/agents/{agent.slug}/chat/')