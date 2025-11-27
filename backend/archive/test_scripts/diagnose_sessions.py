"""
Django ChatSession vs Neo4j Conversation 진단 스크립트
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from gemini.models import ChatSession, ChatMessage
from graph_db.services import get_neo4j_service
from django.contrib.auth.models import User

def main():
    print("=" * 60)
    print("SESSION/CONVERSATION DIAGNOSIS")
    print("=" * 60)

    # 1. Django ChatSession 현황
    print("\n[1] Django ChatSession")
    print("-" * 60)

    all_sessions = ChatSession.objects.all()
    active_sessions = ChatSession.objects.filter(is_active=True)

    print(f"  Total ChatSessions: {all_sessions.count()}")
    print(f"  Active ChatSessions: {active_sessions.count()}")

    if all_sessions.exists():
        print("\n  Recent Sessions:")
        for session in all_sessions[:5]:
            msg_count = session.messages.count()
            active = "ACTIVE" if session.is_active else "inactive"
            user = session.user.username if session.user else "anonymous"
            print(f"    [{active}] {session.id.hex[:8]} | User: {user} | Messages: {msg_count} | {session.created_at}")

    # 2. Neo4j Conversation 현황
    print("\n[2] Neo4j Conversation")
    print("-" * 60)

    neo4j = get_neo4j_service()

    # Count conversations
    conv_query = "MATCH (c:Conversation) RETURN count(c) as count"
    result = neo4j.execute_query(conv_query)
    conv_count = result[0]['count'] if result else 0
    print(f"  Total Conversations: {conv_count}")

    # Show conversations with turn counts
    if conv_count > 0:
        detail_query = """
        MATCH (c:Conversation)
        OPTIONAL MATCH (c)-[:HAS_TURN]->(t:Turn)
        RETURN c.id as conv_id,
               c.user_id as user_id,
               c.django_session_id as django_session_id,
               c.current_agent as current_agent,
               count(DISTINCT t) as turn_count,
               c.started_at as started_at
        ORDER BY c.started_at DESC
        LIMIT 5
        """
        conversations = neo4j.execute_query(detail_query)

        print("\n  Recent Conversations:")
        for conv in conversations:
            conv_id = conv['conv_id'][:16] if conv['conv_id'] else 'N/A'
            user_id = conv['user_id'] or 'anonymous'
            turn_count = conv['turn_count'] or 0
            django_session = conv.get('django_session_id', 'N/A')[:8] if conv.get('django_session_id') else 'N/A'
            agent = conv.get('current_agent', 'N/A')

            print(f"    {conv_id} | User: {user_id} | Agent: {agent} | Turns: {turn_count} | Django: {django_session}")

    # 3. 매칭 분석
    print("\n[3] Django vs Neo4j Matching")
    print("-" * 60)

    if all_sessions.exists():
        for session in all_sessions[:3]:
            session_id = str(session.id)
            msg_count = session.messages.count()

            # Find matching Neo4j conversation
            match_query = """
            MATCH (c:Conversation)
            WHERE c.django_session_id = $session_id
            OPTIONAL MATCH (c)-[:HAS_TURN]->(t:Turn)
            RETURN c.id as conv_id, count(DISTINCT t) as turn_count
            """
            match_result = neo4j.execute_query(match_query, {'session_id': session_id})

            if match_result and match_result[0].get('conv_id'):
                conv_id = match_result[0]['conv_id'][:16]
                turn_count = match_result[0]['turn_count']
                print(f"  Django {session_id[:8]} ({msg_count} msgs) → Neo4j {conv_id} ({turn_count} turns)")
            else:
                print(f"  Django {session_id[:8]} ({msg_count} msgs) → NO MATCHING Neo4j conversation")

    # 4. 문제 감지
    print("\n[4] Detected Issues")
    print("-" * 60)

    issues = []

    # Issue 1: Multiple active sessions per user
    users_with_multiple_active = User.objects.filter(
        chatsession__is_active=True
    ).annotate(
        active_count=models.Count('chatsession')
    ).filter(active_count__gt=1)

    if users_with_multiple_active.exists():
        issues.append(f"WARNING: {users_with_multiple_active.count()} users have multiple active sessions")

    # Issue 2: Neo4j conversations without Django session
    orphan_query = """
    MATCH (c:Conversation)
    WHERE c.django_session_id IS NULL OR c.django_session_id = ''
    RETURN count(c) as count
    """
    orphan_result = neo4j.execute_query(orphan_query)
    orphan_count = orphan_result[0]['count'] if orphan_result else 0

    if orphan_count > 0:
        issues.append(f"WARNING: {orphan_count} Neo4j conversations without django_session_id")

    # Issue 3: Django sessions without messages
    empty_sessions = ChatSession.objects.filter(messages__isnull=True).count()
    if empty_sessions > 0:
        issues.append(f"INFO: {empty_sessions} Django sessions have no messages")

    if issues:
        for issue in issues:
            print(f"  ! {issue}")
    else:
        print("  OK No issues detected")

    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    from django.db import models
    main()
