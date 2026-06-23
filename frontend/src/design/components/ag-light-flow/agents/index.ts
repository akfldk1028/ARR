import { lawGraphEvidenceMapping, lawGraphParticipant } from './law-graph-agent';
import { maasGeometryEvidenceMapping, maasGeometryParticipant } from './maas-geometry-agent';
import { parkingEvidenceMapping, parkingParticipant } from './parking-agent';
import { reviewEvidenceMapping, reviewParticipant } from './review-agent';
import type { AgentEvidenceMapping } from './shared/review-adapter';
import type { JsonModuleParticipant } from './shared/team-config';

export interface DesignFlowAgentModule {
  participant: JsonModuleParticipant;
  mapping: AgentEvidenceMapping;
}

export const DESIGN_FLOW_AGENTS: DesignFlowAgentModule[] = [
  {
    participant: lawGraphParticipant,
    mapping: lawGraphEvidenceMapping,
  },
  {
    participant: parkingParticipant,
    mapping: parkingEvidenceMapping,
  },
  {
    participant: maasGeometryParticipant,
    mapping: maasGeometryEvidenceMapping,
  },
  {
    participant: reviewParticipant,
    mapping: reviewEvidenceMapping,
  },
];
