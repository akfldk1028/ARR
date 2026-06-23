import type { AGLightFlowSettings } from './AGLightFlowToolbar';
import { DESIGN_FLOW_AGENTS } from './agents';
import {
  createJsonAgentNode,
  getAgentMessageIds,
  getMessagesForAgent,
} from './agents/shared/review-adapter';
import {
  createEdge,
  createEndNode,
  createUserNode,
  type AGLightEdge,
  type AGLightMessage,
  type AGLightNode,
  type AGLightReview,
  type AGLightRunStatus,
  NODE_DIMENSIONS,
} from './types';

export type AGLightViewMode = 'pattern' | 'execution';

interface LayoutInput {
  reviews: AGLightReview[];
  messages?: AGLightMessage[];
  status: AGLightRunStatus;
  viewMode: AGLightViewMode;
  settings: AGLightFlowSettings;
  isFullscreen?: boolean;
  selectedAgentId?: string;
  onSelectAgent?: (agentId: string) => void;
}

const HUB_ID = 'design_orchestrator';

const createHubNode = (
  position: { x: number; y: number },
  status: AGLightRunStatus,
  isProcessing: boolean,
  compact: boolean
): AGLightNode => ({
  id: HUB_ID,
  type: 'agLightNode',
  position,
  width: compact ? NODE_DIMENSIONS.compact.width : NODE_DIMENSIONS.default.width,
  height: compact ? NODE_DIMENSIONS.compact.height : NODE_DIMENSIONS.default.height,
  initialWidth: compact ? NODE_DIMENSIONS.compact.width : NODE_DIMENSIONS.default.width,
  initialHeight: compact ? NODE_DIMENSIONS.compact.height : NODE_DIMENSIONS.default.height,
  style: {
    width: compact ? NODE_DIMENSIONS.compact.width : NODE_DIMENSIONS.default.width,
    height: compact ? NODE_DIMENSIONS.compact.height : NODE_DIMENSIONS.default.height,
  },
  data: {
    type: 'agent',
    label: HUB_ID,
    agentType: 'Selector/Handoff',
    description: '법규-설계 협업 라우터',
    isActive: true,
    status,
    reason: null,
    draggable: !isProcessing,
    tone: 'hub',
    compact,
  },
});

const getReviewPositions = (
  agentCount: number,
  direction: AGLightFlowSettings['direction'],
  compact: boolean
): Array<{ x: number; y: number }> => {
  if (!compact) {
    if (direction === 'TB') {
      const startX = 360 - ((agentCount - 1) * 220) / 2;
      return Array.from({ length: agentCount }, (_, index) => ({ x: startX + index * 220, y: 520 }));
    }
    const startY = 160 - ((agentCount - 1) * 132) / 2;
    return Array.from({ length: agentCount }, (_, index) => ({ x: 720, y: startY + index * 132 }));
  }

  if (direction === 'TB') {
    const startX = 8 - ((agentCount - 1) * 144) / 2;
    return Array.from({ length: agentCount }, (_, index) => ({ x: startX + index * 144, y: 268 }));
  }

  const startY = 12 - ((agentCount - 1) * 74) / 2;
  return Array.from({ length: agentCount }, (_, index) => ({ x: 300, y: Math.max(24, startY) + index * 82 }));
};

const getFixedPositions = (
  reviewCount: number,
  direction: AGLightFlowSettings['direction'],
  compact: boolean
) => {
  if (!compact) {
    return {
      user: direction === 'TB' ? { x: 360, y: 60 } : { x: 80, y: 160 },
      hub: direction === 'TB' ? { x: 360, y: 280 } : { x: 380, y: 160 },
      critic: direction === 'TB'
        ? { x: 360 + reviewCount * 220, y: 520 }
        : { x: 720, y: 160 + Math.max(reviewCount, 1) * 132 },
      end: direction === 'TB' ? { x: 360, y: 740 } : { x: 1040, y: 160 },
    };
  }

  return {
    user: direction === 'TB' ? { x: 8, y: 8 } : { x: 8, y: 154 },
    hub: direction === 'TB' ? { x: 8, y: 136 } : { x: 154, y: 154 },
    critic: direction === 'TB'
      ? { x: 8 + reviewCount * 144, y: 268 }
      : { x: 300, y: 12 + Math.max(reviewCount, 1) * 74 },
    end: direction === 'TB' ? { x: 8, y: 392 } : { x: 446, y: 154 },
  };
};

export function generateAGLightLayout({
  reviews,
  messages,
  status,
  viewMode,
  settings,
  isFullscreen = false,
  selectedAgentId,
  onSelectAgent,
}: LayoutInput): { nodes: AGLightNode[]; edges: AGLightEdge[] } {
  const nodes: AGLightNode[] = [];
  const edges: AGLightEdge[] = [];
  const isProcessing = status === 'active' || status === 'awaiting_input';
  const compact = !isFullscreen;
  const positions = getFixedPositions(DESIGN_FLOW_AGENTS.length, settings.direction, compact);
  const agentPositions = getReviewPositions(DESIGN_FLOW_AGENTS.length, settings.direction, compact);

  const userNode = createUserNode(positions.user, true, isProcessing);
  userNode.data.compact = compact;
  nodes.push(userNode);
  nodes.push(createHubNode(positions.hub, status, isProcessing, compact));

  edges.push(createEdge('user-orch', 'user', HUB_ID, {
    animated: true,
    label: settings.showLabels ? 'request' : '',
    messages,
    routingType: 'primary',
    stroke: '#2563eb',
    strokeWidth: 2,
  }));

  const flowTargets = [HUB_ID, ...DESIGN_FLOW_AGENTS.map((agent) => agent.participant.config.name)];

  DESIGN_FLOW_AGENTS.forEach((agent, index) => {
    nodes.push(createJsonAgentNode({
      participant: agent.participant,
      mapping: agent.mapping,
      reviews,
      messages,
      settings,
      position: agentPositions[index],
      isProcessing,
      compact,
      selectedAgentId,
      onSelectAgent,
    }));
  });

  DESIGN_FLOW_AGENTS.forEach((agent, index) => {
    const source = flowTargets[index];
    const target = flowTargets[index + 1];
    const active = reviews.some((review) =>
      agent.mapping.reviewAgentIds.includes(review.agent) &&
      (review.status === 'pass' || review.status === 'check')
    );

    edges.push(createEdge(`flow-${source}-${target}`, source, target, {
      animated: active,
      label: settings.showLabels && active ? (agent.mapping.fallbackLabel || agent.participant.label) : '',
      messages: getMessagesForAgent(messages, getAgentMessageIds(agent.participant, agent.mapping)),
      routingType: 'primary',
      stroke: active ? '#22c55e' : '#6b7280',
      strokeWidth: active ? 2 : 1,
      opacity: active ? 1 : 0.38,
    }));
  });

  if (viewMode === 'execution' && messages?.length) {
    const lastMessage = messages[messages.length - 1];
    const endNode = createEndNode(positions.end, status);
    endNode.data.compact = compact;
    nodes.push(endNode);
    nodes[nodes.length - 1].data.reason = lastMessage?.message || '';
    edges.push(createEdge('review-end', 'review_agent', 'end', {
      label: settings.showLabels ? 'done' : '',
      messages,
      routingType: 'primary',
      stroke: status === 'complete' ? '#22c55e' : '#ef4444',
      strokeWidth: 2,
    }));
  }

  return { nodes, edges };
}
