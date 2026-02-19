/**
 * 법규 AI 채팅 메인 컴포넌트
 * SSE 스트리밍 진행상황 표시 기능 통합
 */

import React, { useRef, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LawAPIProvider, useLawAPI } from './contexts/LawAPIContext';
import { useLawChat } from './hooks/use-law-chat';
import { useLawSearchStream } from './hooks/use-law-search-stream';
import { QueryInput } from './components/QueryInput';
import { ResultDisplay } from './components/ResultDisplay';
import {
  SearchProgressIndicator,
  SearchCompleteHeader,
  SearchErrorIndicator,
} from './components/SearchProgress';

/**
 * 법규 채팅 인터페이스 내부 컴포넌트
 */
function LawChatInner() {
  const navigate = useNavigate();
  const { domains, domainsLoading, selectedDomainId, setSelectedDomainId, isConnected } =
    useLawAPI();
  const { messages, isLoading, search, clearMessages, addMessage } = useLawChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // SSE 스트리밍 훅 (Django 백엔드 사용)
  const { progress, isSearching, startSearch, stopSearch, resetProgress } = useLawSearchStream('http://127.0.0.1:8000');

  // 스트리밍 모드 토글 상태
  const [streamingMode, setStreamingMode] = useState(false);

  /**
   * 메시지 자동 스크롤
   */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /**
   * SSE 스트리밍 완료 시 결과를 메시지로 추가
   */
  useEffect(() => {
    if (progress?.status === 'complete' && progress.results) {
      // 스트리밍 검색 완료 메시지 추가
      addMessage({
        role: 'assistant',
        content: `검색 완료 (${progress.response_time}ms)`,
        search_response: {
          results: progress.results,
          total_count: progress.result_count || progress.results.length,
          query: '', // 쿼리는 이미 사용자 메시지에 있음
          response_time: progress.response_time || 0,
          domain_id: progress.domain_id,
          domain_name: progress.domain_name,
        },
      });

      // 진행상황 초기화 (다음 검색을 위해)
      resetProgress();
    }
  }, [progress, addMessage, resetProgress]);

  /**
   * 검색 핸들러 (스트리밍/일반 모드 분기)
   */
  const handleSearch = (query: string) => {
    if (streamingMode) {
      // SSE 스트리밍 검색
      // 사용자 메시지 추가
      addMessage({
        role: 'user',
        content: query,
      });

      // 검색 시작
      resetProgress(); // 이전 진행상황 초기화
      startSearch(query, 10);
    } else {
      // 기존 REST API 검색
      search(query, 10);
    }
  };

  /**
   * 뒤로 가기
   */
  const handleBack = () => {
    navigate(-1);
  };

  return (
    <div className="law-chat-container flex flex-col h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-200 flex-shrink-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* 뒤로 가기 버튼 */}
              <button
                onClick={handleBack}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                ← 뒤로가기
              </button>

              {/* 타이틀 */}
              <div>
                <h1 className="text-2xl font-bold text-gray-900">법규 검색 AI 채팅</h1>
                <p className="text-sm text-gray-600">
                  국토의 계획 및 이용에 관한 법률 시스템
                </p>
              </div>
            </div>

            {/* 연결 상태 */}
            <div className="flex items-center gap-4">
              {/* 백엔드 연결 상태 */}
              <div className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}
                />
                <span className="text-sm text-gray-600">
                  {isConnected ? '백엔드 연결됨' : '백엔드 연결 끊김'}
                </span>
              </div>

              {/* 스트리밍 모드 토글 */}
              <label className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={streamingMode}
                  onChange={(e) => setStreamingMode(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2 cursor-pointer"
                />
                <span className="text-sm text-gray-600 group-hover:text-gray-900 transition-colors">
                  실시간 진행상황
                </span>
              </label>

              {/* 도메인 선택 */}
              {!domainsLoading && domains.length > 0 && (
                <select
                  value={selectedDomainId || ''}
                  onChange={(e) => setSelectedDomainId(e.target.value || null)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">전체 도메인 (자동 라우팅)</option>
                  {domains.map((domain) => (
                    <option key={domain.domain_id} value={domain.domain_id}>
                      {domain.domain_name} ({domain.node_count}개 노드)
                    </option>
                  ))}
                </select>
              )}

              {/* 검색 중단 버튼 (스트리밍 모드에서만) */}
              {streamingMode && isSearching && (
                <button
                  onClick={stopSearch}
                  className="px-4 py-2 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 border border-red-300 rounded-lg transition-colors font-medium"
                >
                  검색 중단
                </button>
              )}

              {/* 초기화 버튼 */}
              {messages.length > 0 && (
                <button
                  onClick={clearMessages}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  대화 초기화
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 메인 콘텐츠 (스크롤 가능) */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 py-6">
          {/* 안내 메시지 (메시지가 없을 때만) */}
          {messages.length === 0 && (
            <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-blue-900 mb-2">
                💡 법규 검색 AI에 오신 것을 환영합니다!
              </h2>
              <p className="text-sm text-blue-800 mb-3">
                이 시스템은 Multi-Agent System과 이중 임베딩 전략을 사용하여 법률 조항을 검색합니다.
              </p>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• <strong>노드 임베딩 (OpenAI 3072dim)</strong>: 법률 조항 내용 기반 의미 검색</li>
                <li>• <strong>관계 임베딩 (OpenAI 3072dim)</strong>: 법률 구조 관계 기반 검색</li>
                <li>• <strong>그래프 확장 (RNE)</strong>: 연관 조항 탐색</li>
                <li>• <strong>도메인 협업 (A2A)</strong>: 여러 도메인 간 협업 검색</li>
              </ul>
              {streamingMode && (
                <div className="mt-3 pt-3 border-t border-blue-200">
                  <p className="text-sm text-blue-700 font-semibold">
                    실시간 진행상황 모드가 활성화되었습니다. 검색 중 각 단계의 진행상황을 확인할 수 있습니다.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* 검색 입력 */}
          <div className="mb-6">
            <QueryInput onSearch={handleSearch} isLoading={isLoading || isSearching} />
          </div>

          {/* 메시지 목록 */}
          <div className="space-y-4 pb-6">
            {messages.map((message) => (
              <div key={message.id} className="message-container">
                {/* 사용자 메시지 */}
                {message.role === 'user' && (
                  <div className="flex justify-end mb-2">
                    <div className="bg-blue-600 text-white rounded-lg px-4 py-3 max-w-2xl">
                      <p className="text-sm font-medium">{message.content}</p>
                    </div>
                  </div>
                )}

                {/* AI 응답 */}
                {message.role === 'assistant' && (
                  <div className="bg-white rounded-lg border border-gray-200 p-4">
                    {/* 로딩 중 (비스트리밍 모드) */}
                    {!streamingMode && message.loading && (
                      <div className="flex items-center gap-2 text-gray-600">
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                        <span>{message.content}</span>
                      </div>
                    )}

                    {/* 에러 */}
                    {message.error && !message.loading && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <p className="text-red-800 font-medium">❌ {message.content}</p>
                        <p className="text-sm text-red-600 mt-1">{message.error}</p>
                      </div>
                    )}

                    {/* 검색 결과 */}
                    {message.search_response && !message.loading && !message.error && (
                      <div className="space-y-4">
                        {/* 완료 헤더 (스트리밍 모드에서는 이미 표시됨) */}
                        {!streamingMode && (
                          <div className="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg p-4">
                            <div className="flex items-center gap-3">
                              <span className="text-2xl">✅</span>
                              <div>
                                <div className="font-semibold text-green-800">검색 완료</div>
                                <div className="text-sm text-green-600">
                                  {message.search_response.total_count}개 결과 발견
                                  {message.search_response.domain_name &&
                                    ` · ${message.search_response.domain_name}`}
                                </div>
                              </div>
                            </div>
                            <div className="bg-green-600 text-white px-4 py-2 rounded-full font-semibold text-sm">
                              {message.search_response.response_time}ms
                            </div>
                          </div>
                        )}

                        {/* 결과 표시 */}
                        <ResultDisplay response={message.search_response} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* 스트리밍 진행상황 (검색 중일 때만) */}
            {streamingMode && isSearching && progress && (
              <div className="message-container">
                <div className="bg-white rounded-lg border border-gray-200 p-4">
                  {/* 진행 중 */}
                  {progress.status !== 'complete' && progress.status !== 'error' && (
                    <SearchProgressIndicator progress={progress} />
                  )}

                  {/* 에러 */}
                  {progress.status === 'error' && (
                    <SearchErrorIndicator
                      message={progress.message || '알 수 없는 오류가 발생했습니다.'}
                    />
                  )}

                  {/* 완료 헤더 */}
                  {progress.status === 'complete' && (
                    <SearchCompleteHeader
                      resultCount={progress.result_count || 0}
                      responseTime={progress.response_time || 0}
                      domainName={progress.domain_name}
                    />
                  )}
                </div>
              </div>
            )}

            {/* 자동 스크롤 타겟 */}
            <div ref={messagesEndRef} />
          </div>

          {/* 백엔드 연결 안 됨 경고 */}
          {!isConnected && messages.length === 0 && (
            <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-yellow-900 mb-2">
                ⚠️ 백엔드 서버에 연결할 수 없습니다
              </h3>
              <p className="text-sm text-yellow-800 mb-2">
                Django 백엔드 서버가 실행 중인지 확인하세요.
              </p>
              <div className="text-sm text-yellow-700 bg-yellow-100 rounded p-3 mt-3">
                <p className="font-mono">
                  cd D:\Data\11_Backend\01_ARR\backend
                </p>
                <p className="font-mono mt-1">
                  daphne -b 0.0.0.0 -p 8000 backend.asgi:application
                </p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

/**
 * 법규 AI 채팅 메인 컴포넌트 (Provider 포함)
 */
export default function LawChat() {
  return (
    <LawAPIProvider>
      <LawChatInner />
    </LawAPIProvider>
  );
}
