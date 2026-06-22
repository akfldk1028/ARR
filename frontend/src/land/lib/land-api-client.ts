/**
 * Land API client — Vite proxy 경유 (/land/* → Django :8000)
 *
 * 타입은 types.ts 에서 정의. 여기는 fetch 로직만.
 */

import type {
  LandAnalysisResult,
  PnuResolveResult,
  ReverseGeocodeResult,
} from './types';

/** POST /land/analyze/ — 토지 규제 분석 */
export async function analyze(
  input: string,
  inputType: 'pnu' | 'address' = 'address',
  zones?: string[],
  geometry?: object | null,
): Promise<LandAnalysisResult> {
  const body: Record<string, unknown> = { input, input_type: inputType };
  if (zones) body.zones = zones;
  if (geometry) body.geometry = geometry;

  const res = await fetch('/land/analyze/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`분석 실패: ${res.status}`);
  return res.json();
}

/** POST /land/resolve/ — 주소 → PNU */
export async function resolve(
  input: string,
  inputType: 'address' | 'pnu' = 'address',
): Promise<PnuResolveResult> {
  const res = await fetch('/land/resolve/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, input_type: inputType }),
  });
  if (!res.ok) throw new Error(`PNU 변환 실패: ${res.status}`);
  return res.json();
}

/** GET /land/zones/ — 21개 용도지역 목록 */
export async function getZones(): Promise<unknown[]> {
  const res = await fetch('/land/zones/');
  if (!res.ok) throw new Error(`용도지역 조회 실패: ${res.status}`);
  return res.json();
}

/** POST /land/reverse/ — 좌표 → PNU + 필지 geometry */
export async function reverse(x: number, y: number): Promise<ReverseGeocodeResult> {
  const res = await fetch('/land/reverse/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ x, y }),
  });
  return res.json();
}

/** GET /land/elevation-grid/ — 주변 표고 격자 (Open-Meteo or NGII LiDAR) */
export interface ElevationGridPoint { lng: number; lat: number; elev_m: number; }
export interface ElevationGridResult {
  center: { lng: number; lat: number };
  radius_m: number;
  n: number;
  step_m: number;
  provider: string;
  points: ElevationGridPoint[];
}
export async function elevationGrid(
  lng: number, lat: number, radius_m = 50, n = 5,
): Promise<ElevationGridResult> {
  const url = `/land/elevation-grid/?lng=${lng}&lat=${lat}&radius_m=${radius_m}&n=${n}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`elevation-grid failed: ${res.status}`);
  return res.json();
}

// Re-export types for convenience
export type { LandAnalysisResult, PnuResolveResult, ReverseGeocodeResult };
