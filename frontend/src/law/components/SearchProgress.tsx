/**
 * MAS 검색 진행상황 시각화 컴포넌트
 */

import React from 'react';
import type { SearchProgress, SearchStage } from '../hooks/use-law-search-stream';

/**
 * Props 타입
 */
interface SearchProgressProps {
  progress: SearchProgress;
}

/**
 * 단계별 아이콘
 */
const STAGE_ICONS: Record<SearchStage, string> = {
  exact_match: '🎯',
  vector_search: '🔍',
  relationship_search: '🔗',
  rne_expansion: '🌳',
  enrichment: '✨',
};

/**
 * 단계별 한글 이름 (fallback)
 */
const STAGE_NAMES: Record<SearchStage, string> = {
  exact_match: '정확 일치 검색',
  vector_search: '벡터 유사도 검색',
  relationship_search: '관계 임베딩 검색',
  rne_expansion: 'RNE 그래프 확장',
  enrichment: '결과 강화',
};

/**
 * 단계별 진행률 임계값
 */
const STAGE_PROGRESS: Record<SearchStage, number> = {
  exact_match: 0.2,
  vector_search: 0.4,
  relationship_search: 0.6,
  rne_expansion: 0.8,
  enrichment: 0.95,
};

/**
 * 검색 진행상황 표시 컴포넌트
 */
export function SearchProgressIndicator({ progress }: SearchProgressProps) {
  const currentProgress = progress.progress || 0;

  return (
    <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 space-y-4">
      {/* Agent Badge */}
      <div className="flex items-center gap-3 bg-white rounded-lg p-4 border-l-4 border-blue-600">
        <span className="text-2xl">🤖</span>
        <div className="flex-1">
          <div className="font-semibold text-gray-800">
            {progress.agent || '에이전트 준비 중...'}
          </div>
          {progress.node_count && (
            <div className="text-sm text-gray-600">
              {progress.node_count.toLocaleString()} 노드 관리 중
            </div>
          )}
        </div>
      </div>

      {/* Current Stage */}
      <div className="flex items-center gap-3 text-lg font-medium text-gray-700">
        <span className="text-2xl animate-pulse">
          {progress.stage ? STAGE_ICONS[progress.stage] : '🔄'}
        </span>
        <span>{progress.stage_name || STAGE_NAMES[progress.stage!] || '검색 준비 중...'}</span>
      </div>

      {/* Progress Bar */}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-300 ease-out"
          style={{ width: `${currentProgress * 100}%` }}
        />
      </div>

      {/* Stage Checklist */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
        {(Object.entries(STAGE_PROGRESS) as [SearchStage, number][]).map(([stage, threshold]) => {
          const isDone = currentProgress >= threshold;
          return (
            <div
              key={stage}
              className={`
                px-3 py-2 rounded-lg text-sm font-medium transition-all duration-300
                ${
                  isDone
                    ? 'bg-green-100 text-green-700 border-l-3 border-green-500'
                    : 'bg-white text-gray-400 border-l-3 border-gray-300'
                }
              `}
            >
              <span className="mr-1">{STAGE_ICONS[stage]}</span>
              {STAGE_NAMES[stage]}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * 에러 표시 컴포넌트
 */
export function SearchErrorIndicator({ message }: { message: string }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <span className="text-2xl">❌</span>
        <div>
          <div className="font-semibold text-red-800">검색 실패</div>
          <div className="text-sm text-red-600 mt-1">{message}</div>
        </div>
      </div>
    </div>
  );
}

/**
 * 검색 완료 헤더 컴포넌트
 */
export function SearchCompleteHeader({
  resultCount,
  responseTime,
  domainName,
}: {
  resultCount: number;
  responseTime: number;
  domainName?: string;
}) {
  return (
    <div className="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <span className="text-2xl">✅</span>
        <div>
          <div className="font-semibold text-green-800">검색 완료</div>
          <div className="text-sm text-green-600">
            {resultCount}개 결과 발견
            {domainName && ` · ${domainName}`}
          </div>
        </div>
      </div>
      <div className="bg-green-600 text-white px-4 py-2 rounded-full font-semibold text-sm">
        {responseTime}ms
      </div>
    </div>
  );
}
