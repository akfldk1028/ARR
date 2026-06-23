import type { AGLightFlowSettings } from './AGLightFlowToolbar';
import {
  createEdge,
  createEndNode,
  createUserNode,
  type AGLightEdge,
  type AGLightMessage,
  type AGLightNode,
  type AGLightNodeData,
  type AGLightReview,
  type AGLightRunStatus,
} from './types';

export type AGLightViewMode = 'pattern' | 'execution';

interface LayoutInput {
  reviews: AGLightReview[];
  messages?: AGLightMessage[];
  status: AGLightRunStatus;
  viewMode: AGLightViewMode;
  settings: AGLightFlowSettings;
  isFullscreen?: boolean;
}

const HUB_ID = 'design_orchestrator';

const getStatusTone = (agent: string): AGLightNodeData['tone'] => {
  if (agent.includes('law')) return 'law';
  if (agent.includes('parking')) return 'parking';
  if (agent.includes('sunlight')) return 'sunlight';
  if (agent.includes('datum')) return 'datum';
  if (agent.includes('critic')) return 'critic';
  return 'hub';
};

const getLastAgentMessage = (messages: AGLightMessage[] | undefined, agent: string) => {
  const message = messages
    ?.slice()
    .reverse()
    .find((item) => item.from_agent === agent || item.to_agent === agent);
  if (!message?.message) return undefined;
  return message.message.length > 96 ? `${message.message.slice(0, 93)}...` : message.message;
};

const messagesForAgent = (messages: AGLightMessage[] | undefined, agent: string) =>
  messages?.filter((msg) => msg.from_agent === agent || msg.to_agent === agent) || [];

const createHubNode = (
  position: { x: number; y: number },
  status: AGLightRunStatus,
  isProcessing: boolean,
  compact: boolean
): AGLightNode => ({
  id: HUB_ID,
  type: 'agLightNode',
  position,
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

const createReviewNode = (
  review: AGLightReview,
  position: { x: number; y: number },
  isProcessing: boolean,
  compact: boolean,
  messages?: AGLightMessage[]
): AGLightNode => ({
  id: review.agent,
  type: 'agLightNode',
  position,
  data: {
    type: 'agent',
    label: review.label,
    agentType: review.agent,
    description: review.summary,
    isActive: review.status === 'pass' || review.status === 'check',
    status: null,
    reason: review.detail,
    draggable: !isProcessing,
    tone: getStatusTone(review.agent),
    lastMessage: getLastAgentMessage(messages, review.agent),
    review,
    compact,
  },
});

const createDesignCriticNode = (
  position: { x: number; y: number },
  isProcessing: boolean,
  compact: boolean,
  messages?: AGLightMessage[]
): AGLightNode => ({
  id: 'design_critic',
  type: 'agLightNode',
  position,
  data: {
    type: 'agent',
    label: 'design critic',
    agentType: 'design_critic',
    description: 'Checks final shape',
    isActive: true,
    status: null,
    reason: null,
    draggable: !isProcessing,
    tone: 'critic',
    lastMessage: getLastAgentMessage(messages, 'design_critic'),
    compact,
  },
});

const getReviewPositions = (
  reviews: AGLightReview[],
  direction: AGLightFlowSettings['direction'],
  compact: boolean
): Array<{ x: number; y: number }> => {
  if (!compact) {
    if (direction === 'TB') {
      const startX = 360 - ((reviews.length - 1) * 220) / 2;
      return reviews.map((_, index) => ({ x: startX + index * 220, y: 520 }));
    }
    const startY = 160 - ((reviews.length - 1) * 132) / 2;
    return reviews.map((_, index) => ({ x: 720, y: startY + index * 132 }));
  }

  if (direction === 'TB') {
    const startX = 8 - ((reviews.length - 1) * 144) / 2;
    return reviews.map((_, index) => ({ x: startX + index * 144, y: 268 }));
  }

  const startY = 12 - ((reviews.length - 1) * 74) / 2;
  return reviews.map((_, index) => ({ x: 300, y: startY + index * 74 }));
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
    user: direction === 'TB' ? { x: 8, y: 8 } : { x: 8, y: 12 },
    hub: direction === 'TB' ? { x: 8, y: 136 } : { x: 154, y: 12 },
    critic: direction === 'TB'
      ? { x: 8 + reviewCount * 144, y: 268 }
      : { x: 300, y: 12 + Math.max(reviewCount, 1) * 74 },
    end: direction === 'TB' ? { x: 8, y: 392 } : { x: 446, y: 12 },
  };
};

export function generateAGLightLayout({
  reviews,
  messages,
  status,
  viewMode,
  settings,
  isFullscreen = false,
}: LayoutInput): { nodes: AGLightNode[]; edges: AGLightEdge[] } {
  const nodes: AGLightNode[] = [];
  const edges: AGLightEdge[] = [];
  const isProcessing = status === 'active' || status === 'awaiting_input';
  const hasCriticReview = reviews.some((review) => review.agent === 'design_critic');
  const compact = !isFullscreen;
  const positions = getFixedPositions(reviews.length, settings.direction, compact);
  const agentPositions = getReviewPositions(reviews, settings.direction, compact);

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

  reviews.forEach((review, index) => {
    const active = review.status === 'pass' || review.status === 'check';
    nodes.push(createReviewNode(review, agentPositions[index], isProcessing, compact, messages));

    edges.push(createEdge(`orch-${review.agent}`, HUB_ID, review.agent, {
      animated: active,
      label: settings.showLabels && active ? review.label : '',
      messages: messagesForAgent(messages, review.agent),
      routingType: 'primary',
      stroke: active ? '#22c55e' : '#6b7280',
      strokeWidth: active ? 2 : 1,
      opacity: active ? 1 : 0.45,
    }));

    edges.push(createEdge(`${review.agent}-return`, review.agent, HUB_ID, {
      label: settings.showLabels && active ? 'report' : '',
      messages: messagesForAgent(messages, review.agent),
      routingType: 'secondary',
      stroke: active ? '#f59e0b' : '#6b7280',
      strokeWidth: 1,
      opacity: active ? 0.75 : 0.2,
    }));
  });

  if (!hasCriticReview) {
    nodes.push(createDesignCriticNode(positions.critic, isProcessing, compact, messages));
    edges.push(createEdge('orch-critic', HUB_ID, 'design_critic', {
      animated: true,
      label: settings.showLabels ? 'review' : '',
      messages,
      routingType: 'primary',
      stroke: '#a78bfa',
      strokeWidth: 2,
    }));
  }

  if (viewMode === 'execution' && messages?.length) {
    const lastMessage = messages[messages.length - 1];
    const endNode = createEndNode(positions.end, status);
    endNode.data.compact = compact;
    nodes.push(endNode);
    nodes[nodes.length - 1].data.reason = lastMessage?.message || '';
    edges.push(createEdge('critic-end', 'design_critic', 'end', {
      label: settings.showLabels ? 'done' : '',
      messages,
      routingType: 'primary',
      stroke: status === 'complete' ? '#22c55e' : '#ef4444',
      strokeWidth: 2,
    }));
  }

  return { nodes, edges };
}
