/**
 * Land analysis state hook — 좌표 또는 주소 → PNU → 규제 분석
 */

import { useState, useCallback } from 'react';
import { reverse, analyze } from '../lib/land-api-client';
import { isPnu } from '../lib/constants';
import type { LandAnalysisResult, ReverseGeocodeResult } from '../lib/types';

interface AnalysisState {
  analysis: LandAnalysisResult | null;
  reverseResult: ReverseGeocodeResult | null;
  loading: boolean;
  error: string | null;
  step: 'reverse' | 'analyze' | null;
}

const INITIAL_STATE: AnalysisState = {
  analysis: null,
  reverseResult: null,
  loading: false,
  error: null,
  step: null,
};

export function useLandAnalysis() {
  const [state, setState] = useState<AnalysisState>(INITIAL_STATE);

  /** 좌표 클릭 → reverse geocode → analyze */
  const analyzeByCoordinate = useCallback(async (lng: number, lat: number) => {
    setState(prev => ({ ...prev, loading: true, error: null, step: 'reverse' }));

    try {
      const rev = await reverse(lng, lat);
      setState(prev => ({ ...prev, reverseResult: rev }));

      if (!rev.success || !rev.pnu) {
        setState(prev => ({
          ...prev,
          loading: false,
          error: rev.error || 'PNU를 찾을 수 없습니다',
          step: null,
        }));
        return { reverse: rev, analysis: null };
      }

      setState(prev => ({ ...prev, step: 'analyze' }));
      const result = await analyze(rev.pnu, 'pnu', undefined, rev.geometry);
      setState(prev => ({
        ...prev,
        analysis: result,
        loading: false,
        step: null,
      }));
      return { reverse: rev, analysis: result };
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '분석 실패';
      setState(prev => ({ ...prev, loading: false, error: msg, step: null }));
      return { reverse: null, analysis: null };
    }
  }, []);

  /** 주소/PNU 직접 입력 → analyze */
  const analyzeByInput = useCallback(async (input: string) => {
    setState(prev => ({
      ...prev,
      loading: true,
      error: null,
      step: 'analyze',
      reverseResult: null,
    }));

    try {
      const inputType = isPnu(input) ? 'pnu' : 'address';
      const result = await analyze(input.trim(), inputType);
      setState(prev => ({
        ...prev,
        analysis: result,
        loading: false,
        step: null,
      }));
      return result;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '분석 실패';
      setState(prev => ({ ...prev, loading: false, error: msg, step: null }));
      return null;
    }
  }, []);

  const clear = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  return { ...state, analyzeByCoordinate, analyzeByInput, clear };
}
