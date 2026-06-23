import React from 'react';
import { useViewport, type Edge, type Node } from '@xyflow/react';
import type { AGLightEdgeData } from './types';

interface Props {
  nodes: Node[];
  edges: Edge<AGLightEdgeData>[];
}

const getNodeBox = (node: Node) => ({
  x: node.position.x,
  y: node.position.y,
  width: Number(node.width || node.initialWidth || 128),
  height: Number(node.height || node.initialHeight || 86),
});

const getPath = (
  source: ReturnType<typeof getNodeBox>,
  target: ReturnType<typeof getNodeBox>,
  routingType?: AGLightEdgeData['routingType']
) => {
  const sourceX = source.x + source.width / 2;
  const sourceY = source.y + source.height;
  const targetX = target.x + target.width / 2;
  const targetY = target.y;

  if (routingType === 'secondary') {
    const offset = 42;
    const midY = sourceY + (targetY - sourceY) / 2;
    return `M ${sourceX} ${sourceY} L ${sourceX + offset} ${sourceY} L ${sourceX + offset} ${midY} L ${targetX - offset} ${midY} L ${targetX - offset} ${targetY} L ${targetX} ${targetY}`;
  }

  const midY = sourceY + (targetY - sourceY) / 2;
  return `M ${sourceX} ${sourceY} C ${sourceX} ${midY}, ${targetX} ${midY}, ${targetX} ${targetY}`;
};

export default function EdgeOverlay({ nodes, edges }: Props) {
  const viewport = useViewport();
  const nodeMap = React.useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  return (
    <svg
      aria-hidden="true"
      data-testid="ag-light-edge-overlay"
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 1,
        overflow: 'visible',
      }}
    >
      <g transform={`translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})`}>
        {edges.map((edge) => {
          const sourceNode = nodeMap.get(edge.source);
          const targetNode = nodeMap.get(edge.target);
          if (!sourceNode || !targetNode) return null;
          const routingType = edge.data?.routingType;
          const stroke = routingType === 'secondary'
            ? '#0891b2'
            : String(edge.style?.stroke || '#38bdf8');
          const strokeWidth = Number(edge.style?.strokeWidth || 1.5);
          const opacity = Number(edge.style?.opacity ?? 1);

          return (
            <path
              key={edge.id}
              data-testid="ag-light-edge-path"
              d={getPath(getNodeBox(sourceNode), getNodeBox(targetNode), routingType)}
              fill="none"
              stroke={stroke}
              strokeWidth={strokeWidth}
              strokeDasharray={edge.style?.strokeDasharray as string | undefined}
              opacity={Math.max(opacity, 0.34)}
              strokeLinecap="round"
            />
          );
        })}
      </g>
    </svg>
  );
}
