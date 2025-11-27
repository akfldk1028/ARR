from graph_db.services import get_neo4j_service

service = get_neo4j_service()

# Conversation별 Turn 확인
result = service.execute_query('''
MATCH (c:Conversation)-[:HAS_TURN]->(t:Turn)
RETURN
    c.id as conv_id,
    t.sequence as sequence,
    t.started_at as started_at
ORDER BY c.id, t.sequence
''', {})

print('\n=== Conversation별 Turn Sequence ===')
current_conv = None
for r in result:
    conv_short = r['conv_id'][:16]
    if current_conv != r['conv_id']:
        print(f'\n[Conversation: {conv_short}...]')
        current_conv = r['conv_id']
    print(f'  Turn {r["sequence"]} | {r["started_at"]}')

# Conversation 개수
conv_count = service.execute_query('''
MATCH (c:Conversation)
RETURN count(c) as count
''', {})

print(f'\n총 Conversation: {conv_count[0]["count"]}개')
