import type {
  AutoConstraintsResult,
  DesignData,
  DesignJob,
  FloorPlanResult,
  FloorPlanRoom,
  GeoJSONFeature,
  InteractivePreviewResult,
  InteractiveOperationResult,
  InteractivePatchResult,
  MaasAestheticResult,
  MaasLegalVariantsResult,
  SiteBoundaryResult,
} from './types';

const BASE = '/design';
const AG_LIGHT_BASE = (((import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_AG_LIGHT_URL)
  || 'http://127.0.0.1:8200').replace(/\/$/, '');

export interface AgLightHealth {
  service: string;
  status: boolean;
  timestamp?: string;
  components?: {
    bus?: { connected_agents?: string[]; log_count?: number };
    memory?: { decisions?: string[]; events_count?: number };
    mcp?: Record<string, unknown>;
  };
}

export interface AgLightBusEvent {
  timestamp: string;
  from_agent: string;
  to_agent: string;
  message: string;
  event_type?: string;
  metadata?: Record<string, unknown>;
}

export interface DesignEvidence {
  final_status?: string;
  summary?: Record<string, unknown>;
  checks?: Array<Record<string, unknown>>;
  hard_failures?: unknown[];
  missing_evidence?: unknown[];
  open_issues?: unknown[];
  non_negotiable?: Record<string, unknown>;
  domain_status_counts?: Record<string, Record<string, number> | number>;
  [key: string]: unknown;
}

export async function createJob(params: {
  site_polygon: object;
  pnu?: string;
  address?: string;
  constraints?: object[];
  job_spec?: object;
}): Promise<DesignJob> {
  const res = await fetch(`${BASE}/jobs/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || res.statusText);
  return res.json();
}

export async function getJob(jobId: string): Promise<DesignJob> {
  const res = await fetch(`${BASE}/jobs/${jobId}/`);
  if (!res.ok) throw new Error('Job not found');
  return res.json();
}

export async function cancelJob(jobId: string): Promise<void> {
  await fetch(`${BASE}/jobs/${jobId}/cancel/`, { method: 'POST' });
}

export async function runJob(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/jobs/${jobId}/run/`, { method: 'POST' });
  if (!res.ok) throw new Error('Job run failed');
}

export async function getJobResults(jobId: string) {
  const res = await fetch(`${BASE}/jobs/${jobId}/results/`);
  if (!res.ok) throw new Error('Results not found');
  return res.json();
}

export async function getDesignEvidence(jobId: string, designId: number): Promise<DesignEvidence> {
  const res = await fetch(`${BASE}/jobs/${jobId}/results/${designId}/evidence/`);
  if (!res.ok) throw new Error((await res.json()).error || 'Evidence not found');
  return res.json();
}

export async function getAgLightHealth(): Promise<AgLightHealth> {
  const res = await fetch(`${AG_LIGHT_BASE}/health`);
  if (!res.ok) throw new Error('AG-light health check failed');
  return res.json();
}

export async function getAgLightBusLog(limit = 50): Promise<AgLightBusEvent[]> {
  const res = await fetch(`${AG_LIGHT_BASE}/bus/log?limit=${encodeURIComponent(String(limit))}`);
  if (!res.ok) throw new Error('AG-light bus log fetch failed');
  return res.json();
}

export async function sendAgLightBusMessage(params: {
  from_agent: string;
  to_agent: string;
  message: string;
  event_type?: string;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  const res = await fetch(`${AG_LIGHT_BASE}/bus/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error('AG-light bus send failed');
}

export async function getSiteBoundary(pnu: string): Promise<SiteBoundaryResult> {
  const res = await fetch(`${BASE}/site-boundary/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pnu }),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'Boundary fetch failed');
  return res.json();
}

export async function getAutoConstraints(params: {
  pnu?: string;
  zones?: string[];
  address?: string;
  site_polygon?: object;
  building_type?: string;
  include_law_articles?: boolean;
}): Promise<AutoConstraintsResult> {
  const res = await fetch(`${BASE}/auto-constraints/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'Constraint generation failed');
  return res.json();
}

export async function generateFloorPlan(params: {
  footprint_geojson: object;
  rooms: FloorPlanRoom[];
  cell_size?: number;
  algorithm?: string;
  options?: { num_generations?: number; population_size?: number };
}): Promise<FloorPlanResult> {
  const res = await fetch(`${BASE}/floor-plan/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'Floor plan generation failed');
  return res.json();
}

export interface ConstraintsParams {
  site_polygon: object;
  bcr_limit_pct?: number;
  far_limit_pct?: number;
  height_limit_m?: number;
  adjacent_setback_m?: number;
  north_setback_m?: number;
  road_setback_m?: number;
  sunlight_slope?: number;
  sunlight_base_height_m?: number;
}

export interface ConstraintsResult {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: { type: string; coordinates: unknown };
    properties: {
      kind: string;
      label?: string;
      color?: string;
      stroke_width?: number;
      stroke_dasharray?: number[];
      fill_opacity?: number;
      metadata?: Record<string, unknown>;
    };
  }>;
  metadata?: { generator?: string; version?: string };
}

export async function visualizeConstraints(params: ConstraintsParams): Promise<ConstraintsResult> {
  const res = await fetch(`${BASE}/constraints/visualize/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'Constraints visualize failed');
  return res.json();
}

export async function createInteractivePatch(params: {
  message: string;
  selected_design?: DesignData | null;
  mass_geojson?: GeoJSONFeature | null;
  constraints?: object[];
}): Promise<InteractivePatchResult> {
  const res = await fetch(`${BASE}/interactive/patch/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'Interactive patch failed');
  return res.json();
}

export async function createInteractivePreview(params: {
  patch_plan: InteractivePatchResult;
  selected_design: DesignData;
  site_polygon: object;
  site_area_m2: number;
  constraints?: object[];
  building_type?: string;
  algorithm?: string;
}): Promise<InteractivePreviewResult> {
  const res = await fetch(`${BASE}/interactive/preview/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'Interactive preview failed');
  return res.json();
}

export async function applyInteractiveOperation(params: {
  mass_geojson: GeoJSONFeature;
  site_polygon: object;
  operation: object;
  constraints?: object[];
  building_type?: string;
  sunlight_envelope?: object | null;
  setback_geometries?: object | null;
}): Promise<InteractiveOperationResult> {
  const res = await fetch(`${BASE}/interactive/operation/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'Interactive operation failed');
  return res.json();
}

export async function createMaasLegalVariants(params: {
  mass_geojson: GeoJSONFeature;
  site_polygon: object;
  constraints?: object[];
  building_type?: string;
  max_variants?: number;
  sunlight_envelope?: object | null;
  setback_geometries?: object | null;
  include_interactive_seed?: boolean;
  preferred_operator?: string | null;
  pnu?: string | null;
  parking_options?: object | null;
}): Promise<MaasLegalVariantsResult> {
  const res = await fetch(`${BASE}/maas/legal-variants/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'MAAS variants failed');
  return res.json();
}

export async function createMaasAesthetic(params: {
  job_id: string;
  design_id: number;
  provider?: 'placeholder' | 'gpt-image' | 'nano-banana';
  style?: string;
  attach_to_evidence?: boolean;
}): Promise<MaasAestheticResult> {
  const res = await fetch(`${BASE}/jobs/${params.job_id}/results/${params.design_id}/aesthetic/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      provider: params.provider || 'placeholder',
      style: params.style,
      attach_to_evidence: params.attach_to_evidence ?? true,
    }),
  });
  if (!res.ok) throw new Error((await res.json()).error || 'MAAS aesthetic generation failed');
  return res.json();
}
