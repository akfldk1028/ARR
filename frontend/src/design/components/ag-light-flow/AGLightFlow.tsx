import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Background,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeChange,
  applyNodeChanges,
  useReactFlow,
  type NodeTypes,
} from '@xyflow/react';
import AGLightNode from './agentnode';
import AGLightEdge from './edge';
import type {
  AGLightEdge as AGLightEdgeType,
  AGLightMessage,
  AGLightNode as AGLightNodeType,
  AGLightReview,
  AGLightRunStatus,
} from './types';

type ViewMode = 'pattern' | 'execution';

interface Props {
  reviews: AGLightReview[];
  messages?: AGLightMessage[];
  status?: AGLightRunStatus;
  viewMode?: ViewMode;
}

const nodeTypes: NodeTypes = {
  agLightNode: AGLightNode,
};

const edgeTypes = {
  agLightEdge: AGLightEdge,
};

const getStatusTone = (agent: string): AGLightNodeType['data']['tone'] => {
  if (agent.includes('law')) return 'law';
  if (agent.includes('parking')) return 'parking';
  if (agent.includes('sunlight')) return 'sunlight';
  if (agent.includes('datum')) return 'datum';
  if (agent.includes('critic')) return 'critic';
  return 'hub';
};

const createReviewNode = (
  review: AGLightReview,
  position: { x: number; y: number },
  isProcessing: boolean
): AGLightNodeType => ({
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
    review,
  },
});

const createLayout = (
  reviews: AGLightReview[],
  messages: AGLightMessage[] | undefined,
  status: AGLightRunStatus,
  viewMode: ViewMode
) => {
  const nodes: AGLightNodeType[] = [];
  const edges: AGLightEdgeType[] = [];
  const isProcessing = status === 'active' || status === 'awaiting_input';

  nodes.push({
    id: 'user',
    type: 'agLightNode',
    position: { x: 24, y: 124 },
    data: {
      type: 'user',
      label: 'User',
      agentType: 'user',
      description: 'Human user',
      isActive: true,
      status: null,
      reason: null,
      draggable: !isProcessing,
      tone: 'hub',
    },
  });

  const hubX = 182;
  const hubY = 124;
  nodes.push({
    id: 'design_orchestrator',
    type: 'agLightNode',
    position: { x: hubX, y: hubY },
    data: {
      type: 'agent',
      label: 'orchestrator',
      agentType: 'orchestrator',
      description: 'Routes review outcomes',
      isActive: true,
      status: status,
      reason: null,
      draggable: !isProcessing,
      tone: 'hub',
    },
  });

  const spread = Math.max(reviews.length - 1, 1);
  reviews.forEach((review, index) => {
    const angle = reviews.length === 1 ? 0 : (-Math.PI / 3) + (index * (Math.PI * 2 / 3)) / spread;
    const radius = 188;
    const x = hubX + 190 + radius * Math.cos(angle);
    const y = hubY + 28 + radius * Math.sin(angle);
    nodes.push(createReviewNode(review, { x, y }, isProcessing));

    const active = review.status === 'pass' || review.status === 'check';
    edges.push({
      id: `orch-${review.agent}`,
      source: 'design_orchestrator',
      target: review.agent,
      type: 'agLightEdge',
      animated: active,
      data: {
        label: active ? review.label : '',
        messages: messages?.filter(msg => msg.from_agent === review.agent || msg.to_agent === review.agent) || [],
        routingType: 'primary',
      },
      style: {
        stroke: active ? '#22c55e' : '#6b7280',
        strokeWidth: active ? 2 : 1,
        opacity: active ? 1 : 0.45,
      },
    });
    edges.push({
      id: `${review.agent}-return`,
      source: review.agent,
      target: 'design_orchestrator',
      type: 'agLightEdge',
      data: {
        label: '',
        messages: messages?.filter(msg => msg.from_agent === review.agent || msg.to_agent === review.agent) || [],
        routingType: 'secondary',
      },
      style: {
        stroke: active ? '#f59e0b' : '#6b7280',
        strokeWidth: 1,
        opacity: active ? 0.75 : 0.2,
      },
    });
  });

  edges.push({
    id: 'user-orch',
    source: 'user',
    target: 'design_orchestrator',
    type: 'agLightEdge',
    animated: true,
    data: {
      label: 'start',
      messages: messages || [],
      routingType: 'primary',
    },
    style: {
      stroke: '#2563eb',
      strokeWidth: 2,
    },
  });

  nodes.push({
    id: 'design_critic',
    type: 'agLightNode',
    position: { x: 700, y: 124 },
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
    },
  });

  edges.push({
    id: 'orch-critic',
    source: 'design_orchestrator',
    target: 'design_critic',
    type: 'agLightEdge',
    animated: true,
    data: {
      label: 'review',
      messages: messages || [],
      routingType: 'primary',
    },
    style: {
      stroke: '#a78bfa',
      strokeWidth: 2,
    },
  });

  if (viewMode === 'execution' && messages?.length) {
    const lastMessage = messages[messages.length - 1];
    nodes.push({
      id: 'end',
      type: 'agLightNode',
      position: { x: 852, y: 124 },
      data: {
        type: 'end',
        label: 'End',
        agentType: '',
        description: '',
        isActive: false,
        status,
        reason: lastMessage?.message || '',
        draggable: false,
        tone: 'hub',
      },
    });
    edges.push({
      id: 'critic-end',
      source: 'design_critic',
      target: 'end',
      type: 'agLightEdge',
      animated: false,
      data: {
        label: 'done',
        messages: messages || [],
        routingType: 'primary',
      },
      style: {
        stroke: status === 'complete' ? '#22c55e' : '#ef4444',
        strokeWidth: 2,
      },
    });
  }

  return { nodes, edges };
};

function AGLightFlowInner({ reviews, messages, status = 'idle', viewMode = 'pattern' }: Props) {
  const { fitView } = useReactFlow();
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((current) => applyNodeChanges(changes as NodeChange[], current as Node[]) as Node[]);
  }, []);

  useEffect(() => {
    const layout = createLayout(reviews, messages, status, viewMode);
    setNodes(layout.nodes);
    setEdges(layout.edges);
    const timeout = window.setTimeout(() => {
      fitView({ padding: 0.2, duration: 200 });
    }, 50);
    return () => window.clearTimeout(timeout);
  }, [reviews, messages, status, viewMode, fitView]);

  return (
    <div
      data-testid="ag-light-react-flow"
      style={{
        height: 176,
        borderRadius: 8,
        border: '1px solid rgba(94,234,212,0.16)',
        background: '#020617',
        overflow: 'hidden',
        marginTop: 8,
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
        minZoom={0.5}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        panOnDrag={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(148,163,184,0.16)" gap={18} />
        <MiniMap zoomable pannable maskColor="rgba(2,6,23,0.65)" />
      </ReactFlow>
    </div>
  );
}

export default function AGLightFlow(props: Props) {
  return (
    <ReactFlowProvider>
      <AGLightFlowInner {...props} />
    </ReactFlowProvider>
  );
}
