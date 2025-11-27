"""
Migrate import paths from agents.database.neo4j to graph_db
"""

import os
import re

# Files to update and their old -> new import mappings
FILES_TO_UPDATE = [
    'chat/consumers.py',
    'gemini/consumers/simple_consumer.py',
    'gemini/consumers/handlers/a2a_handler.py',
    'agents/worker_agents/base/base_worker.py',
]

OLD_IMPORTS = {
    'from agents.database.neo4j.service import get_neo4j_service':
        'from graph_db.services import get_neo4j_service',

    'from agents.database.neo4j import ConversationTracker, TaskManager, ProvenanceTracker':
        'from graph_db.tracking import ConversationTracker, TaskManager, ProvenanceTracker',

    'from agents.database.neo4j import ConversationTracker':
        'from graph_db.tracking import ConversationTracker',

    'from agents.database.neo4j import TaskManager':
        'from graph_db.tracking import TaskManager',

    'from agents.database.neo4j import ProvenanceTracker':
        'from graph_db.tracking import ProvenanceTracker',
}

def update_file(filepath):
    """Update import paths in a single file"""
    if not os.path.exists(filepath):
        print(f'[SKIP] {filepath} not found')
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    modified = False

    for old_import, new_import in OLD_IMPORTS.items():
        if old_import in content:
            content = content.replace(old_import, new_import)
            modified = True
            print(f'[UPDATE] {filepath}')
            print(f'  {old_import}')
            print(f'  -> {new_import}')

    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    else:
        print(f'[OK] {filepath} - no changes needed')
        return False

def main():
    print('=== Migrating imports to graph_db ===\n')

    updated_count = 0
    for filepath in FILES_TO_UPDATE:
        if update_file(filepath):
            updated_count += 1
        print()

    print(f'\n[DONE] Updated {updated_count}/{len(FILES_TO_UPDATE)} files')

if __name__ == '__main__':
    main()
