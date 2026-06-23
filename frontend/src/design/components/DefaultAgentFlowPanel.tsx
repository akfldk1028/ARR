import React, { useState } from 'react';
import { sendAgLightBusMessage } from '../lib/api-client';
import AGLightFlow from './ag-light-flow/AGLightFlow';
import type { AGLightMessage } from './ag-light-flow/types';
import DirectAgentChatPanel from './DirectAgentChatPanel';

const DEFAULT_AGENT_FLOW_MESSAGES: AGLightMessage[] = [
  {
    from_agent: 'user',
    to_agent: 'design_orchestrator',
    message: '기본 프롬프트: PNU/후보가 들어오면 법규 그래프, 주차, MAAS 매스, 최종검토 에이전트가 순차 검토합니다.',
    event_type: 'prompt_template',
  },
];

export default function DefaultAgentFlowPanel() {
  const [messages, setMessages] = useState<AGLightMessage[]>(DEFAULT_AGENT_FLOW_MESSAGES);
  const [selectedAgentId, setSelectedAgentId] = useState('law_graph_agent');

  const sendDirectAgentMessage = async (targetAgent: string, message: string) => {
    const event: AGLightMessage = {
      from_agent: 'user',
      to_agent: targetAgent,
      message,
      event_type: 'direct_agent_command',
      metadata: { source: 'arr_design_default_flow' },
    };
    await sendAgLightBusMessage(event);
    setMessages((current) => [...current, event]);
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
        status="idle"
        viewMode="pattern"
        selectedAgentId={selectedAgentId}
        onSelectAgent={setSelectedAgentId}
      />
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
