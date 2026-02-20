"""
Neo4j Provenance Tracker - Phase 2-2
W3C PROV Standard + PROV-AGENT Framework
Implements Decision, Evidence, Artifact tracking with DERIVED_FROM relationships
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
import json

from graph_db.services import Neo4jService

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """Tracks provenance of decisions, evidence, and artifacts in the multi-agent system"""

    def __init__(self, service: Neo4jService):
        self.service = service

    # ===== Decision Management =====

    def create_decision(
        self,
        turn_id: str,
        agent_slug: str,
        decision_type: str,
        description: str,
        rationale: str = None,
        confidence: float = None,
        metadata: Dict[str, Any] = None,
        execution_id: str = None
    ) -> str:
        """Create a decision node made by an agent during a turn

        Args:
            turn_id: ID of the turn this decision belongs to
            agent_slug: Slug of the agent making the decision
            decision_type: Type of decision being made
            description: Description of the decision
            rationale: Explanation for why this decision was made
            confidence: Confidence score (0.0 to 1.0)
            metadata: Additional metadata as dict
            execution_id: Optional AgentExecution ID that made this decision

        Returns:
            decision_id: UUID of the created decision
        """
        decision_id = str(uuid4())

        # If execution_id provided, link Decision to AgentExecution
        if execution_id:
            query = """
            MATCH (t:Turn {id: $turn_id})
            MATCH (a:Agent {slug: $agent_slug})
            MATCH (ae:AgentExecution {id: $execution_id})
            CREATE (d:Decision {
                id: $decision_id,
                turn_id: $turn_id,
                agent_slug: $agent_slug,
                decision_type: $decision_type,
                description: $description,
                rationale: $rationale,
                confidence: $confidence,
                created_at: datetime($created_at),
                metadata: $metadata
            })
            CREATE (t)-[:HAS_DECISION]->(d)
            CREATE (d)-[:MADE_BY]->(a)
            CREATE (ae)-[:MADE_DECISION]->(d)
            RETURN d.id as decision_id
            """
            params = {
                'decision_id': decision_id,
                'turn_id': turn_id,
                'agent_slug': agent_slug,
                'execution_id': execution_id,
                'decision_type': decision_type,
                'description': description,
                'rationale': rationale,
                'confidence': confidence,
                'created_at': datetime.utcnow().isoformat(),
                'metadata': json.dumps(metadata or {})
            }
        else:
            # Legacy mode: no execution_id provided
            query = """
            MATCH (t:Turn {id: $turn_id})
            MATCH (a:Agent {slug: $agent_slug})
            CREATE (d:Decision {
                id: $decision_id,
                turn_id: $turn_id,
                agent_slug: $agent_slug,
                decision_type: $decision_type,
                description: $description,
                rationale: $rationale,
                confidence: $confidence,
                created_at: datetime($created_at),
                metadata: $metadata
            })
            CREATE (t)-[:HAS_DECISION]->(d)
            CREATE (d)-[:MADE_BY]->(a)
            RETURN d.id as decision_id
            """
            params = {
                'decision_id': decision_id,
                'turn_id': turn_id,
                'agent_slug': agent_slug,
                'decision_type': decision_type,
                'description': description,
                'rationale': rationale,
                'confidence': confidence,
                'created_at': datetime.utcnow().isoformat(),
                'metadata': json.dumps(metadata or {})
            }

        self.service.execute_write_query(query, params)
        logger.info(f"Created decision {decision_id} by {agent_slug}: {decision_type}" +
                   (f" (execution: {execution_id})" if execution_id else ""))
        return decision_id

    # ===== Evidence Management =====

    def create_evidence(
        self,
        evidence_type: str,
        content: str,
        source: str,
        confidence_score: float = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create an evidence node"""
        evidence_id = str(uuid4())
        query = """
        CREATE (e:Evidence {
            id: $evidence_id,
            evidence_type: $evidence_type,
            content: $content,
            source: $source,
            confidence_score: $confidence_score,
            created_at: datetime($created_at),
            metadata: $metadata
        })
        RETURN e.id as evidence_id
        """

        params = {
            'evidence_id': evidence_id,
            'evidence_type': evidence_type,
            'content': content,
            'source': source,
            'confidence_score': confidence_score,
            'created_at': datetime.utcnow().isoformat(),
            'metadata': json.dumps(metadata or {})
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Created evidence {evidence_id}: {evidence_type} from {source}")
        return evidence_id

    def link_evidence_to_decision(
        self,
        decision_id: str,
        evidence_id: str,
        weight: float = 1.0
    ):
        """Link evidence to a decision with weight"""
        query = """
        MATCH (d:Decision {id: $decision_id})
        MATCH (e:Evidence {id: $evidence_id})
        CREATE (d)-[s:SUPPORTED_BY {weight: $weight}]->(e)
        RETURN d, e
        """

        params = {
            'decision_id': decision_id,
            'evidence_id': evidence_id,
            'weight': weight
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Linked evidence {evidence_id} to decision {decision_id} (weight: {weight})")

    # ===== Artifact Management =====

    def create_artifact(
        self,
        task_id: str,
        artifact_type: str,
        content: str,
        format: str = "text",
        metadata: Dict[str, Any] = None,
        execution_id: str = None
    ) -> str:
        """Create an artifact produced by a task

        Args:
            task_id: ID of the task that produced this artifact
            artifact_type: Type of artifact
            content: Artifact content
            format: Format of content (text, json, etc.)
            metadata: Additional metadata as dict
            execution_id: Optional AgentExecution ID that produced this artifact

        Returns:
            artifact_id: UUID of the created artifact
        """
        artifact_id = str(uuid4())

        # If execution_id provided, link Artifact to AgentExecution
        if execution_id:
            query = """
            MATCH (t:Task {id: $task_id})
            MATCH (ae:AgentExecution {id: $execution_id})
            CREATE (a:Artifact {
                id: $artifact_id,
                task_id: $task_id,
                artifact_type: $artifact_type,
                content: $content,
                format: $format,
                created_at: datetime($created_at),
                metadata: $metadata
            })
            CREATE (t)-[:PRODUCED]->(a)
            CREATE (ae)-[:PRODUCED]->(a)
            RETURN a.id as artifact_id
            """
            params = {
                'artifact_id': artifact_id,
                'task_id': task_id,
                'execution_id': execution_id,
                'artifact_type': artifact_type,
                'content': content,
                'format': format,
                'created_at': datetime.utcnow().isoformat(),
                'metadata': json.dumps(metadata or {})
            }
        else:
            # Legacy mode: no execution_id provided
            query = """
            MATCH (t:Task {id: $task_id})
            CREATE (a:Artifact {
                id: $artifact_id,
                task_id: $task_id,
                artifact_type: $artifact_type,
                content: $content,
                format: $format,
                created_at: datetime($created_at),
                metadata: $metadata
            })
            CREATE (t)-[:PRODUCED]->(a)
            RETURN a.id as artifact_id
            """
            params = {
                'artifact_id': artifact_id,
                'task_id': task_id,
                'artifact_type': artifact_type,
                'content': content,
                'format': format,
                'created_at': datetime.utcnow().isoformat(),
                'metadata': json.dumps(metadata or {})
            }

        self.service.execute_write_query(query, params)
        logger.info(f"Created artifact {artifact_id}: {artifact_type} for task {task_id}" +
                   (f" (execution: {execution_id})" if execution_id else ""))
        return artifact_id

    def link_artifact_derivation(
        self,
        derived_artifact_id: str,
        source_artifact_id: str,
        transformation: str = None
    ):
        """Create DERIVED_FROM relationship between artifacts"""
        query = """
        MATCH (derived:Artifact {id: $derived_artifact_id})
        MATCH (source:Artifact {id: $source_artifact_id})
        CREATE (derived)-[d:DERIVED_FROM {
            transformation: $transformation,
            created_at: datetime($created_at)
        }]->(source)
        RETURN derived, source
        """

        params = {
            'derived_artifact_id': derived_artifact_id,
            'source_artifact_id': source_artifact_id,
            'transformation': transformation,
            'created_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Linked artifact {derived_artifact_id} derived from {source_artifact_id}")

    def link_decision_to_artifact(
        self,
        decision_id: str,
        artifact_id: str
    ):
        """Link a decision to an artifact it produced"""
        query = """
        MATCH (d:Decision {id: $decision_id})
        MATCH (a:Artifact {id: $artifact_id})
        CREATE (d)-[:RESULTED_IN]->(a)
        RETURN d, a
        """

        params = {
            'decision_id': decision_id,
            'artifact_id': artifact_id
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Linked decision {decision_id} to artifact {artifact_id}")

    # ===== Provenance Queries =====

    def get_decision_provenance(self, decision_id: str) -> Dict[str, Any]:
        """Get complete provenance chain for a decision"""
        query = """
        MATCH (d:Decision {id: $decision_id})
        OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Evidence)
        OPTIONAL MATCH (d)-[:RESULTED_IN]->(a:Artifact)
        OPTIONAL MATCH (d)-[:MADE_BY]->(agent:Agent)
        RETURN d as decision,
               collect(DISTINCT e) as supporting_evidence,
               collect(DISTINCT a) as resulting_artifacts,
               agent
        """

        params = {'decision_id': decision_id}
        result = self.service.execute_query(query, params)

        if result:
            return result[0]
        return {}

    def get_artifact_lineage(self, artifact_id: str) -> List[Dict]:
        """Get the complete lineage of an artifact (all ancestors)"""
        query = """
        MATCH path = (artifact:Artifact {id: $artifact_id})-[:DERIVED_FROM*0..]->(ancestor:Artifact)
        WITH artifact, ancestor, path
        ORDER BY length(path) DESC
        RETURN ancestor.id as artifact_id,
               ancestor.artifact_type as type,
               ancestor.created_at as created_at,
               length(path) as depth
        """

        params = {'artifact_id': artifact_id}
        result = self.service.execute_query(query, params)
        logger.info(f"Retrieved lineage for artifact {artifact_id}: {len(result)} ancestors")
        return result

    def get_decision_chain(self, turn_id: str) -> List[Dict]:
        """Get all decisions made during a turn with their evidence"""
        query = """
        MATCH (t:Turn {id: $turn_id})-[:HAS_DECISION]->(d:Decision)
        OPTIONAL MATCH (d)-[s:SUPPORTED_BY]->(e:Evidence)
        WITH d, collect({
            evidence_id: e.id,
            type: e.evidence_type,
            source: e.source,
            weight: s.weight
        }) as evidence
        RETURN d.id as decision_id,
               d.decision_type as type,
               d.description as description,
               d.confidence as confidence,
               d.rationale as rationale,
               evidence
        ORDER BY d.created_at
        """

        params = {'turn_id': turn_id}
        result = self.service.execute_query(query, params)
        logger.info(f"Retrieved {len(result)} decisions for turn {turn_id}")
        return result

    def trace_artifact_to_decision(self, artifact_id: str) -> List[Dict]:
        """Trace an artifact back to the decisions that led to it"""
        query = """
        MATCH (artifact:Artifact {id: $artifact_id})
        MATCH (artifact)<-[:PRODUCED]-(task:Task)
        MATCH (task)<-[:GENERATED_TASK]-(turn:Turn)
        MATCH (turn)-[:HAS_DECISION]->(decision:Decision)
        OPTIONAL MATCH (decision)-[:RESULTED_IN]->(artifact)
        RETURN decision.id as decision_id,
               decision.decision_type as type,
               decision.description as description,
               decision.agent_slug as agent,
               EXISTS((decision)-[:RESULTED_IN]->(artifact)) as directly_resulted
        """

        params = {'artifact_id': artifact_id}
        result = self.service.execute_query(query, params)
        logger.info(f"Traced artifact {artifact_id} to {len(result)} decisions")
        return result

    def get_evidence_impact(self, evidence_id: str) -> Dict[str, Any]:
        """Analyze the impact of a piece of evidence on decisions"""
        query = """
        MATCH (e:Evidence {id: $evidence_id})<-[s:SUPPORTED_BY]-(d:Decision)
        RETURN e.evidence_type as evidence_type,
               e.source as source,
               count(d) as decisions_influenced,
               avg(s.weight) as avg_weight,
               collect({
                   decision_id: d.id,
                   type: d.decision_type,
                   confidence: d.confidence,
                   weight: s.weight
               }) as decisions
        """

        params = {'evidence_id': evidence_id}
        result = self.service.execute_query(query, params)

        if result:
            return result[0]
        return {}

    def find_conflicting_decisions(self, turn_id: str) -> List[Dict]:
        """Find decisions in a turn that might conflict (same type, different outcomes)"""
        query = """
        MATCH (t:Turn {id: $turn_id})-[:HAS_DECISION]->(d1:Decision)
        MATCH (t)-[:HAS_DECISION]->(d2:Decision)
        WHERE d1.decision_type = d2.decision_type
          AND d1.id < d2.id
          AND d1.description <> d2.description
        RETURN d1.id as decision1_id,
               d2.id as decision2_id,
               d1.decision_type as type,
               d1.description as description1,
               d2.description as description2,
               d1.confidence as confidence1,
               d2.confidence as confidence2
        """

        params = {'turn_id': turn_id}
        result = self.service.execute_query(query, params)

        if result:
            logger.warning(f"Found {len(result)} conflicting decisions in turn {turn_id}")

        return result
