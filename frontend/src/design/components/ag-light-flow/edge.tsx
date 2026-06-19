import React from 'react';
import {
  EdgeLabelRenderer,
  type EdgeProps,
  getSmoothStepPath,
} from '@xyflow/react';
import type { AGLightEdgeData } from './types';

const EDGE_OFFSET = 140;

interface Props extends Omit<EdgeProps, 'data'> {
  data: AGLightEdgeData;
}

export function AGLightEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  source,
  target,
  data,
  style = {},
  markerEnd,
}: Props) {
  const isSelfLoop = source === target;
  const baseStrokeWidth = (style.strokeWidth as number) || 1;
  const messageCount = data.messages?.length || 0;
  const finalStrokeWidth = isSelfLoop
    ? Math.max(baseStrokeWidth, 2)
    : Math.min(Math.max(messageCount, 1), 5) * baseStrokeWidth;

  let edgePath = '';
  let labelX = 0;
  let labelY = 0;

  if (data.routingType === 'secondary' || isSelfLoop) {
    const midY = (sourceY + targetY) / 2;
    const offset = EDGE_OFFSET;
    edgePath = `
      M ${sourceX},${sourceY}
      L ${sourceX},${sourceY + 10}
      L ${sourceX + offset},${sourceY + 10}
      L ${sourceX + offset},${targetY - 10}
      L ${targetX},${targetY - 10}
      L ${targetX},${targetY}
    `;
    labelX = sourceX + offset;
    labelY = midY;
  } else {
    [edgePath, labelX, labelY] = getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
    });
  }

  const getLabelPosition = (x: number, y: number) => {
    if (!data.routingType || isSelfLoop) return { x, y };
    const verticalOffset = data.routingType === 'secondary' ? -35 : 35;
    const horizontalOffset = data.routingType === 'secondary' ? -25 : 25;
    const dx = targetX - sourceX;
    const dy = targetY - sourceY;
    const isMoreHorizontal = Math.abs(dx) > Math.abs(dy);
    return {
      x: isMoreHorizontal ? x : x + horizontalOffset,
      y: y + (data.routingType === 'secondary' ? -20 : 20) + verticalOffset * 0,
    };
  };

  const labelPosition = getLabelPosition(labelX, labelY);

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={{
          ...style,
          strokeWidth: finalStrokeWidth,
          stroke: data.routingType === 'secondary' ? '#0891b2' : style.stroke,
        }}
        markerEnd={markerEnd}
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelPosition.x}px,${labelPosition.y}px)`,
              pointerEvents: 'all',
              transition: 'all 0.2s ease-in-out',
            }}
            onClick={data.onClick}
          >
            <div
              className="px-2 py-1 rounded bg-secondary hover:bg-tertiary text-primary cursor-pointer transform hover:scale-110 transition-all flex items-center gap-1"
              style={{ whiteSpace: 'nowrap' }}
            >
              {messageCount > 0 && <span className="text-xs text-secondary">({messageCount})</span>}
              <span className="text-sm">{data.label}</span>
            </div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export default AGLightEdge;
