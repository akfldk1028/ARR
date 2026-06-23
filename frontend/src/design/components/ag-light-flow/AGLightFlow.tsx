import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Background,
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
import AGLightFlowToolbar, {
  DEFAULT_AG_LIGHT_SETTINGS,
  type AGLightFlowSettings,
} from './AGLightFlowToolbar';
import { generateAGLightLayout, type AGLightViewMode } from './layout-generator';
import type {
  AGLightMessage,
  AGLightReview,
  AGLightRunStatus,
} from './types';

interface Props {
  reviews: AGLightReview[];
  messages?: AGLightMessage[];
  status?: AGLightRunStatus;
  viewMode?: AGLightViewMode;
}

const nodeTypes: NodeTypes = {
  agLightNode: AGLightNode,
};

const edgeTypes = {
  agLightEdge: AGLightEdge,
};

function AGLightFlowInner({ reviews, messages, status = 'idle', viewMode = 'pattern' }: Props) {
  const { fitView, setViewport } = useReactFlow();
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [settings, setSettings] = useState<AGLightFlowSettings>(DEFAULT_AG_LIGHT_SETTINGS);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((current) => applyNodeChanges(changes as NodeChange[], current as Node[]) as Node[]);
  }, []);

  useEffect(() => {
    const layout = generateAGLightLayout({ reviews, messages, status, viewMode, settings, isFullscreen });
    setNodes(layout.nodes);
    setEdges(layout.edges);
    const timeout = window.setTimeout(() => {
      fitView({ padding: isFullscreen ? 0.08 : 0.2, duration: 200 });
    }, 50);
    return () => window.clearTimeout(timeout);
  }, [reviews, messages, status, viewMode, settings, isFullscreen, fitView]);

  useEffect(() => {
    if (!isFullscreen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsFullscreen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isFullscreen]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      if (isFullscreen) {
        setViewport({ x: 80, y: 190, zoom: 1.05 }, { duration: 200 });
      } else {
        fitView({ padding: 0.2, duration: 200 });
      }
    }, 120);
    return () => window.clearTimeout(timeout);
  }, [isFullscreen, fitView, setViewport]);

  return (
    <div
      data-testid="ag-light-react-flow"
      style={{
        position: isFullscreen ? 'fixed' : 'relative',
        inset: isFullscreen ? 16 : undefined,
        zIndex: isFullscreen ? 80 : undefined,
        height: isFullscreen ? 'calc(100vh - 32px)' : 280,
        borderRadius: 8,
        border: '1px solid rgba(94,234,212,0.16)',
        background: '#020617',
        overflow: 'hidden',
        marginTop: 8,
        boxShadow: isFullscreen ? '0 28px 80px rgba(0,0,0,0.45)' : undefined,
      }}
    >
      {isFullscreen && (
        <div
          aria-hidden="true"
          onClick={() => setIsFullscreen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: -1,
            background: 'rgba(0,0,0,0.52)',
          }}
        />
      )}
      <ReactFlow
        key={isFullscreen ? 'fullscreen' : 'panel'}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        defaultViewport={isFullscreen ? { x: 80, y: 190, zoom: 1.05 } : { x: 0, y: 0, zoom: 1 }}
        minZoom={0.3}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        zoomOnScroll={false}
        zoomOnPinch={false}
        panOnDrag={false}
        proOptions={{ hideAttribution: true }}
        fitView={!isFullscreen}
        fitViewOptions={{ padding: isFullscreen ? 0.08 : 0.2 }}
      >
        {settings.showGrid && <Background color="rgba(148,163,184,0.16)" gap={18} />}
        <AGLightFlowToolbar
          isFullscreen={isFullscreen}
          onToggleFullscreen={() => setIsFullscreen((value) => !value)}
          onResetView={() => fitView({ padding: 0.2, duration: 200 })}
          settings={settings}
          onSettingsChange={setSettings}
        />
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
