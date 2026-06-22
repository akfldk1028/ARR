import { create } from 'zustand';

export interface ConversationTurn {
  role: 'user' | 'agent' | 'system';
  text: string;
  isFinal: boolean;
  timestamp: Date;
  groundingChunks?: Array<any>;
  toolResponse?: any;
}

export interface MapMarker {
  position: google.maps.LatLngAltitudeLiteral | google.maps.LatLngLiteral;
  [key: string]: unknown;
}

export const personas: Record<string, string> = {
  Default: 'Default assistant',
};

type UIState = {
  isSidebarOpen: boolean;
  showSystemMessages: boolean;
  toggleSidebar: () => void;
  toggleShowSystemMessages: () => void;
};

export const useUI = create<UIState>((set) => ({
  isSidebarOpen: false,
  showSystemMessages: true,
  toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
  toggleShowSystemMessages: () => set((s) => ({ showSystemMessages: !s.showSystemMessages })),
}));

type SettingsState = {
  systemPrompt: string;
  model: string;
  voice: string;
  isEasterEggMode: boolean;
  activePersona: string;
  setSystemPrompt: (value: string) => void;
  setModel: (value: string) => void;
  setVoice: (value: string) => void;
  setPersona: (value: string) => void;
  activateEasterEggMode: () => void;
};

export const useSettings = create<SettingsState>((set) => ({
  systemPrompt: 'You are a helpful map assistant.',
  model: 'gemini-2.0-flash-live-001',
  voice: 'Puck',
  isEasterEggMode: false,
  activePersona: 'Default',
  setSystemPrompt: (systemPrompt) => set({ systemPrompt }),
  setModel: (model) => set({ model }),
  setVoice: (voice) => set({ voice }),
  setPersona: (activePersona) => set({ activePersona }),
  activateEasterEggMode: () => set({ isEasterEggMode: true }),
}));

type LogState = {
  turns: ConversationTurn[];
  isAwaitingFunctionResponse: boolean;
  addTurn: (turn: Omit<ConversationTurn, 'timestamp'> & { timestamp?: Date }) => void;
  updateLastTurn: (patch: Partial<ConversationTurn>) => void;
  mergeIntoLastAgentTurn: (patch: Partial<ConversationTurn>) => void;
  clearTurns: () => void;
  setIsAwaitingFunctionResponse: (value: boolean) => void;
};

export const useLogStore = create<LogState>((set) => ({
  turns: [],
  isAwaitingFunctionResponse: false,
  addTurn: (turn) => set((s) => ({ turns: [...s.turns, { ...turn, timestamp: turn.timestamp || new Date() }] })),
  updateLastTurn: (patch) => set((s) => {
    if (!s.turns.length) return s;
    const turns = [...s.turns];
    turns[turns.length - 1] = { ...turns[turns.length - 1], ...patch };
    return { turns };
  }),
  mergeIntoLastAgentTurn: (patch) => set((s) => {
    const idx = s.turns.map((t) => t.role).lastIndexOf('agent');
    if (idx < 0) return s;
    const turns = [...s.turns];
    turns[idx] = { ...turns[idx], ...patch, text: `${turns[idx].text || ''}${patch.text || ''}` };
    return { turns };
  }),
  clearTurns: () => set({ turns: [] }),
  setIsAwaitingFunctionResponse: (isAwaitingFunctionResponse) => set({ isAwaitingFunctionResponse }),
}));

type MapState = {
  markers: MapMarker[];
  cameraTarget: google.maps.maps3d.CameraOptions | null;
  preventAutoFrame: boolean;
  setCameraTarget: (target: google.maps.maps3d.CameraOptions | null) => void;
  setPreventAutoFrame: (value: boolean) => void;
  clearMarkers: () => void;
};

export const useMapStore = create<MapState>((set) => ({
  markers: [],
  cameraTarget: null,
  preventAutoFrame: false,
  setCameraTarget: (cameraTarget) => set({ cameraTarget }),
  setPreventAutoFrame: (preventAutoFrame) => set({ preventAutoFrame }),
  clearMarkers: () => set({ markers: [] }),
}));

export type ToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  isEnabled: boolean;
};

export const useTools = create<{ tools: ToolDefinition[] }>(() => ({
  tools: [],
}));
