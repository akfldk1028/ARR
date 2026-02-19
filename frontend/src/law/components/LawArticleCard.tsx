/**
 * 법률 조항 카드 컴포넌트
 */

import React from 'react';
import type { LawArticle } from '../lib/types';

interface LawArticleCardProps {
  /** 법률 조항 데이터 */
  article: LawArticle;

  /** 순서 번호 */
  index: number;
}

/**
 * 검색 방법 배지 색상
 */
const STAGE_COLORS: Record<string, string> = {
  vector: 'bg-green-100 text-green-800',
  relationship: 'bg-purple-100 text-purple-800',
  graph_expansion: 'bg-orange-100 text-orange-800',
};

/**
 * 검색 방법 배지 텍스트
 */
const STAGE_LABELS: Record<string, string> = {
  vector: '노드',
  relationship: '관계',
  graph_expansion: '확장',
};

/**
 * 법률 조항 카드 컴포넌트
 */
export function LawArticleCard({ article, index }: LawArticleCardProps) {
  /**
   * 유사도를 백분율로 변환
   */
  const similarityPercent = Math.round(article.similarity * 100);

  /**
   * A2A 협업 결과인지 확인
   */
  const isA2A = article.via_a2a === true;

  /**
   * 유사도에 따른 배지 색상
   */
  const getSimilarityColor = (similarity: number): string => {
    if (similarity >= 0.8) return 'bg-red-100 text-red-800';
    if (similarity >= 0.6) return 'bg-yellow-100 text-yellow-800';
    return 'bg-gray-100 text-gray-800';
  };

  /**
   * 출처 배지 색상
   */
  const getSourceColor = (source: string): string => {
    return source === 'my_domain' ? 'bg-cyan-100 text-cyan-800' : 'bg-pink-100 text-pink-800';
  };

  /**
   * 카드 테두리 색상 (A2A 협업 시 강조)
   */
  const cardBorderClass = isA2A
    ? 'border-2 border-pink-300 shadow-md shadow-pink-100'
    : 'border border-gray-200';

  return (
    <div className={`law-article-card bg-white rounded-lg p-4 hover:shadow-lg transition-all ${cardBorderClass}`}>
      {/* A2A 협업 배너 */}
      {isA2A && (
        <div className="mb-3 -mt-4 -mx-4 px-4 py-2 bg-gradient-to-r from-pink-100 to-purple-100 border-b-2 border-pink-200">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-pink-700">🤝 A2A 협업 결과</span>
            {article.source_domain && (
              <span className="px-2 py-0.5 bg-white border border-pink-300 text-pink-700 text-xs font-medium rounded">
                {article.source_domain}
              </span>
            )}
          </div>
          {article.a2a_refined_query && (
            <div className="mt-1 text-[10px] text-purple-600">
              <span className="font-semibold">정제된 쿼리:</span> {article.a2a_refined_query}
            </div>
          )}
        </div>
      )}

      {/* 헤더 */}
      <div className="flex items-start justify-between mb-2">
        {/* 순서 번호 */}
        <div className="flex items-center gap-2">
          <div className={`flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm ${
            isA2A ? 'bg-gradient-to-r from-pink-500 to-purple-500 text-white' : 'bg-blue-600 text-white'
          }`}>
            {index}
          </div>

          {/* 유사도 배지 */}
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSimilarityColor(article.similarity)}`}>
            유사도 {similarityPercent}%
          </span>
        </div>

        {/* 출처 배지 */}
        {!isA2A && (
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSourceColor(article.source)}`}>
            {article.source === 'my_domain' ? '자체' : '협업'}
          </span>
        )}
      </div>

      {/* 법률 조항 ID */}
      <div className="mb-2">
        <h4 className="text-sm font-semibold text-gray-900 break-all">
          📄 {article.hang_id}
        </h4>
        {article.unit_path && (
          <p className="text-xs text-gray-500 mt-1">경로: {article.unit_path}</p>
        )}
      </div>

      {/* 내용 */}
      <div className="mb-3">
        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
          {article.content}
        </p>
      </div>

      {/* 검색 방법 태그 */}
      <div className="flex flex-wrap gap-1.5">
        <span className="text-xs text-gray-500 font-medium">검색:</span>
        {article.stages.map((stage, idx) => (
          <span
            key={idx}
            className={`px-2 py-0.5 rounded text-xs font-medium ${STAGE_COLORS[stage] || 'bg-gray-100 text-gray-800'}`}
          >
            {STAGE_LABELS[stage] || stage}
          </span>
        ))}
      </div>
    </div>
  );
}
