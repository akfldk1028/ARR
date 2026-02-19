/**
 * 법규 검색 입력 컴포넌트
 */

import React, { useState, KeyboardEvent } from 'react';

interface QueryInputProps {
  /** 검색 실행 콜백 */
  onSearch: (query: string) => void;

  /** 로딩 상태 */
  isLoading?: boolean;

  /** 플레이스홀더 텍스트 */
  placeholder?: string;

  /** 초기 값 */
  initialValue?: string;
}

/**
 * 법규 검색 입력 컴포넌트
 */
export function QueryInput({
  onSearch,
  isLoading = false,
  placeholder = '법규 내용을 검색하세요... (예: 개발행위 허가 요건)',
  initialValue = '',
}: QueryInputProps) {
  const [query, setQuery] = useState(initialValue);

  /**
   * 검색 실행
   */
  const handleSearch = () => {
    if (query.trim() && !isLoading) {
      onSearch(query.trim());
    }
  };

  /**
   * Enter 키 처리
   */
  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  return (
    <div className="query-input-container">
      <div className="flex gap-2">
        {/* 입력 필드 */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={placeholder}
          disabled={isLoading}
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
        />

        {/* 검색 버튼 */}
        <button
          onClick={handleSearch}
          disabled={!query.trim() || isLoading}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
        >
          {isLoading ? '검색 중...' : '검색'}
        </button>
      </div>

      {/* 예시 쿼리 */}
      {!query && (
        <div className="mt-2 text-sm text-gray-500">
          <span className="font-medium">예시:</span>
          <button
            onClick={() => setQuery('개발행위 허가 요건')}
            className="ml-2 text-blue-600 hover:underline"
          >
            개발행위 허가 요건
          </button>
          <button
            onClick={() => setQuery('도시계획 수립 절차')}
            className="ml-2 text-blue-600 hover:underline"
          >
            도시계획 수립 절차
          </button>
          <button
            onClick={() => setQuery('용도지역 변경')}
            className="ml-2 text-blue-600 hover:underline"
          >
            용도지역 변경
          </button>
        </div>
      )}
    </div>
  );
}
