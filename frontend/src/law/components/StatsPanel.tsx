/**
 * 검색 통계 패널 컴포넌트
 */

import React from 'react';
import type { SearchStats } from '../lib/types';

interface StatsPanelProps {
  /** 검색 통계 */
  stats?: SearchStats;

  /** 응답 시간 (ms) */
  responseTime?: number;

  /** 도메인 이름 */
  domainName?: string;

  /** 조회한 도메인 목록 */
  domainsQueried?: string[];

  /** A2A 협업한 도메인 목록 */
  a2aDomains?: string[];
}

/**
 * 검색 통계 패널 컴포넌트
 */
export function StatsPanel({
  stats,
  responseTime,
  domainName,
  domainsQueried,
  a2aDomains
}: StatsPanelProps) {
  const hasA2ACollaboration = stats?.a2a_collaboration_triggered && a2aDomains && a2aDomains.length > 0;

  return (
    <div className="stats-panel bg-gray-50 border border-gray-200 rounded-lg p-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-700">📊 검색 통계</h3>
          {hasA2ACollaboration && (
            <span className="px-2 py-0.5 bg-gradient-to-r from-pink-500 to-purple-500 text-white text-[10px] font-bold rounded-full">
              PARALLEL A2A
            </span>
          )}
        </div>
        {responseTime && (
          <span className={`text-xs font-medium ${hasA2ACollaboration ? 'text-purple-600' : 'text-gray-500'}`}>
            {hasA2ACollaboration && '⚡ '}응답 시간: {responseTime}ms
          </span>
        )}
      </div>

      {/* 통계 그리드 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {/* 총 결과 */}
        <div className="stat-item bg-white rounded-md p-3 border border-gray-100">
          <div className="text-2xl font-bold text-blue-600">{stats?.total || 0}</div>
          <div className="text-xs text-gray-600 mt-1">총 조항</div>
        </div>

        {/* 노드 임베딩 */}
        <div className="stat-item bg-white rounded-md p-3 border border-gray-100">
          <div className="text-2xl font-bold text-green-600">{stats?.vector_count || 0}</div>
          <div className="text-xs text-gray-600 mt-1">노드 임베딩</div>
          <div className="text-[10px] text-gray-400 mt-0.5">KR-SBERT 768dim</div>
        </div>

        {/* 관계 임베딩 */}
        <div className="stat-item bg-white rounded-md p-3 border border-gray-100">
          <div className="text-2xl font-bold text-purple-600">{stats?.relationship_count || 0}</div>
          <div className="text-xs text-gray-600 mt-1">관계 임베딩</div>
          <div className="text-[10px] text-gray-400 mt-0.5">OpenAI 3072dim</div>
        </div>

        {/* 그래프 확장 */}
        <div className="stat-item bg-white rounded-md p-3 border border-gray-100">
          <div className="text-2xl font-bold text-orange-600">
            {stats?.graph_expansion_count || 0}
          </div>
          <div className="text-xs text-gray-600 mt-1">그래프 확장</div>
          <div className="text-[10px] text-gray-400 mt-0.5">RNE 알고리즘</div>
        </div>

        {/* 자체 도메인 */}
        <div className="stat-item bg-white rounded-md p-3 border border-gray-100">
          <div className="text-2xl font-bold text-cyan-600">{stats?.my_domain_count || 0}</div>
          <div className="text-xs text-gray-600 mt-1">자체 도메인</div>
          {domainName && (
            <div className="text-[10px] text-gray-400 mt-0.5 truncate" title={domainName}>
              {domainName}
            </div>
          )}
        </div>

        {/* 협업 도메인 */}
        <div className="stat-item bg-white rounded-md p-3 border border-gray-100">
          <div className="text-2xl font-bold text-pink-600">{stats?.neighbor_count || 0}</div>
          <div className="text-xs text-gray-600 mt-1">협업 도메인</div>
          <div className="text-[10px] text-gray-400 mt-0.5">A2A 통신</div>
        </div>
      </div>

      {/* A2A 협업 정보 */}
      {hasA2ACollaboration && (
        <div className="mt-3 pt-3 border-t border-purple-200 bg-gradient-to-r from-pink-50 to-purple-50 -mx-4 px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-semibold text-purple-700">🤝 A2A 협업 도메인</span>
            <span className="px-1.5 py-0.5 bg-purple-600 text-white text-[10px] font-bold rounded">
              {stats?.a2a_collaborations || a2aDomains?.length || 0}개 도메인
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {a2aDomains?.map((domain, idx) => (
              <span
                key={idx}
                className="px-2 py-1 bg-white border-2 border-purple-300 text-purple-700 text-xs font-medium rounded-md shadow-sm"
              >
                {domain}
              </span>
            ))}
          </div>
          {stats?.a2a_results_count !== undefined && stats.a2a_results_count > 0 && (
            <div className="mt-2 text-[10px] text-purple-600 font-medium">
              ✨ 병렬 협업으로 {stats.a2a_results_count}개의 추가 조항 발견
            </div>
          )}
        </div>
      )}

      {/* 도메인 조회 정보 */}
      {domainsQueried && domainsQueried.length > 1 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="text-xs text-gray-600 mb-2">
            조회한 도메인 ({domainsQueried.length}개)
          </div>
          <div className="flex flex-wrap gap-1.5">
            {domainsQueried.map((domain, idx) => {
              const isA2A = a2aDomains?.includes(domain);
              return (
                <span
                  key={idx}
                  className={`px-2 py-1 text-xs font-medium rounded ${
                    isA2A
                      ? 'bg-pink-100 text-pink-700 border border-pink-300'
                      : 'bg-cyan-100 text-cyan-700 border border-cyan-300'
                  }`}
                >
                  {domain}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* 검색 방법 비율 */}
      {stats?.total && stats.total > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="text-xs text-gray-600 mb-2">검색 방법 비율</div>
          <div className="flex gap-1 h-2 rounded-full overflow-hidden">
            {stats.vector_count > 0 && (
              <div
                className="bg-green-500"
                style={{ width: `${(stats.vector_count / stats.total) * 100}%` }}
                title={`노드: ${stats.vector_count}개 (${Math.round((stats.vector_count / stats.total) * 100)}%)`}
              />
            )}
            {stats.relationship_count > 0 && (
              <div
                className="bg-purple-500"
                style={{ width: `${(stats.relationship_count / stats.total) * 100}%` }}
                title={`관계: ${stats.relationship_count}개 (${Math.round((stats.relationship_count / stats.total) * 100)}%)`}
              />
            )}
            {stats.graph_expansion_count > 0 && (
              <div
                className="bg-orange-500"
                style={{ width: `${(stats.graph_expansion_count / stats.total) * 100}%` }}
                title={`확장: ${stats.graph_expansion_count}개 (${Math.round((stats.graph_expansion_count / stats.total) * 100)}%)`}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
