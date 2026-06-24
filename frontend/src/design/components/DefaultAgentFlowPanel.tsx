import React, { useEffect, useMemo, useState } from 'react';
import { getAgLightBusLog, sendAgLightBusMessage } from '../lib/api-client';
import { COLLABORATION_STEPS } from '../lib/ag-light-collaboration';
import AGLightFlow from './ag-light-flow/AGLightFlow';
import type { AGLightMessage, AGLightRunStatus } from './ag-light-flow/types';
import DirectAgentChatPanel from './DirectAgentChatPanel';

const DEFAULT_AGENT_FLOW_MESSAGES: AGLightMessage[] = [
  {
    from_agent: 'user',
    to_agent: 'design_orchestrator',
    message: '기본 프롬프트: PNU/후보가 들어오면 법규 그래프, 주차, MAAS 매스, 최종검토 에이전트가 순차 검토합니다.',
    event_type: 'prompt_template',
  },
];

const FLOW_AGENT_IDS = new Set([
  'user',
  'design_orchestrator',
  'law_graph_agent',
  'law_agent',
  'parking_agent',
  'maas_geometry_agent',
  'sunlight_agent',
  'datum_agent',
  'review_agent',
  'design_critic',
]);

const toFlowMessage = (event: {
  timestamp?: string;
  from_agent: string;
  to_agent: string;
  message: string;
  event_type?: string;
  metadata?: Record<string, unknown>;
}): AGLightMessage => ({
  timestamp: event.timestamp,
  from_agent: event.from_agent,
  to_agent: event.to_agent,
  message: event.message,
  event_type: event.event_type,
  metadata: event.metadata,
});

export default function DefaultAgentFlowPanel({
  pnu,
  status = 'idle',
}: {
  pnu?: string | null;
  status?: AGLightRunStatus;
}) {
  const pnuMessage = useMemo<AGLightMessage | null>(() => {
    if (!pnu) return null;
    return {
      from_agent: 'user',
      to_agent: 'design_orchestrator',
      message: `PNU ${pnu} 입력됨: 법규 그래프, 주차, 매스/기준면, 최종검토 순서로 전달 대기`,
      event_type: 'pnu_context',
      metadata: { pnu },
    };
  }, [pnu]);
  const [manualMessages, setManualMessages] = useState<AGLightMessage[]>([]);
  const [busMessages, setBusMessages] = useState<AGLightMessage[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('law_graph_agent');
  const messages = useMemo(
    () => [
      ...DEFAULT_AGENT_FLOW_MESSAGES,
      ...(pnuMessage ? [pnuMessage] : []),
      ...busMessages,
      ...manualMessages,
    ].slice(-18),
    [busMessages, manualMessages, pnuMessage],
  );

  useEffect(() => {
    let cancelled = false;
    const loadBus = async () => {
      try {
        const events = await getAgLightBusLog(30);
        if (cancelled) return;
        const relevant = events
          .filter((event) => FLOW_AGENT_IDS.has(event.from_agent) || FLOW_AGENT_IDS.has(event.to_agent))
          .map(toFlowMessage)
          .slice(-8);
        setBusMessages(relevant);
      } catch {
        if (!cancelled) setBusMessages([]);
      }
    };
    loadBus();
    const timer = window.setInterval(loadBus, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const sendDirectAgentMessage = async (targetAgent: string, message: string) => {
    const event: AGLightMessage = {
      from_agent: 'user',
      to_agent: targetAgent,
      message,
      event_type: 'direct_agent_command',
      metadata: { source: 'arr_design_default_flow' },
    };
    await sendAgLightBusMessage(event);
    setManualMessages((current) => [...current, event].slice(-8));
  };

  return (
    <div style={{
      border: '1px solid rgba(94,234,212,0.18)',
      borderRadius: 8,
      padding: 10,
      color: '#64748b',
      fontSize: 12,
      lineHeight: 1.6,
      background: 'rgba(15,23,42,0.72)',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 8,
        marginBottom: 8,
      }}>
        <div>
          <div style={{ color: '#d1fae5', fontSize: 12, fontWeight: 800 }}>
            기본 프롬프트 React Flow
          </div>
          <div style={{ color: '#64748b', fontSize: 10, marginTop: 2 }}>
            PNU/후보 선택 전에도 User 요청이 어떤 에이전트에 연결되는지 표시
          </div>
        </div>
        <span style={{
          color: '#fbbf24',
          fontSize: 9,
          border: '1px solid rgba(251,191,36,0.22)',
          borderRadius: 999,
          padding: '2px 7px',
          whiteSpace: 'nowrap',
        }}>
          TEMPLATE
        </span>
      </div>
      <AGLightFlow
        reviews={[]}
        messages={messages}
        status={status}
        viewMode="pattern"
        pnu={pnu}
        selectedAgentId={selectedAgentId}
        onSelectAgent={setSelectedAgentId}
      />
      <div
        data-testid="ag-light-collaboration-method"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: 6,
          marginTop: 8,
        }}
      >
        {COLLABORATION_STEPS.map((step) => (
          <button
            key={step.agent}
            type="button"
            onClick={() => setSelectedAgentId(step.agent)}
            style={{
              minHeight: 56,
              padding: '7px 8px',
              borderRadius: 7,
              border: selectedAgentId === step.agent
                ? '1px solid rgba(94,234,212,0.5)'
                : '1px solid rgba(148,163,184,0.14)',
              background: selectedAgentId === step.agent
                ? 'rgba(20,184,166,0.14)'
                : 'rgba(2,6,23,0.38)',
              textAlign: 'left',
              cursor: 'pointer',
            }}
          >
            <div style={{ color: selectedAgentId === step.agent ? '#99f6e4' : '#bfdbfe', fontSize: 10, fontWeight: 900 }}>
              {step.label}
            </div>
            <div style={{ color: '#60a5fa', fontSize: 9, marginTop: 2, fontFamily: 'ui-monospace, monospace' }}>
              {step.agent}
            </div>
            <div style={{ color: '#94a3b8', fontSize: 9, lineHeight: 1.3, marginTop: 3 }}>
              {step.output}
            </div>
          </button>
        ))}
      </div>
      <DirectAgentChatPanel
        selectedAgentId={selectedAgentId}
        onSelectedAgentChange={setSelectedAgentId}
        onSend={sendDirectAgentMessage}
        helperText="AG-light가 켜져 있으면 선택 agent의 bus로 바로 전송됩니다."
      />
      <div style={{ marginTop: 8, color: '#94a3b8', fontSize: 10, lineHeight: 1.5 }}>
        후보를 선택하면 이 흐름에 실제 법규 evidence, 주차 검토, MAAS 매스 검토 결과가 붙습니다.
      </div>
    </div>
  );
}
