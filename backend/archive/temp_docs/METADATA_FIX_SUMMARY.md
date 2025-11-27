# Neo4j Metadata Storage Fix - Summary

## Problem Discovered

Django sessions were appearing to "lump into one conversation" in Neo4j due to metadata storage issues.

### Root Cause
Neo4j node properties **cannot store nested dictionaries (MAP type)**. They only accept:
- Primitive types: string, int, float, bool, date
- Arrays of primitive types

The original code attempted to store metadata as a dict:
```python
# WRONG - Neo4j rejects this:
'metadata': metadata or {}  # Dict type not allowed as property
```

This caused error:
```
Property values can only be of primitive types or arrays thereof.
Encountered: Map{test_key -> String("test_value"), ...}
```

## Solution Implemented

### Hybrid Storage Approach

**For Conversation nodes:**
- Extract critical fields as **separate primitive properties** (queryable)
- Store full metadata as **JSON string** (preserves all data)

```python
# Extract key fields as properties
django_session_id = metadata.get('django_session_id', '')
current_agent = metadata.get('agent', 'hostagent')

CREATE (c:Conversation {
    id: $conversation_id,
    user_id: $user_id,
    django_session_id: $django_session_id,      # Primitive - queryable
    current_agent: $current_agent,              # Primitive - queryable
    started_at: datetime($started_at),
    status: 'active',
    metadata_json: $metadata_json               # JSON string - full preservation
})

params = {
    'django_session_id': django_session_id,
    'current_agent': current_agent,
    'metadata_json': json.dumps(metadata)       # Store as JSON string
}
```

**Benefits:**
1. ✅ Can query conversations by `django_session_id` directly
2. ✅ Full metadata preserved in `metadata_json`
3. ✅ Neo4j constraint satisfied (primitives only)
4. ✅ No data loss

## Files Modified

### 1. `graph_db/tracking/conversation.py`
- **create_conversation()** (lines 50-85): Hybrid approach with `django_session_id`, `current_agent`, `metadata_json`
- **add_message()** (lines 115-157): Changed `metadata` to `metadata_json`
- **create_agent_execution()** (lines 159-195): Changed `metadata` to `metadata_json`

### 2. `diagnose_sessions.py`
Updated queries to use new schema:
- Query `c.django_session_id` instead of `c.metadata.django_session_id`
- Query `c.id` instead of `c.conversation_id`
- Query `c.user_id` instead of `c.username`
- Query `c.current_agent` directly
- Use `HAS_TURN` relationship (not `HAS_SESSION`)

### 3. `test_metadata_map.py`
Updated to test hybrid approach:
- Verify `django_session_id` as primitive property
- Verify `current_agent` as primitive property
- Verify `metadata_json` as valid JSON string
- Test Message metadata storage

## Verification

### Test Results

**test_metadata_map.py:**
```
✅ django_session_id stored as queryable property
✅ current_agent stored as queryable property
✅ metadata_json is valid JSON string
✅ Parsed metadata contains 4 keys
✅ Message metadata_json is valid JSON string
```

**diagnose_sessions.py:**
```
✅ Shows conversations with correct schema
✅ Can query by django_session_id
✅ Properly detects matches/mismatches
✅ No schema errors
```

## Query Examples

### Query conversations by Django session:
```cypher
MATCH (c:Conversation)
WHERE c.django_session_id = 'abc123...'
RETURN c
```

### Query by agent:
```cypher
MATCH (c:Conversation)
WHERE c.current_agent = 'hostagent'
RETURN c
```

### Access full metadata:
```cypher
MATCH (c:Conversation {id: 'xyz'})
RETURN c.metadata_json as metadata_json
```

Then parse in Python:
```python
import json
full_metadata = json.loads(result['metadata_json'])
```

## Production Readiness

✅ All tests passing
✅ Neo4j constraints satisfied
✅ Backward compatible (no breaking changes to API)
✅ Diagnostic tools updated
✅ Database reset tested

## Next Steps

The metadata storage fix is complete. To deploy:

1. Reset Neo4j database (optional - clears old STRING metadata):
   ```bash
   python neo4j_reset_auto.py
   ```

2. Test with actual WebSocket connections to verify end-to-end

3. Monitor `diagnose_sessions.py` to ensure conversations are properly separated by `django_session_id`

## Key Learning

**Neo4j Property Constraint:** Node properties must be primitive types. For complex data:
- Store queryable fields as separate properties
- Store full data as JSON string
- Parse JSON when retrieving complex data
