/**
 * 검색 결과 표시 컴포넌트
 */

import React from 'react';
import type { LawSearchResponse } from '../lib/types';
import { LawArticleCard } from './LawArticleCard';
import { StatsPanel } from './StatsPanel';

interface ResultDisplayProps {
  /** 검색 응답 데이터 */
  response: LawSearchResponse;
}

/**
 * 검색 결과 표시 컴포넌트
 */
export function ResultDisplay({ response }: ResultDisplayProps) {
  const { results, stats, domain_name, response_time, domains_queried, a2a_domains } = response;

  // A2A 협업 여부 확인
  const hasA2ACollaboration = stats?.a2a_collaboration_triggered && a2a_domains && a2a_domains.length > 0;

  // 결과를 자체 도메인과 A2A 협업으로 분리
  const selfResults = results.filter(r => !r.via_a2a);
  const a2aResults = results.filter(r => r.via_a2a);

  // 결과가 없는 경우
  if (results.length === 0) {
    return (
      <div className="result-display">
        {/* 통계 패널 (결과가 0개여도 표시) */}
        <StatsPanel
          stats={stats}
          responseTime={response_time}
          domainName={domain_name}
          domainsQueried={domains_queried}
          a2aDomains={a2a_domains}
        />

        {/* 결과 없음 메시지 */}
        <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <div className="text-4xl mb-2">🔍</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            검색 결과가 없습니다
          </h3>
          <p className="text-sm text-gray-600">
            다른 검색어를 시도해 보세요.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="result-display space-y-4">
      {/* 통계 패널 */}
      <StatsPanel
        stats={stats}
        responseTime={response_time}
        domainName={domain_name}
        domainsQueried={domains_queried}
        a2aDomains={a2a_domains}
      />

      {/* A2A 협업 결과가 있는 경우 섹션 분리 */}
      {hasA2ACollaboration ? (
        <>
          {/* 자체 도메인 결과 섹션 */}
          {selfResults.length > 0 && (
            <div className="self-domain-section">
              <div className="flex items-center gap-2 mb-3">
                <div className="flex-1 h-px bg-gradient-to-r from-cyan-300 to-transparent"></div>
                <h3 className="text-base font-bold text-cyan-700 flex items-center gap-2">
                  <span className="w-2 h-2 bg-cyan-500 rounded-full"></span>
                  자체 도메인 결과
                  <span className="px-2 py-0.5 bg-cyan-100 text-cyan-700 text-xs font-bold rounded">
                    {selfResults.length}개
                  </span>
                </h3>
                <div className="flex-1 h-px bg-gradient-to-l from-cyan-300 to-transparent"></div>
              </div>
              {domain_name && (
                <div className="mb-3 text-sm text-gray-600 text-center">
                  주 도메인: <span className="font-semibold text-cyan-700">{domain_name}</span>
                </div>
              )}
              <div className="space-y-3">
                {selfResults.map((article, index) => (
                  <LawArticleCard
                    key={article.hang_id}
                    article={article}
                    index={index + 1}
                  />
                ))}
              </div>
            </div>
          )}

          {/* A2A 협업 결과 섹션 */}
          {a2aResults.length > 0 && (
            <div className="a2a-domain-section mt-6">
              <div className="flex items-center gap-2 mb-3">
                <div className="flex-1 h-px bg-gradient-to-r from-pink-300 via-purple-300 to-transparent"></div>
                <h3 className="text-base font-bold text-transparent bg-clip-text bg-gradient-to-r from-pink-600 to-purple-600 flex items-center gap-2">
                  <span className="w-2 h-2 bg-gradient-to-r from-pink-500 to-purple-500 rounded-full"></span>
                  🤝 A2A 협업 결과
                  <span className="px-2 py-0.5 bg-gradient-to-r from-pink-100 to-purple-100 text-pink-700 text-xs font-bold rounded">
                    {a2aResults.length}개
                  </span>
                </h3>
                <div className="flex-1 h-px bg-gradient-to-l from-purple-300 via-pink-300 to-transparent"></div>
              </div>
              <div className="mb-3 text-sm text-center">
                <span className="text-purple-600 font-medium">
                  병렬 협업으로 {a2a_domains?.length || 0}개 도메인에서 추가 결과 발견
                </span>
              </div>
              <div className="space-y-3">
                {a2aResults.map((article, index) => (
                  <LawArticleCard
                    key={article.hang_id}
                    article={article}
                    index={selfResults.length + index + 1}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          {/* A2A 협업이 없는 경우 - 기존 단순 표시 */}
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">
              📄 검색 결과 ({results.length}개)
            </h3>
            {domain_name && (
              <span className="text-sm text-gray-600">도메인: {domain_name}</span>
            )}
          </div>

          {/* 법률 조항 목록 */}
          <div className="space-y-3">
            {results.map((article, index) => (
              <LawArticleCard
                key={article.hang_id}
                article={article}
                index={index + 1}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
