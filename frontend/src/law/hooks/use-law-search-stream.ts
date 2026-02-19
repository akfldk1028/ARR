/**
 * 법규 검색 실시간 스트리밍 훅
 * SSE (Server-Sent Events)를 사용하여 MAS 진행상황을 실시간으로 추적
 */

import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * 검색 진행 상태 타입
 */
export type SearchProgressStatus = 'started' | 'searching' | 'processing' | 'complete' | 'error';

/**
 * 검색 단계 타입
 */
export type SearchStage =
  | 'exact_match'
  | 'vector_search'
  | 'relationship_search'
  | 'rne_expansion'
  | 'enrichment';

/**
 * 검색 진행 정보
 */
export interface SearchProgress {
  /** 현재 상태 */
  status: SearchProgressStatus;

  /** 현재 단계 */
  stage?: SearchStage;

  /** 단계 이름 (한글) */
  stage_name?: string;

  /** 진행률 (0~1) */
  progress?: number;

  /** 활성화된 에이전트 이름 */
  agent?: string;

  /** 도메인 ID */
  domain_id?: string;

  /** 노드 개수 */
  node_count?: number;

  /** 타임스탬프 */
  timestamp?: number;

  /** 검색 결과 (완료 시) */
  results?: any[];

  /** 결과 개수 */
  result_count?: number;

  /** 응답 시간 (ms) */
  response_time?: number;

  /** 도메인 이름 */
  domain_name?: string;

  /** 에러 메시지 */
  message?: string;
}

/**
 * 훅 반환 타입
 */
export interface UseLawSearchStreamReturn {
  /** 현재 진행 상태 */
  progress: SearchProgress | null;

  /** 검색 중인지 여부 */
  isSearching: boolean;

  /** 검색 시작 */
  startSearch: (query: string, limit?: number) => void;

  /** 검색 중단 */
  stopSearch: () => void;

  /** 진행 상태 초기화 */
  resetProgress: () => void;
}

/**
 * SSE 기반 실시간 검색 훅
 *
 * @param baseURL - API 기본 URL (기본: http://localhost:8011)
 *
 * @example
 * ```tsx
 * function SearchComponent() {
 *   const { progress, isSearching, startSearch } = useLawSearchStream();
 *
 *   const handleSearch = () => {
 *     startSearch("36조", 5);
 *   };
 *
 *   return (
 *     <div>
 *       {isSearching && <div>진행률: {(progress?.progress || 0) * 100}%</div>}
 *       {progress?.status === 'complete' && <Results data={progress.results} />}
 *     </div>
 *   );
 * }
 * ```
 */
export function useLawSearchStream(
  baseURL: string = 'http://localhost:8011'
): UseLawSearchStreamReturn {
  const [progress, setProgress] = useState<SearchProgress | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const currentQueryRef = useRef<string>('');

  /**
   * 기존 연결 정리
   */
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  /**
   * 검색 시작
   */
  const startSearch = useCallback(
    (query: string, limit: number = 10) => {
      if (!query.trim()) {
        console.warn('Empty query provided');
        return;
      }

      // 기존 연결 종료
      cleanup();

      // 상태 초기화
      currentQueryRef.current = query;
      setIsSearching(true);
      setProgress({
        status: 'started',
        progress: 0,
      });

      // SSE 연결 URL (Django 경로)
      const url = `${baseURL}/agents/law/api/search/stream?query=${encodeURIComponent(query)}&limit=${limit}`;

      try {
        const eventSource = new EventSource(url);
        eventSourceRef.current = eventSource;

        // 메시지 수신
        eventSource.onmessage = (event) => {
          try {
            const data: SearchProgress = JSON.parse(event.data);
            console.log('SSE Event:', data);

            setProgress(data);

            // 완료 또는 에러 시 연결 종료
            if (data.status === 'complete' || data.status === 'error') {
              setIsSearching(false);
              cleanup();
            }
          } catch (error) {
            console.error('Failed to parse SSE data:', error);
          }
        };

        // 에러 처리
        eventSource.onerror = (error) => {
          console.error('SSE Error:', error);

          setProgress({
            status: 'error',
            message: '서버 연결에 실패했습니다. 서버 상태를 확인해주세요.',
          });

          setIsSearching(false);
          cleanup();
        };
      } catch (error) {
        console.error('Failed to create EventSource:', error);

        setProgress({
          status: 'error',
          message: 'EventSource 생성 실패',
        });

        setIsSearching(false);
      }
    },
    [baseURL, cleanup]
  );

  /**
   * 검색 중단
   */
  const stopSearch = useCallback(() => {
    cleanup();
    setIsSearching(false);
    setProgress((prev) => ({
      ...prev,
      status: 'error',
      message: '사용자가 검색을 중단했습니다.',
    } as SearchProgress));
  }, [cleanup]);

  /**
   * 진행 상태 초기화
   */
  const resetProgress = useCallback(() => {
    setProgress(null);
    currentQueryRef.current = '';
  }, []);

  /**
   * 컴포넌트 언마운트 시 정리
   */
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    progress,
    isSearching,
    startSearch,
    stopSearch,
    resetProgress,
  };
}
