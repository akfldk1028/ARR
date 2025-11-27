"""
Comprehensive test for 36 search query
Tests:
1. Results properly distinguish between , , 
2. No duplicate results
3. Results show diversity across different law types
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.agent_manager import AgentManager
from graph_db.services.neo4j_service import Neo4jService
import json
from collections import defaultdict

def analyze_search_results(result):
    """Analyze search results for type distribution, duplicates, and diversity"""
    print("\n" + "="*80)
    print("SEARCH RESULT ANALYSIS FOR: 36")
    print("="*80)

    # Extract all HANG results from all phases
    all_hang_results = []
    hang_by_phase = defaultdict(list)

    # Phase 1 - Domain agent results
    if 'domain_results' in result:
        for domain_name, domain_data in result['domain_results'].items():
            if 'hang_results' in domain_data:
                for hang in domain_data['hang_results']:
                    hang['source_phase'] = 'Phase 1'
                    hang['source_domain'] = domain_name
                    all_hang_results.append(hang)
                    hang_by_phase['Phase 1'].append(hang)

    # Phase 2 - A2A collaboration results
    if 'a2a_results' in result:
        for domain_name, a2a_data in result['a2a_results'].items():
            if 'shared_hang' in a2a_data:
                for hang in a2a_data['shared_hang']:
                    hang['source_phase'] = 'Phase 2'
                    hang['source_domain'] = domain_name
                    all_hang_results.append(hang)
                    hang_by_phase['Phase 2'].append(hang)

    # Phase 3 - Synthesized results
    if 'synthesized_results' in result:
        if 'hang_results' in result['synthesized_results']:
            for hang in result['synthesized_results']['hang_results']:
                hang['source_phase'] = 'Phase 3'
                hang['source_domain'] = 'Synthesized'
                all_hang_results.append(hang)
                hang_by_phase['Phase 3'].append(hang)

    print(f"\nTOTAL HANG RESULTS FOUND: {len(all_hang_results)}")
    print(f"   - Phase 1: {len(hang_by_phase['Phase 1'])}")
    print(f"   - Phase 2: {len(hang_by_phase['Phase 2'])}")
    print(f"   - Phase 3: {len(hang_by_phase['Phase 3'])}")

    # Analysis 1: Check for LAW type distribution
    print("\n" + "="*80)
    print("1⃣  LAW TYPE DISTRIBUTION ANALYSIS")
    print("="*80)

    law_types = defaultdict(int)
    law_type_by_hang = {}

    for hang in all_hang_results:
        law_name = hang.get('law_name', 'Unknown')
        law_type = hang.get('law_type', 'Unknown')
        hang_id = hang.get('hang_id', 'Unknown')

        law_types[law_type] += 1

        if hang_id not in law_type_by_hang:
            law_type_by_hang[hang_id] = {
                'law_name': law_name,
                'law_type': law_type,
                'jo_number': hang.get('jo_number', 'Unknown'),
                'hang_number': hang.get('hang_number', 'Unknown')
            }

    print(f"\n Law Type Counts:")
    for law_type, count in sorted(law_types.items()):
        print(f"   - {law_type}: {count}")

    # Check if all are same type (problem indicator)
    unique_types = set(law_types.keys())
    if len(unique_types) == 1 and '' in unique_types:
        print("\n  WARNING: All results are '' - no diversity!")
    elif len(unique_types) == 1:
        print(f"\n  WARNING: All results are '{list(unique_types)[0]}' - no diversity!")
    else:
        print(f"\n GOOD: Found {len(unique_types)} different law types")

    # Analysis 2: Check for duplicates
    print("\n" + "="*80)
    print("2⃣  DUPLICATE DETECTION ANALYSIS")
    print("="*80)

    hang_occurrences = defaultdict(list)

    for idx, hang in enumerate(all_hang_results):
        hang_id = hang.get('hang_id', f'unknown_{idx}')
        hang_occurrences[hang_id].append({
            'phase': hang.get('source_phase', 'Unknown'),
            'domain': hang.get('source_domain', 'Unknown'),
            'law_name': hang.get('law_name', 'Unknown'),
            'law_type': hang.get('law_type', 'Unknown'),
            'jo_number': hang.get('jo_number', 'Unknown'),
            'hang_number': hang.get('hang_number', 'Unknown')
        })

    duplicates = {k: v for k, v in hang_occurrences.items() if len(v) > 1}

    if duplicates:
        print(f"\n  FOUND {len(duplicates)} DUPLICATE HANG IDs:")
        for hang_id, occurrences in list(duplicates.items())[:5]:  # Show first 5
            print(f"\n    {hang_id} (appears {len(occurrences)} times):")
            for occ in occurrences:
                print(f"      - Phase: {occ['phase']}, Domain: {occ['domain']}")
                print(f"        {occ['law_name']} ({occ['law_type']}) - {occ['jo_number']} {occ['hang_number']}")
        if len(duplicates) > 5:
            print(f"\n   ... and {len(duplicates) - 5} more duplicates")
    else:
        print("\n NO DUPLICATES: All HANG IDs are unique")

    # Analysis 3: Diversity across law types
    print("\n" + "="*80)
    print("3⃣  DIVERSITY ANALYSIS")
    print("="*80)

    # Group by law name and type
    law_groups = defaultdict(list)

    for hang in all_hang_results:
        key = f"{hang.get('law_name', 'Unknown')} ({hang.get('law_type', 'Unknown')})"
        law_groups[key].append(hang)

    print(f"\n Found {len(law_groups)} unique law documents:")
    for law_key, hangs in sorted(law_groups.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n   {law_key}:")
        print(f"    {len(hangs)} HANG results")

        # Show sample of jo numbers
        jo_numbers = set()
        for hang in hangs:
            jo_number = hang.get('jo_number', 'Unknown')
            if jo_number and jo_number != 'Unknown':
                jo_numbers.add(jo_number)

        if jo_numbers:
            jo_list = sorted(list(jo_numbers), key=lambda x: int(x) if str(x).isdigit() else 999)
            if len(jo_list) <= 5:
                print(f"       numbers: {', '.join(map(str, jo_list))}")
            else:
                print(f"       numbers: {', '.join(map(str, jo_list[:5]))}... ({len(jo_list)} total)")

    # Check diversity quality
    if len(law_groups) < 3:
        print(f"\n  LOW DIVERSITY: Only {len(law_groups)} different law documents")
    else:
        print(f"\n GOOD DIVERSITY: {len(law_groups)} different law documents")

    # Analysis 4: Detailed sample results
    print("\n" + "="*80)
    print("4⃣  SAMPLE RESULTS (First 10)")
    print("="*80)

    for idx, hang in enumerate(all_hang_results[:10]):
        print(f"\n{idx+1}. [{hang.get('source_phase', 'Unknown')}] {hang.get('law_name', 'Unknown')}")
        print(f"   Type: {hang.get('law_type', 'Unknown')}")
        print(f"   Location: {hang.get('jo_number', 'Unknown')} {hang.get('hang_number', 'Unknown')}")
        print(f"   HANG ID: {hang.get('hang_id', 'Unknown')}")
        print(f"   Domain: {hang.get('source_domain', 'Unknown')}")

        content = hang.get('content', '')
        if content:
            content_preview = content[:100] + "..." if len(content) > 100 else content
            print(f"   Content: {content_preview}")

    # Return analysis summary
    return {
        'total_results': len(all_hang_results),
        'unique_hang_count': len(hang_occurrences),
        'duplicate_count': len(duplicates),
        'law_types': dict(law_types),
        'unique_law_documents': len(law_groups),
        'has_diversity': len(unique_types) > 1,
        'all_same_type': len(unique_types) == 1,
        'law_groups': {k: len(v) for k, v in law_groups.items()}
    }


def verify_neo4j_law_types():
    """Verify that Neo4j database has properly typed LAW nodes"""
    print("\n" + "="*80)
    print("VERIFYING NEO4J LAW NODE TYPES")
    print("="*80)

    neo4j = Neo4jService()
    neo4j.connect()

    # Query all LAW nodes with type
    query = """
    MATCH (law:LAW)
    RETURN law.name as name, law.type as type, law.law_id as law_id
    ORDER BY law.name
    """

    results = neo4j.execute_query(query)

    print(f"\n Total LAW nodes: {len(results)}")

    type_counts = defaultdict(int)
    for record in results:
        law_type = record.get('type', 'Unknown')
        type_counts[law_type] += 1

    print(f"\n LAW Type Distribution in Database:")
    for law_type, count in sorted(type_counts.items()):
        print(f"   - {law_type}: {count}")

    # Show sample laws
    print(f"\n Sample LAW Nodes:")
    for record in results[:10]:
        print(f"   - {record['name']} ({record.get('type', 'Unknown')})")

    # Check for 36 specifically
    print(f"\n Checking for laws with 36:")
    query_36jo = """
    MATCH (law:LAW)-[:HAS_JO]->(jo:JO {jo_number: "36"})
    RETURN DISTINCT law.name as name, law.type as type, law.law_id as law_id
    ORDER BY law.name
    """

    results_36jo = neo4j.execute_query(query_36jo)
    print(f"\n Found {len(results_36jo)} laws with 36:")
    for record in results_36jo:
        print(f"   - {record['name']} ({record.get('type', 'Unknown')})")

    neo4j.close()

    return {
        'total_laws': len(results),
        'type_distribution': dict(type_counts),
        'laws_with_36jo': len(results_36jo)
    }


def main():
    """Main test function"""
    print("\n" + "="*80)
    print("  COMPREHENSIVE 36 SEARCH TEST")
    print("="*80)

    # Step 1: Verify Neo4j database
    db_verification = verify_neo4j_law_types()

    # Step 2: Run search
    print("\n\n" + "="*80)
    print("EXECUTING SEARCH: 36")
    print("="*80)

    manager = AgentManager()

    try:
        result = manager.search(
            query="36",
            session_id="test_36jo_comprehensive"
        )

        # Step 3: Analyze results
        analysis = analyze_search_results(result)

        # Step 4: Final summary
        print("\n\n" + "="*80)
        print(" FINAL SUMMARY")
        print("="*80)

        print(f"\nDatabase Status:")
        print(f"   - Total LAW nodes: {db_verification['total_laws']}")
        print(f"   - LAW types in DB: {db_verification['type_distribution']}")
        print(f"   - Laws with 36: {db_verification['laws_with_36jo']}")

        print(f"\nSearch Results:")
        print(f"   - Total HANG results: {analysis['total_results']}")
        print(f"   - Unique HANG results: {analysis['unique_hang_count']}")
        print(f"   - Duplicate HANGs: {analysis['duplicate_count']}")
        print(f"   - Unique law documents: {analysis['unique_law_documents']}")

        print(f"\nType Distribution:")
        for law_type, count in sorted(analysis['law_types'].items()):
            print(f"   - {law_type}: {count}")

        print(f"\nQuality Checks:")
        print(f"   - Has type diversity: {'YES' if analysis['has_diversity'] else 'NO'}")
        print(f"   - All same type: {'YES (WARNING)' if analysis['all_same_type'] else 'NO'}")
        print(f"   - Has duplicates: {'YES (WARNING)' if analysis['duplicate_count'] > 0 else 'NO'}")

        # Recommendations
        print(f"\nRecommendations:")

        issues = []
        if analysis['all_same_type']:
            issues.append("All results are the same type - need to fix search to include // diversity")
        if analysis['duplicate_count'] > 0:
            issues.append(f"Found {analysis['duplicate_count']} duplicates - need deduplication in search algorithm")
        if analysis['unique_law_documents'] < 3:
            issues.append("Low diversity in law documents - consider expanding search scope")

        if issues:
            for idx, issue in enumerate(issues, 1):
                print(f"   {idx}. {issue}")
        else:
            print("   No major issues found!")

        # Save results to file
        output_file = backend_dir / "test_36jo_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'database_verification': db_verification,
                'search_analysis': analysis,
                'full_results': result
            }, f, ensure_ascii=False, indent=2)

        print(f"\nFull results saved to: {output_file}")

    except Exception as e:
        print(f"\nERROR during search: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
