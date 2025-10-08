"""
Sync Agent Cards Management Command

Syncs JSON agent cards to Django database.
JSON cards are the source of truth, Django DB is the cache.
"""

from django.core.management.base import BaseCommand
from agents.worker_agents.card_loader import AgentCardLoader


class Command(BaseCommand):
    help = 'Sync JSON agent cards to Django database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear card cache before syncing',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('  Syncing Agent Cards: JSON -> Django DB'))
        self.stdout.write(self.style.WARNING('=' * 60))

        # Clear cache if requested
        if options['clear_cache']:
            self.stdout.write('Clearing card cache...')
            AgentCardLoader.clear_cache()

        # Load cards from JSON files
        self.stdout.write('\nLoading agent cards from JSON files...')
        cards = AgentCardLoader.load_all_cards()
        self.stdout.write(self.style.SUCCESS(f'[OK] Found {len(cards)} agent cards'))

        # Display cards
        self.stdout.write('\nAgent Cards:')
        for slug, card in cards.items():
            self.stdout.write(f"  - {slug:20s} - {card.get('name')}")

        # Sync to database
        self.stdout.write('\nSyncing to Django database...')
        synced_count = AgentCardLoader.sync_to_database()

        # Success summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(f'  [OK] Successfully synced {synced_count} agents'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Note: JSON cards are now the source of truth.'))
        self.stdout.write(self.style.WARNING('      Django DB is just a cache for queries.'))
